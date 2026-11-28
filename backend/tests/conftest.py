"""Pytest fixtures for isolated HunarLink FastAPI testing (ASIGS Guardrails + Razorpay).

NOTE: Tests run against an in-memory SQLite database derived from SQLAlchemy models
aligned verbatim with HunarLink's MySQL 8.4 LTS schema, using FakeRazorpayGateway.
These are automated mocked unit/integration tests — NEVER equate passing mocked tests
with live MySQL 8.4 execution or Razorpay Live Mode readiness.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import AuthenticatedPrincipal, get_current_principal
from app.core.config import Settings
from app.core.database import get_db
from app.integrations.razorpay.exceptions import RazorpayGatewayError, RazorpayTimeoutError
from app.integrations.razorpay.schemas import (
    RazorpayOrderDTO,
    RazorpayPaymentDTO,
    RazorpayRefundDTO,
)
from app.main import create_app
from app.models.base import Base, new_uuid, utcnow
from app.models.core_models import (
    Category,
    DealerProfile,
    DealerQuote,
    DealerWholesaleListing,
    GIReferenceRecord,
    PlatformRole,
    Product,
    ProductVariant,
    RetailOrder,
    RetailOrderItem,
    SellerFulfilmentGroup,
    SellerProductListing,
    SellerProfile,
    SupplierProfile,
    User,
    UserRoleAssignment,
    Warehouse,
    WarehouseStock,
    WholesaleBuyerProfile,
    WholesaleOrder,
    WholesaleOrderItem,
    WholesaleRFQ,
)
from app.models.guardrail_models import GuardrailRule
from app.modules.guardrails.router import _document_upload_limiter
from app.modules.payments.router import get_razorpay_gateway, payment_rate_limiter
from app.modules.storefront.router import (
    artisan_lookup_rate_limiter,
    product_lookup_rate_limiter,
    review_write_rate_limiter,
)


@dataclass
class FakeRazorpayGateway:
    """Deterministic in-memory Razorpay mock for unit/integration tests."""

    create_order_calls: int = 0
    fetch_payment_calls: int = 0
    create_refund_calls: int = 0
    fail_create_order_with: str | None = None  # "timeout" | "gateway_error"
    next_payment_status: str = "captured"
    override_payment_amount_paise: int | None = None
    override_payment_currency: str | None = None
    override_payment_order_id: str | None = None
    orders: dict[str, RazorpayOrderDTO] = field(default_factory=dict)

    def create_order(
        self,
        *,
        amount_paise: int,
        currency: str,
        receipt: str,
        notes: dict[str, str],
    ) -> RazorpayOrderDTO:
        self.create_order_calls += 1
        if self.fail_create_order_with == "timeout":
            raise RazorpayTimeoutError("Simulated Razorpay API timeout")
        if self.fail_create_order_with == "gateway_error":
            raise RazorpayGatewayError("Simulated Razorpay rejection", code="BAD_REQUEST_ERROR")

        order_id = f"order_test_{uuid.uuid4().hex[:12]}"
        dto = RazorpayOrderDTO(
            id=order_id,
            amount=amount_paise,
            currency=currency,
            receipt=receipt,
            status="created",
        )
        self.orders[order_id] = dto
        return dto

    def fetch_payment(self, *, razorpay_payment_id: str) -> RazorpayPaymentDTO:
        self.fetch_payment_calls += 1
        latest_order = list(self.orders.values())[-1] if self.orders else None
        return RazorpayPaymentDTO(
            id=razorpay_payment_id,
            order_id=self.override_payment_order_id or (latest_order.id if latest_order else None),
            amount=self.override_payment_amount_paise
            if self.override_payment_amount_paise is not None
            else (latest_order.amount if latest_order else 10000),
            currency=self.override_payment_currency or (latest_order.currency if latest_order else "INR"),
            status=self.next_payment_status,
            method="upi",
        )

    def create_refund(
        self,
        *,
        razorpay_payment_id: str,
        amount_paise: int,
        notes: dict[str, str],
    ) -> RazorpayRefundDTO:
        self.create_refund_calls += 1
        return RazorpayRefundDTO(
            id=f"rfnd_test_{uuid.uuid4().hex[:10]}",
            payment_id=razorpay_payment_id,
            amount=amount_paise,
            currency="INR",
            status="processed",
        )


@pytest.fixture()
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="testing",
        database_url="sqlite+pysqlite:///:memory:",
        private_storage_dir=str(tmp_path / "private_uploads"),
        max_upload_size_bytes=512_000,
        malware_scanner_mode="pending_only",
        razorpay_key_id="rzp_test_HunarLinkKeyId123",
        razorpay_key_secret=SecretStr("rzp_test_secret_NEVER_EXPOSE_987654321"),
        razorpay_webhook_secret=SecretStr("rzp_webhook_secret_SEPARATE_123456789"),
    )


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = SessionLocal()

    for code, name in [
        ("CUSTOMER", "Retail Customer"),
        ("DIRECT_SELLER", "Direct Artisan Seller"),
        ("SUPPLIER", "Craft Supplier"),
        ("DEALER", "Wholesale Dealer"),
        ("ADMIN", "Platform Admin"),
    ]:
        session.add(PlatformRole(id=new_uuid(), code=code, name=name))

    session.add(
        GuardrailRule(
            id=new_uuid(),
            rule_code="PROD_SELLER_CANNOT_SELF_VERIFY_GI",
            layer="PRODUCT",
            name="Block seller self-assignment of GI_VERIFIED",
            default_outcome="BLOCK",
            is_active=True,
            rule_version="1.0.0",
        )
    )
    session.commit()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def fake_razorpay() -> FakeRazorpayGateway:
    return FakeRazorpayGateway()


@pytest.fixture()
def app_and_client(
    test_settings: Settings,
    db_session: Session,
    fake_razorpay: FakeRazorpayGateway,
):
    payment_rate_limiter._hits.clear()
    artisan_lookup_rate_limiter._hits.clear()
    product_lookup_rate_limiter._hits.clear()
    review_write_rate_limiter._hits.clear()
    _document_upload_limiter._hits.clear()
    app = create_app(settings_override=test_settings)

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_razorpay_gateway] = lambda: fake_razorpay

    client = TestClient(app)
    yield app, client
    app.dependency_overrides.clear()


def set_authenticated_principal(app, principal: AuthenticatedPrincipal | None) -> None:
    if principal is None:
        app.dependency_overrides.pop(get_current_principal, None)
    else:
        app.dependency_overrides[get_current_principal] = lambda: principal


def create_user_with_roles(
    db: Session,
    *,
    email: str,
    full_name: str,
    roles: list[str],
    account_status: str = "ACTIVE",
    permissions: set[str] | None = None,
) -> tuple[User, AuthenticatedPrincipal]:
    from app.modules.auth.role_views import derive_account_role

    parts = full_name.split(" ", 1)
    user = User(
        id=new_uuid(),
        clerk_user_id=f"user_{uuid.uuid4().hex[:14]}",
        email=email,
        first_name=parts[0],
        last_name=parts[1] if len(parts) > 1 else None,
        display_name=full_name,
        account_role=derive_account_role(roles, account_status=account_status),
        account_status=account_status,
    )
    db.add(user)
    db.flush()

    for code in roles:
        role = db.query(PlatformRole).filter(PlatformRole.code == code).one()
        db.add(
            UserRoleAssignment(
                id=new_uuid(),
                user_id=user.id,
                platform_role_id=role.id,
                assignment_status="ACTIVE",
            )
        )

    db.commit()
    principal = AuthenticatedPrincipal(
        user_id=user.id,
        clerk_user_id=user.clerk_user_id,
        email=user.email,
        account_status=user.account_status,
        roles=frozenset(roles),
        admin_permissions=frozenset(permissions or set()),
        is_active_admin="ADMIN" in roles,
    )
    return user, principal


def seed_marketplace_entities(db: Session) -> dict[str, Any]:
    """Seed clean, realistic test catalog, seller, supplier, dealer, warehouse & stock."""
    cat = Category(
        id=new_uuid(),
        code=f"PASH-{uuid.uuid4().hex[:4].upper()}",
        slug=f"pashmina-{uuid.uuid4().hex[:6]}",
        name="Kashmir Pashmina",
        is_gi_eligible_category=True,
        is_active=True,
    )
    db.add(cat)
    db.flush()

    prod = Product(
        id=new_uuid(),
        category_id=cat.id,
        sku_root=f"KANIROOT-{uuid.uuid4().hex[:5].upper()}",
        slug=f"kani-shawl-{uuid.uuid4().hex[:6]}",
        name="Handwoven Kani Pashmina Shawl",
        description="Traditional Kashmiri Kani loom pashmina.",
        approval_status="APPROVED",
        gi_status="UNVERIFIED",
        is_active=True,
    )
    db.add(prod)
    db.flush()

    variant = ProductVariant(
        id=new_uuid(),
        product_id=prod.id,
        variant_sku=f"KANI-{uuid.uuid4().hex[:6].upper()}",
        variant_name="Natural Ivory 200x100cm",
        base_mrp=Decimal("18000.00"),
        is_active=True,
    )
    db.add(variant)

    seller_user, seller_principal = create_user_with_roles(
        db, email="seller@example.com", full_name="Bashir Ahmad", roles=["DIRECT_SELLER"]
    )
    seller_profile = SellerProfile(
        id=new_uuid(),
        user_id=seller_user.id,
        store_name="Bashir Kani Looms",
        store_slug=f"bashir-kani-{uuid.uuid4().hex[:6]}",
        verification_path="GI",
        verification_status="APPROVED",
        profile_status="ACTIVE",
    )
    db.add(seller_profile)

    supplier_user, supplier_principal = create_user_with_roles(
        db, email="supplier@example.com", full_name="Farooq Crafts", roles=["SUPPLIER"]
    )
    supplier_profile = SupplierProfile(
        id=new_uuid(),
        user_id=supplier_user.id,
        supplier_name="Srinagar Craft Cooperative",
        verification_status="APPROVED",
        profile_status="ACTIVE",
    )
    db.add(supplier_profile)

    dealer_user, dealer_principal = create_user_with_roles(
        db, email="dealer@example.com", full_name="Chinar Wholesale", roles=["DEALER"]
    )
    dealer_profile = DealerProfile(
        id=new_uuid(),
        user_id=dealer_user.id,
        dealership_name="Chinar Heritage Wholesale Pvt Ltd",
        dealership_slug=f"chinar-ws-{uuid.uuid4().hex[:6]}",
        city="Srinagar",
        state_province="Jammu and Kashmir",
        verification_status="APPROVED",
        profile_status="ACTIVE",
    )
    db.add(dealer_profile)
    db.flush()

    warehouse = Warehouse(
        id=new_uuid(),
        owner_type="DEALER",
        dealer_profile_id=dealer_profile.id,
        warehouse_code=f"WH-SXR-{uuid.uuid4().hex[:4].upper()}",
        name="Srinagar Main Depot",
        address_line1="Residency Road, Craft Complex",
        city="Srinagar",
        state_province="Jammu and Kashmir",
        postal_code="190001",
        is_active=True,
    )
    db.add(warehouse)
    db.flush()

    stock = WarehouseStock(
        id=new_uuid(),
        warehouse_id=warehouse.id,
        product_id=prod.id,
        product_variant_id=variant.id,
        owner_type="DEALER",
        dealer_profile_id=dealer_profile.id,
        available_quantity=Decimal("10.000"),
        reserved_quantity=Decimal("0.000"),
        damaged_quantity=Decimal("0.000"),
        version=1,
    )
    db.add(stock)

    active_listing = SellerProductListing(
        id=new_uuid(),
        seller_profile_id=seller_profile.id,
        product_id=prod.id,
        product_variant_id=variant.id,
        seller_sku=f"SEL-SKU-{uuid.uuid4().hex[:6].upper()}",
        listing_title="Handwoven Kani Shawl",
        selling_price=Decimal("14500.00"),
        compare_at_mrp=Decimal("18000.00"),
        currency_code="INR",
        min_order_qty=1,
        listing_status="ACTIVE",
    )
    db.add(active_listing)

    ws_listing = DealerWholesaleListing(
        id=new_uuid(),
        dealer_profile_id=dealer_profile.id,
        warehouse_id=warehouse.id,
        warehouse_stock_id=stock.id,
        product_id=prod.id,
        product_variant_id=variant.id,
        dealer_sku=f"DLR-SKU-{uuid.uuid4().hex[:6].upper()}",
        listing_title="Wholesale Kani Pashmina Lot",
        base_unit_price=Decimal("11000.00"),
        currency_code="INR",
        minimum_order_quantity=Decimal("5.000"),
        listing_status="ACTIVE",
    )
    db.add(ws_listing)

    gi_ref = GIReferenceRecord(
        id=new_uuid(),
        gi_registration_number="GI-46-KASHMIR-PASHMINA",
        gi_name="Kashmir Pashmina",
        authorized_geographic_area="Kashmir Valley, Jammu and Kashmir",
        state_region="Jammu and Kashmir",
        source_authority="GI Registry India (Test Fixture)",
        dataset_version="test-gi-ref-2026.1",
        is_active=True,
    )
    db.add(gi_ref)

    buyer_user, buyer_principal = create_user_with_roles(
        db, email="buyer@example.com", full_name="Aarav Sharma", roles=["CUSTOMER"]
    )
    ws_buyer_profile = WholesaleBuyerProfile(
        id=new_uuid(),
        user_id=buyer_user.id,
        company_name="Aarav Heritage Emporium LLP",
        business_city="New Delhi",
        business_state="Delhi",
        profile_status="ACTIVE",
        verification_status="APPROVED",
    )
    db.add(ws_buyer_profile)

    other_user, other_principal = create_user_with_roles(
        db, email="other@example.com", full_name="Zoya Mir", roles=["CUSTOMER"]
    )
    admin_user, admin_principal = create_user_with_roles(
        db,
        email="admin@example.com",
        full_name="HunarLink Ops Admin",
        roles=["ADMIN"],
        permissions={
            "guardrails.read",
            "guardrails.decide",
            "sellers.review",
            "gi.review",
            "procurement.read",
            "payments.read",
            "payments.refund",
        },
    )
    db.commit()

    return {
        "category": cat,
        "product": prod,
        "variant": variant,
        "seller_user": seller_user,
        "seller_principal": seller_principal,
        "seller_profile": seller_profile,
        "supplier_user": supplier_user,
        "supplier_principal": supplier_principal,
        "supplier_profile": supplier_profile,
        "dealer_user": dealer_user,
        "dealer_principal": dealer_principal,
        "dealer_profile": dealer_profile,
        "warehouse": warehouse,
        "stock": stock,
        "active_listing": active_listing,
        "ws_listing": ws_listing,
        "ws_buyer_profile": ws_buyer_profile,
        "gi_ref": gi_ref,
        "buyer_user": buyer_user,
        "buyer_principal": buyer_principal,
        "other_user": other_user,
        "other_principal": other_principal,
        "admin_user": admin_user,
        "admin_principal": admin_principal,
    }


def create_retail_order(
    db: Session,
    *,
    buyer_user_id: str,
    seller_profile_id: str,
    listing_id: str,
    product_variant_id: str,
    unit_price: Decimal = Decimal("14500.00"),
    quantity: int = 2,
    payment_method: str = "RAZORPAY_STANDARD",
    currency_code: str = "INR",
    discount_amount: Decimal = Decimal("0.00"),
    tax_amount: Decimal = Decimal("0.00"),
    shipping_amount: Decimal = Decimal("0.00"),
) -> RetailOrder:
    variant = db.query(ProductVariant).filter(ProductVariant.id == product_variant_id).one()
    subtotal = (unit_price * Decimal(quantity)).quantize(Decimal("0.01"))
    total = (subtotal - discount_amount + tax_amount + shipping_amount).quantize(Decimal("0.01"))
    order = RetailOrder(
        id=new_uuid(),
        order_number=f"HL-RET-{uuid.uuid4().hex[:8].upper()}",
        customer_user_id=buyer_user_id,
        shipping_address_snapshot_json={"city": "Jammu", "state": "Jammu and Kashmir", "pincode": "180001"},
        currency_code=currency_code,
        subtotal_amount=subtotal,
        discount_amount=discount_amount,
        tax_amount=tax_amount,
        shipping_fee=shipping_amount,
        total_amount=total,
        payment_method=payment_method,
        payment_status="PENDING",
        fulfilment_status="PENDING_PAYMENT",
    )
    db.add(order)
    db.flush()

    group = SellerFulfilmentGroup(
        id=new_uuid(),
        fulfilment_number=f"FG-{uuid.uuid4().hex[:8].upper()}",
        retail_order_id=order.id,
        seller_profile_id=seller_profile_id,
        currency_code=currency_code,
        subtotal_amount=subtotal,
        group_total_amount=total,
        fulfilment_status="PENDING_PAYMENT",
    )
    db.add(group)
    db.flush()

    db.add(
        RetailOrderItem(
            id=new_uuid(),
            retail_order_id=order.id,
            seller_fulfilment_group_id=group.id,
            seller_listing_id=listing_id,
            product_id=variant.product_id,
            product_variant_id=product_variant_id,
            product_name_snapshot="Handwoven Kani Pashmina Shawl",
            sku_snapshot=variant.variant_sku,
            quantity=quantity,
            unit_price_snapshot=unit_price,
            line_total_amount=subtotal,
            currency_code=currency_code,
        )
    )
    db.commit()
    return order


def create_wholesale_order(
    db: Session,
    *,
    buyer_user_id: str,
    dealer_profile_id: str,
    ws_listing_id: str | None,
    product_variant_id: str,
    order_source: str = "DIRECT_WHOLESALE_LISTING",
    unit_price: Decimal = Decimal("11000.00"),
    quantity: Decimal = Decimal("5.000"),
    quote_valid_until_offset_hours: int = 48,
    quote_status: str = "ACCEPTED",
) -> WholesaleOrder:
    ws_buyer = db.query(WholesaleBuyerProfile).filter(WholesaleBuyerProfile.user_id == buyer_user_id).one()
    variant = db.query(ProductVariant).filter(ProductVariant.id == product_variant_id).one()
    dealer = db.query(DealerProfile).filter(DealerProfile.id == dealer_profile_id).one()

    rfq_id = None
    quote_id = None
    subtotal = (unit_price * quantity).quantize(Decimal("0.01"))

    if order_source == "ACCEPTED_RFQ_QUOTE":
        rfq = WholesaleRFQ(
            id=new_uuid(),
            rfq_number=f"RFQ-{uuid.uuid4().hex[:8].upper()}",
            wholesale_buyer_profile_id=ws_buyer.id,
            buyer_user_id=buyer_user_id,
            title="Festive Kani Pashmina Bulk Order",
            rfq_status="ACCEPTED",
        )
        db.add(rfq)
        db.flush()
        quote = DealerQuote(
            id=new_uuid(),
            quote_number=f"QT-{uuid.uuid4().hex[:8].upper()}",
            wholesale_rfq_id=rfq.id,
            dealer_profile_id=dealer_profile_id,
            submitted_by_user_id=dealer.user_id,
            currency_code="INR",
            subtotal_amount=subtotal,
            total_amount=subtotal,
            valid_until=utcnow() + timedelta(hours=quote_valid_until_offset_hours),
            quote_status=quote_status,
        )
        db.add(quote)
        db.flush()
        rfq_id = rfq.id
        quote_id = quote.id

    order = WholesaleOrder(
        id=new_uuid(),
        order_number=f"HL-WS-{uuid.uuid4().hex[:8].upper()}",
        wholesale_buyer_profile_id=ws_buyer.id,
        buyer_user_id=buyer_user_id,
        dealer_profile_id=dealer_profile_id,
        order_source=order_source,
        wholesale_rfq_id=rfq_id,
        dealer_quote_id=quote_id,
        shipping_address_snapshot_json={"city": "New Delhi", "state": "Delhi", "pincode": "110001"},
        currency_code="INR",
        subtotal_amount=subtotal,
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        shipping_fee=Decimal("0.00"),
        total_amount=subtotal,
        payment_method="RAZORPAY_STANDARD",
        payment_status="PENDING",
        fulfilment_status="PENDING_PAYMENT",
    )
    db.add(order)
    db.flush()
    db.add(
        WholesaleOrderItem(
            id=new_uuid(),
            wholesale_order_id=order.id,
            dealer_wholesale_listing_id=ws_listing_id,
            product_id=variant.product_id,
            product_variant_id=product_variant_id,
            product_name_snapshot="Wholesale Kani Pashmina Lot",
            sku_snapshot=variant.variant_sku,
            quantity=quantity,
            unit_price_snapshot=unit_price,
            line_total_amount=subtotal,
            currency_code="INR",
        )
    )
    db.commit()
    return order
