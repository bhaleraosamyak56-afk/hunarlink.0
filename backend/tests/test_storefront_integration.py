"""End-to-end Storefront -> Retail Order -> Razorpay Checkout integration tests (6 tests)."""
from __future__ import annotations

from decimal import Decimal

from app.integrations.razorpay.signatures import compute_checkout_signature
from tests.conftest import seed_marketplace_entities, set_authenticated_principal


def test_01_public_catalog_and_artisans_return_active_db_records_while_orders_require_auth(app_and_client, db_session):
    app, client = app_and_client
    entities = seed_marketplace_entities(db_session)
    set_authenticated_principal(app, None)

    # Public read-only browsing works for catalog & verified artisan profiles
    resp = client.get("/api/v1/catalog/products")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["listing_id"] == entities["active_listing"].id
    assert Decimal(items[0]["selling_price"]) == Decimal("14500.00")

    artisans_resp = client.get("/api/v1/artisans")
    assert artisans_resp.status_code == 200
    artisans = artisans_resp.json()
    assert len(artisans) == 1
    assert artisans[0]["slug"] == entities["seller_profile"].store_slug
    assert artisans[0]["listing_count"] == 1

    detail_resp = client.get(f"/api/v1/artisans/{entities['seller_profile'].store_slug}")
    assert detail_resp.status_code == 200
    assert len(detail_resp.json()["listings"]) == 1

    # All private/mutating endpoints remain strictly 401 when unauthenticated
    assert client.get("/api/v1/orders/retail/my").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/addresses").status_code == 401

    # Pausing listing excludes it from catalog immediately
    entities["active_listing"].listing_status = "PAUSED"
    db_session.commit()
    assert client.get("/api/v1/catalog/products").json() == []


def test_02_create_retail_order_requires_authentication(app_and_client, db_session):
    app, client = app_and_client
    entities = seed_marketplace_entities(db_session)
    set_authenticated_principal(app, None)

    resp = client.post(
        "/api/v1/orders/retail",
        json={
            "items": [{"seller_listing_id": entities["active_listing"].id, "quantity": 1}],
            "shipping_address": {
                "name": "Priya Sharma",
                "phone": "+91 9811044210",
                "locality": "Residency Road",
                "city": "Jammu",
                "pincode": "180001",
            },
        },
    )
    assert resp.status_code == 401


def test_03_create_retail_order_forbids_client_price_fields(app_and_client, db_session):
    app, client = app_and_client
    entities = seed_marketplace_entities(db_session)
    set_authenticated_principal(app, entities["buyer_principal"])

    resp = client.post(
        "/api/v1/orders/retail",
        json={
            "items": [{"seller_listing_id": entities["active_listing"].id, "quantity": 2}],
            "shipping_address": {
                "name": "Aarav Sharma",
                "phone": "+91 9811044210",
                "locality": "Gandhi Nagar",
                "city": "Jammu",
                "pincode": "180004",
            },
            "total_amount": "1.00",  # Forbidden extra field!
        },
    )
    assert resp.status_code == 422


def test_04_end_to_end_retail_order_to_razorpay_capture_and_my_orders(
    app_and_client, db_session, test_settings
):
    app, client = app_and_client
    entities = seed_marketplace_entities(db_session)
    set_authenticated_principal(app, entities["buyer_principal"])

    # Step 1: Create server-validated retail order from listing_id & qty
    order_resp = client.post(
        "/api/v1/orders/retail",
        json={
            "items": [{"seller_listing_id": entities["active_listing"].id, "quantity": 2}],
            "shipping_address": {
                "name": "Aarav Sharma",
                "phone": "+91 9811044210",
                "locality": "Gandhi Nagar",
                "city": "Jammu",
                "pincode": "180004",
            },
            "payment_method": "RAZORPAY_STANDARD",
        },
    )
    assert order_resp.status_code == 201
    order = order_resp.json()
    assert Decimal(order["total_amount"]) == Decimal("29000.00")
    assert order["fulfilment_status"] == "PENDING_PAYMENT"

    # Step 2: Create Razorpay Standard Checkout order for the newly created order_id
    rzp_resp = client.post(
        "/api/v1/payments/razorpay/create-order",
        json={
            "order_scope": "RETAIL",
            "order_id": order["order_id"],
            "idempotency_key": f"idem-e2e-{order['order_id']}",
        },
    )
    assert rzp_resp.status_code == 200
    rzp = rzp_resp.json()
    assert rzp["amount_paise"] == 2900000

    # Step 3: Verify HMAC signature & capture payment
    sig = compute_checkout_signature(
        stored_razorpay_order_id=rzp["razorpay_order_id"],
        razorpay_payment_id="pay_e2e_storefront_01",
        key_secret=test_settings.razorpay_key_secret.get_secret_value(),
    )
    verify_resp = client.post(
        "/api/v1/payments/razorpay/verify",
        json={
            "payment_id": rzp["payment_id"],
            "razorpay_order_id": rzp["razorpay_order_id"],
            "razorpay_payment_id": "pay_e2e_storefront_01",
            "razorpay_signature": sig,
        },
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["payment_status"] == "CAPTURED"
    assert verify_resp.json()["fulfilment_status"] == "CONFIRMED"

    # Step 4: Confirm buyer sees order in /api/v1/orders/retail/my and other buyer does NOT
    my_orders = client.get("/api/v1/orders/retail/my").json()
    assert len(my_orders) == 1
    assert my_orders[0]["order_id"] == order["order_id"]
    assert my_orders[0]["payment_status"] == "CAPTURED"

    set_authenticated_principal(app, entities["other_principal"])
    assert client.get("/api/v1/orders/retail/my").json() == []


def test_05_cod_retail_order_stays_separate_from_razorpay(app_and_client, db_session):
    app, client = app_and_client
    entities = seed_marketplace_entities(db_session)
    set_authenticated_principal(app, entities["buyer_principal"])

    cod_resp = client.post(
        "/api/v1/orders/retail",
        json={
            "items": [{"seller_listing_id": entities["active_listing"].id, "quantity": 1}],
            "shipping_address": {
                "name": "Aarav Sharma",
                "phone": "+91 9811044210",
                "locality": "Channi Himmat",
                "city": "Jammu",
                "pincode": "180015",
            },
            "payment_method": "COD",
        },
    )
    assert cod_resp.status_code == 201
    cod_order = cod_resp.json()
    assert cod_order["payment_method"] == "COD"
    assert cod_order["payment_status"] == "COD_PENDING"

    # Attempting to open Razorpay Checkout for a COD order MUST fail cleanly
    rzp_try = client.post(
        "/api/v1/payments/razorpay/create-order",
        json={
            "order_scope": "RETAIL",
            "order_id": cod_order["order_id"],
            "idempotency_key": "idem-cod-e2e",
        },
    )
    assert rzp_try.status_code == 400


def test_06_inactive_listing_blocked_during_retail_order_creation(app_and_client, db_session):
    app, client = app_and_client
    entities = seed_marketplace_entities(db_session)
    entities["active_listing"].listing_status = "PAUSED"
    db_session.commit()
    set_authenticated_principal(app, entities["buyer_principal"])

    resp = client.post(
        "/api/v1/orders/retail",
        json={
            "items": [{"seller_listing_id": entities["active_listing"].id, "quantity": 1}],
            "shipping_address": {
                "name": "Aarav Sharma",
                "phone": "+91 9811044210",
                "locality": "Residency Road",
                "city": "Jammu",
                "pincode": "180001",
            },
        },
    )
    assert resp.status_code == 409


def test_07_readyz_reports_truthful_database_connectivity(app_and_client):
    _app, client = app_and_client
    resp = client.get("/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["database"] == "connected"
    assert body["database_dialect"] == "sqlite"


def test_08_uuid_product_and_artisan_lookup_endpoints(app_and_client, db_session):
    _app, client = app_and_client
    entities = seed_marketplace_entities(db_session)

    listing_uuid = entities["active_listing"].id
    seller_uuid = entities["seller_profile"].id

    # Product lookup by unique listing UUID (query param & path)
    prod_q_resp = client.get(f"/api/v1/catalog/product?id={listing_uuid}")
    assert prod_q_resp.status_code == 200
    assert prod_q_resp.json()["listing_id"] == listing_uuid

    prod_resp = client.get(f"/api/v1/catalog/products/{listing_uuid}")
    assert prod_resp.status_code == 200
    assert prod_resp.json()["listing_id"] == listing_uuid
    assert prod_resp.json()["seller_profile_id"] == seller_uuid

    # Artisan lookup by unique seller_profile_id UUID via query param (?id=<uuid>) and path
    art_q_resp = client.get(f"/api/v1/artisans/detail?id={seller_uuid}")
    assert art_q_resp.status_code == 200
    assert art_q_resp.json()["seller_profile_id"] == seller_uuid
    assert len(art_q_resp.json()["listings"]) == 1

    art_p_resp = client.get(f"/api/v1/artisans/{seller_uuid}")
    assert art_p_resp.status_code == 200
    assert art_p_resp.json()["seller_profile_id"] == seller_uuid

    # Invalid / malformed identifiers return 422; unknown UUIDs return 404
    assert client.get("/api/v1/artisans/detail?id=../../etc/passwd").status_code == 422
    assert client.get("/api/v1/catalog/products/not_a_valid_id!").status_code == 422
    assert client.get("/api/v1/artisans/detail?id=00000000-0000-4000-8000-000000000999").status_code == 404
    assert client.get("/api/v1/catalog/products/00000000-0000-4000-8000-000000000999").status_code == 404


def test_09_unverified_or_suspended_artisan_uuid_is_blocked_and_audited(app_and_client, db_session):
    from app.models.core_models import AuditLog

    _app, client = app_and_client
    entities = seed_marketplace_entities(db_session)
    seller = entities["seller_profile"]
    seller.verification_status = "UNDER_REVIEW"
    db_session.commit()

    resp = client.get(f"/api/v1/artisans/detail?id={seller.id}")
    assert resp.status_code == 404

    audit_rows = db_session.query(AuditLog).filter(
        AuditLog.action == "ARTISAN_ENDPOINT_BLOCKED_UNVERIFIED_ID"
    ).all()
    assert len(audit_rows) == 1
    assert audit_rows[0].target_id == seller.id


def test_10_full_96_products_and_53_artisans_seeder_hydrates_images_and_uuids(app_and_client, db_session):
    from scripts.seed_real_artisans import seed_artisans_and_catalog

    _app, client = app_and_client
    stats = seed_artisans_and_catalog(session_override=db_session)
    assert stats["total_artisans"] == 53
    assert stats["total_products"] == 96

    products = client.get("/api/v1/catalog/products?limit=200").json()
    assert len(products) == 96
    listing_uuids = {p["listing_id"] for p in products}
    assert len(listing_uuids) == 96
    assert all(p["image_url"] and p["image_url"].startswith("assets/products/") for p in products)

    artisans = client.get("/api/v1/artisans").json()
    assert len(artisans) == 53
    artisan_uuids = {a["seller_profile_id"] for a in artisans}
    assert len(artisan_uuids) == 53
    showcase = [a for a in artisans if a["is_featured_showcase"]]
    assert len(showcase) == 6
    assert all(a["portrait_url"].startswith("img/artisans/artisan-0") for a in showcase)


def test_11_seller_studio_asigs_guardrails_to_admin_approval_and_live_catalog(app_and_client, db_session):
    app, client = app_and_client
    entities = seed_marketplace_entities(db_session)
    set_authenticated_principal(app, entities["seller_principal"])

    # 1. Spoofing GI_VERIFIED is blocked by ASIGS Layer 4
    blocked_gi = client.post(
        "/api/v1/seller/studio/validate",
        json={
            "title": "Handwoven Saffron Kani Shawl",
            "guild": "pashmina",
            "description": "Authentic handwoven Kani piece from Srinagar workshop.",
            "selling_price": "24000",
            "compare_at_mrp": "28000",
            "requested_gi_status": "GI_VERIFIED",
        },
    )
    assert blocked_gi.status_code == 200
    assert blocked_gi.json()["outcome"] == "BLOCK"
    assert "PROD_SELLER_CANNOT_SELF_VERIFY_GI" in blocked_gi.json()["triggered_rule_codes"]

    # 2. Price > MRP is blocked on publish (422)
    blocked_price = client.post(
        "/api/v1/seller/studio/listings",
        json={
            "title": "Walnut Jewelry Box",
            "guild": "walnut",
            "selling_price": "9500",
            "compare_at_mrp": "5000",
        },
    )
    assert blocked_price.status_code == 422

    # 3. Extreme discount anomaly triggers WARNING + creates PENDING_APPROVAL listing
    flagged = client.post(
        "/api/v1/seller/studio/listings",
        json={
            "title": "Zadibal Gold-Leaf Papier Mache Vase",
            "guild": "papier-mache",
            "description": "Hand-painted floral vase from Zadibal workshop.",
            "selling_price": "500",
            "compare_at_mrp": "12000",
            "stock_quantity": 3,
        },
    )
    assert flagged.status_code == 201
    fbody = flagged.json()
    assert fbody["outcome"] == "WARNING"
    assert "COMM_UNUSUAL_PRICE_OUTLIER" in fbody["triggered_rule_codes"]
    assert fbody["business_status"] == "PENDING_APPROVAL"
    listing_id = fbody["created_resource_id"]
    assert listing_id is not None

    # Seller sees their own pending listing in Seller Studio
    mine = client.get("/api/v1/seller/studio/listings")
    assert mine.status_code == 200
    assert any(item["listing_id"] == listing_id and item["listing_status"] == "PENDING_APPROVAL" for item in mine.json())

    # 4. Duplicate submission of existing product triggers REVIEW_REQUIRED -> creates GuardrailCase
    dup_payload = {
        "product_id": entities["product"].id,
        "product_variant_id": entities["variant"].id,
        "seller_sku": "HL-DUP-STUDIO-01",
        "listing_title": "Duplicate Studio Shawl Submission",
        "selling_price": "22000",
        "compare_at_mrp": "26000",
        "currency_code": "INR",
    }
    first_sub = client.post("/api/v1/seller/listings", json=dup_payload)
    assert first_sub.status_code == 201
    dup_payload["seller_sku"] = "HL-DUP-STUDIO-02"
    second_sub = client.post("/api/v1/seller/listings", json=dup_payload)
    assert second_sub.status_code == 201
    assert second_sub.json()["outcome"] == "REVIEW_REQUIRED"
    case_id = second_sub.json()["review_case_id"]
    dup_listing_id = second_sub.json()["created_resource_id"]
    assert case_id is not None

    # 5. Admin approves both the GuardrailCase AND the Studio listing -> both live in public catalog!
    set_authenticated_principal(app, entities["admin_principal"])
    cases = client.get("/api/v1/admin/guardrail/cases")
    assert cases.status_code == 200
    assert any(c["id"] == case_id for c in cases.json())

    decided = client.post(
        f"/api/v1/admin/guardrail/cases/{case_id}/decision",
        json={
            "decision": "APPROVE",
            "reason": "Workshop verified legitimate second batch of shawl listing.",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["case_status"] == "APPROVED"

    mod = client.post(
        f"/api/v1/admin/listings/{listing_id}/moderate",
        json={"listing_status": "ACTIVE"},
    )
    assert mod.status_code == 200
    assert mod.json()["listing_status"] == "ACTIVE"

    catalog = client.get("/api/v1/catalog/products")
    assert catalog.status_code == 200
    catalog_ids = {p["listing_id"] for p in catalog.json()}
    assert listing_id in catalog_ids
    assert dup_listing_id in catalog_ids


def test_12_retail_order_razorpay_checkout_to_admin_refund_end_to_end(app_and_client, db_session, test_settings):
    import hashlib
    import hmac
    from app.modules.payments.router import get_razorpay_gateway
    from tests.conftest import FakeRazorpayGateway

    app, client = app_and_client
    fake_rzp = FakeRazorpayGateway()
    app.dependency_overrides[get_razorpay_gateway] = lambda: fake_rzp

    entities = seed_marketplace_entities(db_session)
    set_authenticated_principal(app, entities["buyer_principal"])

    # 1. Create retail order
    order_resp = client.post(
        "/api/v1/orders/retail",
        json={
            "items": [{"seller_listing_id": entities["active_listing"].id, "quantity": 1}],
            "shipping_address": {
                "name": "Meera Kaul",
                "phone": "+91 9811044211",
                "locality": "Lal Chowk",
                "city": "Srinagar",
                "pincode": "190001",
            },
            "payment_method": "RAZORPAY_STANDARD",
        },
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["order_id"]

    # 2. Create Razorpay order
    rzp_order = client.post(
        "/api/v1/payments/razorpay/create-order",
        json={
            "order_scope": "RETAIL",
            "order_id": order_id,
            "idempotency_key": "idem-studio-rzp-order-01",
        },
    )
    assert rzp_order.status_code == 200
    payment_id = rzp_order.json()["payment_id"]
    provider_order_id = rzp_order.json()["razorpay_order_id"]

    # 3. Verify HMAC signature against captured payment
    provider_payment_id = "pay_studio_e2e_001"
    sig = hmac.new(
        test_settings.razorpay_key_secret.get_secret_value().encode("utf-8"),
        f"{provider_order_id}|{provider_payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    verified = client.post(
        "/api/v1/payments/razorpay/verify",
        json={
            "payment_id": payment_id,
            "razorpay_order_id": provider_order_id,
            "razorpay_payment_id": provider_payment_id,
            "razorpay_signature": sig,
        },
    )
    assert verified.status_code == 200
    assert verified.json()["payment_status"] == "CAPTURED"

    # 4. Admin views captured payment and issues full refund
    set_authenticated_principal(app, entities["admin_principal"])
    admin_payments = client.get("/api/v1/admin/payments")
    assert admin_payments.status_code == 200
    assert any(p["id"] == payment_id and p["payment_status"] == "CAPTURED" for p in admin_payments.json())

    refund_resp = client.post(
        f"/api/v1/payments/{payment_id}/refund",
        json={
            "refund_type": "FULL",
            "reason": "Buyer requested order cancellation prior to workshop dispatch.",
            "idempotency_key": "idem-studio-refund-01",
        },
    )
    assert refund_resp.status_code == 200
    assert refund_resp.json()["payment_status"] == "REFUNDED"

    admin_refunds = client.get("/api/v1/admin/refunds")
    assert admin_refunds.status_code == 200
    assert any(r["payment_id"] == payment_id for r in admin_refunds.json())

    app.dependency_overrides.pop(get_razorpay_gateway, None)


def test_13_product_reviews_persistence_verified_purchase_and_guardrails(app_and_client, db_session):
    from sqlalchemy import select

    from app.models.core_models import ProductReview, SellerVerificationApplication
    from tests.conftest import create_user_with_roles

    app, client = app_and_client
    entities = seed_marketplace_entities(db_session)
    listing = entities["active_listing"]
    seller = entities["seller_profile"]

    # Seed an archived collector quote in artisan verification metadata
    ver_app = SellerVerificationApplication(
        seller_profile_id=seller.id,
        application_number="HL-VER-REV-TEST-01",
        verification_path="GI",
        application_status="APPROVED",
        submitted_metadata={
            "reviews": [
                {
                    "author": "Kavita Kapoor",
                    "city": "Mumbai",
                    "stars": 5,
                    "text": "Authentic Kani border work — museum-grade Kashmiri pashmina.",
                }
            ]
        },
    )
    db_session.add(ver_app)
    db_session.commit()

    # 1. Guest can view public reviews + archived quotes, but cannot post
    set_authenticated_principal(app, None)
    pub_resp = client.get(f"/api/v1/catalog/products/{listing.id}/reviews")
    assert pub_resp.status_code == 200
    pub_data = pub_resp.json()
    assert pub_data["product_id"] == entities["product"].id
    assert len(pub_data["reviews"]) == 1
    assert pub_data["reviews"][0]["author_name"] == "Kavita Kapoor"
    assert pub_data["reviews"][0]["source"] == "heritage_archive"

    guest_post = client.post(
        f"/api/v1/catalog/products/{listing.id}/reviews",
        json={"rating": 5, "review_body": "Attempting unauthenticated review."},
    )
    assert guest_post.status_code == 401

    # 2. Signed-in buyer blocked if content violates ASIGS vulgarity/script guardrails
    set_authenticated_principal(app, entities["buyer_principal"])
    bad_xss = client.post(
        f"/api/v1/catalog/products/{listing.id}/reviews",
        json={"rating": 4, "review_body": "<script>alert(1)</script> nice weave"},
    )
    assert bad_xss.status_code == 422

    bad_vulgar = client.post(
        f"/api/v1/catalog/products/{listing.id}/reviews",
        json={"rating": 1, "review_body": "Total bullshit madarchod fake item"},
    )
    assert bad_vulgar.status_code == 422

    # 3. Signed-in buyer with CONFIRMED/COD order gets automatic Verified Purchase badge
    cod_order = client.post(
        "/api/v1/orders/retail",
        json={
            "items": [{"seller_listing_id": listing.id, "quantity": 1}],
            "shipping_address": {
                "name": "Meera Sharma",
                "phone": "+919876500112",
                "locality": "Jor Bagh",
                "city": "New Delhi",
                "state": "Delhi",
                "pincode": "110003",
            },
            "payment_method": "COD",
        },
    )
    assert cod_order.status_code == 201

    post_verified = client.post(
        f"/api/v1/catalog/products/{listing.id}/reviews",
        json={
            "rating": 5,
            "title": "Heirloom Kani border craftsmanship",
            "review_body": "Soft handspun pashmina with crisp GI provenance tag.",
            "author_city": "New Delhi",
        },
    )
    assert post_verified.status_code == 201
    created_rev = post_verified.json()
    assert created_rev["is_verified_purchase"] is True
    assert created_rev["rating"] == 5
    assert created_rev["author_city"] == "New Delhi"

    # 4. Separate buyer without order can still publish a Collector Review (is_verified_purchase=False)
    _other_user, other_principal = create_user_with_roles(
        db_session,
        email="collector.no.order@example.com",
        full_name="Rohan Verma",
        roles=["CUSTOMER"],
    )
    set_authenticated_principal(app, other_principal)
    post_collector = client.post(
        f"/api/v1/catalog/products/{listing.id}/reviews",
        json={
            "rating": 4,
            "title": "Saw it at gallery preview",
            "review_body": "Beautiful natural walnut dye palette and fine finish.",
            "author_city": "Bengaluru",
        },
    )
    assert post_collector.status_code == 201
    assert post_collector.json()["is_verified_purchase"] is False

    # 5. GET reviews reflects both DB reviews newest-first + breakdown + persisted rows
    summary_after = client.get(f"/api/v1/catalog/products/{listing.id}/reviews")
    assert summary_after.status_code == 200
    sdata = summary_after.json()
    assert sdata["total_reviews"] >= 3
    assert sdata["reviews"][0]["author_name"] == "Rohan Verma"
    assert sdata["reviews"][1]["is_verified_purchase"] is True
    db_count = len(db_session.scalars(select(ProductReview).where(ProductReview.product_id == entities["product"].id)).all())
    assert db_count == 2


