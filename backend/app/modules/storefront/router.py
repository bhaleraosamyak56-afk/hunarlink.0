"""Storefront router: DB-backed catalog, verified artisans (UUID + slug) & retail orders.

Security rules:
  - Public read-only endpoints return ONLY verified/active artisans (`User.account_status == 'ACTIVE'`,
    active `DIRECT_SELLER` role assignment, `SellerProfile.profile_status == 'ACTIVE'`,
    `SellerProfile.verification_status == 'APPROVED'`) and active/approved products/listings.
  - Every product and artisan lookup supports unique database UUIDs (`?id=<uuid>` / `/{uuid}`)
    with strict regex validation, sliding-window rate limiting, and `AuditLog` tracking when
    blocked/unverified records are probed.
  - All order/account mutations strictly require an authenticated `ACTIVE` Clerk principal.
"""
from __future__ import annotations

import re
import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit_log
from app.core.auth import AuthenticatedPrincipal, get_current_principal, require_admin_permission
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import SlidingWindowRateLimiter
from app.models.base import new_uuid, utcnow
from app.models.core_models import (
    AdminCredential,
    AuditLog,
    Category,
    PlatformRole,
    Product,
    ProductImage,
    ProductVariant,
    RetailOrder,
    RetailOrderItem,
    SellerDocument,
    SellerFulfilmentGroup,
    SellerProductListing,
    SellerProfile,
    SellerVerificationApplication,
    User,
    UserLoginLog,
    UserRoleAssignment,
)
from app.models.guardrail_models import FileSecurityScan
from app.modules.auth.deletion import execute_user_deletion
from app.modules.auth.schemas import AdminDeleteUserRequest, DeleteAccountResponse
from app.modules.guardrails import repository as guardrail_repo, service as guardrail_service
from app.modules.guardrails.schemas import (
    GuardrailOutcome,
    GuardrailResponse,
    SellerListingInput,
)
from app.modules.storefront.schemas import (
    ArtisanDetailResponse,
    ArtisanReviewItem,
    ArtisanSummaryItem,
    CatalogProductItem,
    CreateRetailOrderRequest,
    RetailOrderItemSummary,
    RetailOrderSummaryResponse,
    SellerStudioListingInput,
)

router = APIRouter(tags=["Storefront, Artisans & Retail Orders"])

# Rate limiters for public lookup endpoints against UUID/slug enumeration
artisan_lookup_rate_limiter = SlidingWindowRateLimiter(max_requests=120, window_seconds=60)
product_lookup_rate_limiter = SlidingWindowRateLimiter(max_requests=180, window_seconds=60)

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,178}[a-z0-9])?$")


def _check_lookup_rate_limit(limiter: SlidingWindowRateLimiter, request: Request, response: Response) -> None:
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = limiter.allow(client_ip)
    if not allowed:
        response.headers["Retry-After"] = str(retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many lookup requests. Please slow down.",
        )


def _validate_identifier(raw: str, label: str = "Identifier") -> tuple[str, bool]:
    """Validate either a canonical 36-char UUID or a clean lowercase slug."""
    cleaned = (raw or "").strip()
    if _UUID_RE.match(cleaned):
        return cleaned.lower(), True
    low = cleaned.lower()
    if _SLUG_RE.match(low):
        return low, False
    raise HTTPException(
        status_code=422,
        detail=f"Invalid {label} format.",
    )


def _verified_seller_conditions():
    return (
        User.account_status == "ACTIVE",
        SellerProfile.profile_status == "ACTIVE",
        SellerProfile.verification_status == "APPROVED",
    )


def _has_active_direct_seller_role(db: Session, user_id: str) -> bool:
    hit = db.scalar(
        select(UserRoleAssignment.id)
        .join(PlatformRole, PlatformRole.id == UserRoleAssignment.platform_role_id)
        .where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.assignment_status == "ACTIVE",
            PlatformRole.code == "DIRECT_SELLER",
            PlatformRole.is_active == True,  # noqa: E712
        )
        .limit(1)
    )
    return hit is not None


def _load_product_images_map(db: Session, product_ids: list[str]) -> dict[str, list[str]]:
    if not product_ids:
        return {}
    rows = db.execute(
        select(ProductImage.product_id, ProductImage.storage_key)
        .where(ProductImage.product_id.in_(product_ids))
        .order_by(ProductImage.is_primary.desc(), ProductImage.sort_order.asc())
    ).all()
    mapping: dict[str, list[str]] = defaultdict(list)
    for pid, key in rows:
        if key and key not in mapping[pid]:
            mapping[pid].append(key)
    return mapping


def _load_seller_portraits_map(db: Session, seller_ids: list[str]) -> dict[str, str]:
    if not seller_ids:
        return {}
    rows = db.execute(
        select(SellerDocument.seller_profile_id, SellerDocument.storage_key)
        .where(
            SellerDocument.seller_profile_id.in_(seller_ids),
            SellerDocument.document_type == "ARTISAN_PORTRAIT",
            SellerDocument.verification_status == "ACCEPTED",
        )
        .order_by(SellerDocument.created_at.desc())
    ).all()
    mapping: dict[str, str] = {}
    for sid, key in rows:
        if sid not in mapping and key:
            mapping[sid] = key
    return mapping


def _load_seller_metadata_map(db: Session, seller_ids: list[str]) -> dict[str, dict]:
    if not seller_ids:
        return {}
    rows = db.execute(
        select(
            SellerVerificationApplication.seller_profile_id,
            SellerVerificationApplication.submitted_metadata,
        )
        .where(
            SellerVerificationApplication.seller_profile_id.in_(seller_ids),
            SellerVerificationApplication.application_status == "APPROVED",
        )
        .order_by(SellerVerificationApplication.created_at.desc())
    ).all()
    mapping: dict[str, dict] = {}
    for sid, meta in rows:
        if sid not in mapping and isinstance(meta, dict):
            mapping[sid] = meta
    return mapping


def _serialize_catalog_row(
    listing: SellerProductListing,
    product: Product,
    category: Category,
    seller: SellerProfile,
    artisan_user: User | None,
    *,
    images: list[str] | None = None,
    artisan_portrait_url: str | None = None,
) -> CatalogProductItem:
    artisan_name = (
        (artisan_user.display_name or f"{artisan_user.first_name} {artisan_user.last_name or ''}".strip())
        if artisan_user is not None
        else seller.store_name
    )
    attrs = product.attributes_json if isinstance(product.attributes_json, dict) else {}
    img_list = list(images or [])
    attr_img = attrs.get("image")
    if isinstance(attr_img, str) and attr_img and attr_img not in img_list:
        img_list.insert(0, attr_img)
    primary_img = img_list[0] if img_list else None

    orig_price_raw = attrs.get("original_price")
    original_market_price = (
        Decimal(str(orig_price_raw))
        if orig_price_raw is not None
        else listing.compare_at_mrp
    )

    return CatalogProductItem(
        listing_id=listing.id,
        product_id=product.id,
        product_variant_id=listing.product_variant_id,
        seller_profile_id=seller.id,
        seller_sku=listing.seller_sku,
        product_slug=product.slug,
        legacy_code=attrs.get("legacy_code"),
        title=listing.listing_title,
        description=product.description or "",
        category_slug=category.slug,
        category_name=category.name,
        guild=attrs.get("guild") or category.slug,
        technique=product.craft_technique or attrs.get("technique"),
        store_name=seller.store_name,
        artisan_name=artisan_name,
        artisan_slug=seller.store_slug,
        artisan_portrait_url=artisan_portrait_url,
        workshop_district=product.origin_district or seller.workshop_district,
        craft_specialty=seller.craft_specialty,
        verification_path=seller.verification_path,
        verification_status=seller.verification_status,
        claimed_gi_code=attrs.get("gi_id") or seller.claimed_gi_authorized_user_no,
        gi_level=int(attrs.get("gi_level") or (3 if product.gi_status == "GI_VERIFIED" else 2)),
        purity_metric=product.material_composition or attrs.get("purity_metric"),
        loom_hours=int(attrs["loom_hours"]) if attrs.get("loom_hours") is not None else None,
        dimensions=attrs.get("dimensions"),
        rating=float(attrs.get("rating") or 4.9),
        review_count=int(attrs.get("review_count") or 0),
        image_url=primary_img,
        gallery_images=img_list,
        selling_price=listing.selling_price,
        compare_at_mrp=listing.compare_at_mrp,
        original_market_price=original_market_price,
        currency_code=listing.currency_code,
        min_order_qty=listing.min_order_qty,
        max_order_qty=listing.max_order_qty,
        gi_status=product.gi_status,
    )


def _serialize_artisan_summary(
    seller: SellerProfile,
    artisan_user: User,
    listing_rows: list[tuple[SellerProductListing, Category]],
    *,
    portrait_url: str | None = None,
    meta: dict | None = None,
) -> ArtisanSummaryItem:
    prices = [Decimal(l.selling_price) for l, _ in listing_rows]
    cats = sorted({c.name for _, c in listing_rows})
    name = artisan_user.display_name or f"{artisan_user.first_name} {artisan_user.last_name or ''}".strip()
    meta_dict = meta or {}

    raw_reviews = meta_dict.get("reviews") if isinstance(meta_dict.get("reviews"), list) else []
    parsed_reviews = [
        ArtisanReviewItem(
            author=str(r.get("author") or "Verified Collector"),
            city=str(r.get("city") or "India"),
            stars=int(r.get("stars") or 5),
            text=str(r.get("text") or ""),
        )
        for r in raw_reviews
        if isinstance(r, dict) and r.get("text")
    ]

    resolved_portrait = portrait_url or meta_dict.get("portrait_url")
    avg_rating = (
        Decimal(str(seller.average_rating))
        if seller.average_rating and Decimal(str(seller.average_rating)) > Decimal("0.00")
        else Decimal("4.90")
    )

    return ArtisanSummaryItem(
        seller_profile_id=seller.id,
        slug=seller.store_slug,
        name=name,
        store_name=seller.store_name,
        craft_specialty=seller.craft_specialty,
        workshop_district=seller.workshop_district,
        verification_path=seller.verification_path,
        verification_status=seller.verification_status,
        profile_status=seller.profile_status,
        claimed_gi_code=seller.claimed_gi_authorized_user_no,
        portrait_url=resolved_portrait,
        bio=seller.bio or meta_dict.get("bio"),
        credential=meta_dict.get("credential"),
        since_year=int(meta_dict["since"]) if meta_dict.get("since") is not None else None,
        is_featured_showcase=bool(meta_dict.get("featured_showcase", False)),
        featured_order=int(meta_dict.get("featured_order", 999)),
        average_rating=avg_rating,
        total_reviews=int(seller.total_reviews or len(parsed_reviews)),
        reviews=parsed_reviews,
        listing_count=len(listing_rows),
        starting_price=min(prices) if prices else None,
        categories=cats,
    )


@router.get("/catalog/products", response_model=list[CatalogProductItem])
def list_active_catalog_products(
    category_slug: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[CatalogProductItem]:
    """Return active, approved marketplace listings from the DB for public browsing."""
    safe_limit = max(1, min(limit, 250))
    stmt = (
        select(SellerProductListing, Product, Category, SellerProfile, User)
        .join(Product, Product.id == SellerProductListing.product_id)
        .join(Category, Category.id == Product.category_id)
        .join(SellerProfile, SellerProfile.id == SellerProductListing.seller_profile_id)
        .join(User, User.id == SellerProfile.user_id)
        .where(
            SellerProductListing.listing_status == "ACTIVE",
            Product.is_active == True,  # noqa: E712
            Product.approval_status == "APPROVED",
            *_verified_seller_conditions(),
        )
        .order_by(Product.sku_root.asc(), SellerProductListing.created_at.desc())
        .limit(safe_limit)
    )
    if category_slug:
        stmt = stmt.where(Category.slug == category_slug.strip())

    rows = [
        row
        for row in db.execute(stmt).all()
        if _has_active_direct_seller_role(db, row[4].id)
    ]

    product_ids = list({product.id for _, product, _, _, _ in rows})
    seller_ids = list({seller.id for _, _, _, seller, _ in rows})
    images_map = _load_product_images_map(db, product_ids)
    portraits_map = _load_seller_portraits_map(db, seller_ids)
    meta_map = _load_seller_metadata_map(db, seller_ids)

    return [
        _serialize_catalog_row(
            listing,
            product,
            category,
            seller,
            artisan_user,
            images=images_map.get(product.id),
            artisan_portrait_url=portraits_map.get(seller.id) or (meta_map.get(seller.id) or {}).get("portrait_url"),
        )
        for listing, product, category, seller, artisan_user in rows
    ]


@router.get("/catalog/product", response_model=CatalogProductItem)
def get_active_catalog_product_by_query_id(
    id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> CatalogProductItem:
    """Return a single active, approved product listing via `?id=<uuid>`."""
    return get_active_catalog_product(id, request, response, db)


@router.get("/catalog/products/{identifier}", response_model=CatalogProductItem)
def get_active_catalog_product(
    identifier: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> CatalogProductItem:
    """Return a single active, approved product listing by its unique DB UUID (or slug)."""
    _check_lookup_rate_limit(product_lookup_rate_limiter, request, response)
    clean_id, is_uuid = _validate_identifier(identifier, label="product ID")

    stmt = (
        select(SellerProductListing, Product, Category, SellerProfile, User)
        .join(Product, Product.id == SellerProductListing.product_id)
        .join(Category, Category.id == Product.category_id)
        .join(SellerProfile, SellerProfile.id == SellerProductListing.seller_profile_id)
        .join(User, User.id == SellerProfile.user_id)
        .where(
            SellerProductListing.listing_status == "ACTIVE",
            Product.is_active == True,  # noqa: E712
            Product.approval_status == "APPROVED",
            *_verified_seller_conditions(),
        )
    )
    if is_uuid:
        stmt = stmt.where(
            or_(
                SellerProductListing.id == clean_id,
                Product.id == clean_id,
            )
        )
    else:
        stmt = stmt.where(
            or_(
                Product.slug == clean_id,
                Product.sku_root == clean_id.upper(),
                SellerProductListing.seller_sku == clean_id.upper(),
            )
        )

    row = db.execute(stmt).first()
    if row is None or not _has_active_direct_seller_role(db, row[4].id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Craft listing not found.")

    listing, product, category, seller, artisan_user = row
    images_map = _load_product_images_map(db, [product.id])
    portraits_map = _load_seller_portraits_map(db, [seller.id])
    meta_map = _load_seller_metadata_map(db, [seller.id])

    return _serialize_catalog_row(
        listing,
        product,
        category,
        seller,
        artisan_user,
        images=images_map.get(product.id),
        artisan_portrait_url=portraits_map.get(seller.id) or (meta_map.get(seller.id) or {}).get("portrait_url"),
    )


@router.get("/artisans", response_model=list[ArtisanSummaryItem])
def list_verified_artisans(
    db: Session = Depends(get_db),
) -> list[ArtisanSummaryItem]:
    """Return verified/active artisans strictly from the database for public browsing."""
    sellers = [
        (seller, artisan_user)
        for seller, artisan_user in db.execute(
            select(SellerProfile, User)
            .join(User, User.id == SellerProfile.user_id)
            .where(*_verified_seller_conditions())
            .order_by(SellerProfile.created_at.asc())
        ).all()
        if _has_active_direct_seller_role(db, artisan_user.id)
    ]

    seller_ids = [s.id for s, _ in sellers]
    portraits_map = _load_seller_portraits_map(db, seller_ids)
    meta_map = _load_seller_metadata_map(db, seller_ids)

    results: list[ArtisanSummaryItem] = []
    for seller, artisan_user in sellers:
        listing_rows = db.execute(
            select(SellerProductListing, Category)
            .join(Product, Product.id == SellerProductListing.product_id)
            .join(Category, Category.id == Product.category_id)
            .where(
                SellerProductListing.seller_profile_id == seller.id,
                SellerProductListing.listing_status == "ACTIVE",
                Product.is_active == True,  # noqa: E712
                Product.approval_status == "APPROVED",
            )
        ).all()
        results.append(
            _serialize_artisan_summary(
                seller,
                artisan_user,
                listing_rows,
                portrait_url=portraits_map.get(seller.id),
                meta=meta_map.get(seller.id),
            )
        )

    results.sort(key=lambda a: (a.featured_order, a.name.lower()))
    return results


def _resolve_verified_artisan_detail(
    identifier: str,
    request: Request,
    response: Response,
    db: Session,
) -> ArtisanDetailResponse:
    _check_lookup_rate_limit(artisan_lookup_rate_limiter, request, response)
    clean_id, is_uuid = _validate_identifier(identifier, label="artisan ID")

    probe_cond = SellerProfile.id == clean_id if is_uuid else SellerProfile.store_slug == clean_id
    raw_seller_row = db.execute(
        select(SellerProfile, User)
        .join(User, User.id == SellerProfile.user_id)
        .where(probe_cond)
    ).first()

    if raw_seller_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artisan not found.")

    seller, artisan_user = raw_seller_row
    is_verified = (
        artisan_user.account_status == "ACTIVE"
        and seller.profile_status == "ACTIVE"
        and seller.verification_status == "APPROVED"
        and _has_active_direct_seller_role(db, artisan_user.id)
    )
    if not is_verified:
        corr_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
        db.add(
            AuditLog(
                id=new_uuid(),
                actor_user_id=None,
                actor_role="PUBLIC",
                action="ARTISAN_ENDPOINT_BLOCKED_UNVERIFIED_ID",
                target_type="seller_profile",
                target_id=seller.id,
                reason=f"Blocked public access to unverified/inactive artisan ({clean_id}).",
                correlation_id=corr_id,
                ip_address=request.client.host if request.client else None,
            )
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artisan not found.")

    listing_rows = db.execute(
        select(SellerProductListing, Product, Category)
        .join(Product, Product.id == SellerProductListing.product_id)
        .join(Category, Category.id == Product.category_id)
        .where(
            SellerProductListing.seller_profile_id == seller.id,
            SellerProductListing.listing_status == "ACTIVE",
            Product.is_active == True,  # noqa: E712
            Product.approval_status == "APPROVED",
        )
        .order_by(Product.sku_root.asc(), SellerProductListing.created_at.desc())
    ).all()

    product_ids = [prod.id for _, prod, _ in listing_rows]
    images_map = _load_product_images_map(db, product_ids)
    portraits_map = _load_seller_portraits_map(db, [seller.id])
    meta_map = _load_seller_metadata_map(db, [seller.id])
    portrait_url = portraits_map.get(seller.id) or (meta_map.get(seller.id) or {}).get("portrait_url")

    serialized_listings = [
        _serialize_catalog_row(
            listing,
            product,
            category,
            seller,
            artisan_user,
            images=images_map.get(product.id),
            artisan_portrait_url=portrait_url,
        )
        for listing, product, category in listing_rows
    ]
    summary = _serialize_artisan_summary(
        seller,
        artisan_user,
        [(l, c) for l, _, c in listing_rows],
        portrait_url=portraits_map.get(seller.id),
        meta=meta_map.get(seller.id),
    )

    return ArtisanDetailResponse(
        **summary.model_dump(),
        listings=serialized_listings,
    )


@router.get("/artisans/detail", response_model=ArtisanDetailResponse)
def get_verified_artisan_by_query_id(
    id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> ArtisanDetailResponse:
    """Return a single verified artisan + DB listings via `?id=<uuid>`."""
    return _resolve_verified_artisan_detail(id, request, response, db)


@router.get("/artisans/{identifier}", response_model=ArtisanDetailResponse)
def get_verified_artisan_by_id_or_slug(
    identifier: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> ArtisanDetailResponse:
    """Return a single verified artisan + DB listings by unique DB UUID or store slug."""
    return _resolve_verified_artisan_detail(identifier, request, response, db)


def _serialize_order(order: RetailOrder, items: list[RetailOrderItem]) -> RetailOrderSummaryResponse:
    snap = order.shipping_address_snapshot_json if isinstance(order.shipping_address_snapshot_json, dict) else {}
    return RetailOrderSummaryResponse(
        order_id=order.id,
        order_number=order.order_number,
        order_scope="RETAIL",
        payment_method=order.payment_method,
        payment_label=snap.get("payment_label"),
        payment_status=order.payment_status,
        fulfilment_status=order.fulfilment_status,
        currency_code=order.currency_code,
        subtotal_amount=order.subtotal_amount,
        discount_amount=order.discount_amount,
        tax_amount=order.tax_amount,
        shipping_fee=order.shipping_fee,
        total_amount=order.total_amount,
        item_count=sum(i.quantity for i in items),
        shipping_address=snap,
        items=[
            RetailOrderItemSummary(
                product_id=i.product_id,
                seller_listing_id=i.seller_listing_id,
                title=i.product_name_snapshot,
                sku=i.sku_snapshot,
                gi_status=i.gi_status_snapshot,
                quantity=i.quantity,
                unit_price=i.unit_price_snapshot,
                line_total=i.line_total_amount,
            )
            for i in items
        ],
        created_at=order.created_at,
    )


@router.post(
    "/orders/retail",
    response_model=RetailOrderSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_retail_order_from_cart(
    payload: CreateRetailOrderRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> RetailOrderSummaryResponse:
    """Create a server-validated RetailOrder whose totals come strictly from DB prices."""
    buyer = db.scalar(select(User).where(User.id == principal.user_id))
    if buyer is None or buyer.account_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active customer account required to place orders.",
        )

    grouped_lines: dict[str, list[tuple[SellerProductListing, Product, ProductVariant, int, Decimal]]] = defaultdict(list)
    order_subtotal = Decimal("0.00")

    for req_item in payload.items:
        listing = db.scalar(
            select(SellerProductListing).where(SellerProductListing.id == req_item.seller_listing_id)
        )
        if listing is None or listing.listing_status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Listing '{req_item.seller_listing_id}' is unavailable or inactive.",
            )
        if listing.currency_code.upper() != "INR":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only INR retail listings are supported.",
            )

        seller = db.scalar(select(SellerProfile).where(SellerProfile.id == listing.seller_profile_id))
        seller_user = db.scalar(select(User).where(User.id == seller.user_id)) if seller else None
        if (
            seller is None
            or seller_user is None
            or seller_user.account_status != "ACTIVE"
            or seller.profile_status != "ACTIVE"
            or seller.verification_status != "APPROVED"
            or not _has_active_direct_seller_role(db, seller_user.id)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Seller for one of the requested items is not active and verified.",
            )

        product = db.scalar(select(Product).where(Product.id == listing.product_id))
        variant = db.scalar(select(ProductVariant).where(ProductVariant.id == listing.product_variant_id))
        if product is None or not product.is_active or product.approval_status != "APPROVED" or variant is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Referenced product or variant is inactive or unapproved.",
            )

        if req_item.quantity < listing.min_order_qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Quantity for '{listing.listing_title}' must be at least {listing.min_order_qty}.",
            )
        if listing.max_order_qty is not None and req_item.quantity > listing.max_order_qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Quantity for '{listing.listing_title}' cannot exceed {listing.max_order_qty}.",
            )

        line_total = (Decimal(listing.selling_price) * Decimal(req_item.quantity)).quantize(Decimal("0.01"))
        order_subtotal += line_total
        grouped_lines[seller.id].append((listing, product, variant, req_item.quantity, line_total))

    is_cod = payload.payment_method == "COD"
    addr_snap = payload.shipping_address.model_dump(mode="json")
    if payload.payment_label:
        addr_snap["payment_label"] = payload.payment_label.strip()

    order = RetailOrder(
        id=new_uuid(),
        order_number=f"HL-RET-{uuid.uuid4().hex[:8].upper()}",
        customer_user_id=principal.user_id,
        shipping_address_snapshot_json=addr_snap,
        currency_code="INR",
        subtotal_amount=order_subtotal,
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        shipping_fee=Decimal("0.00"),
        total_amount=order_subtotal,
        payment_method=payload.payment_method,
        payment_status="COD_PENDING" if is_cod else "PENDING",
        fulfilment_status="CONFIRMED" if is_cod else "PENDING_PAYMENT",
        confirmed_at=utcnow() if is_cod else None,
    )
    db.add(order)
    db.flush()

    created_items: list[RetailOrderItem] = []
    for seller_profile_id, seller_items in grouped_lines.items():
        group_sub = sum((lt for _, _, _, _, lt in seller_items), Decimal("0.00")).quantize(Decimal("0.01"))
        group = SellerFulfilmentGroup(
            id=new_uuid(),
            fulfilment_number=f"FG-{uuid.uuid4().hex[:8].upper()}",
            retail_order_id=order.id,
            seller_profile_id=seller_profile_id,
            currency_code="INR",
            subtotal_amount=group_sub,
            group_total_amount=group_sub,
            fulfilment_status=order.fulfilment_status,
        )
        db.add(group)
        db.flush()

        for listing, product, variant, qty, line_total in seller_items:
            row = RetailOrderItem(
                id=new_uuid(),
                retail_order_id=order.id,
                seller_fulfilment_group_id=group.id,
                seller_listing_id=listing.id,
                product_id=product.id,
                product_variant_id=variant.id,
                product_name_snapshot=listing.listing_title,
                sku_snapshot=variant.variant_sku,
                gi_status_snapshot=product.gi_status,
                quantity=qty,
                unit_price_snapshot=listing.selling_price,
                line_total_amount=line_total,
                currency_code="INR",
            )
            db.add(row)
            created_items.append(row)

    db.commit()
    return _serialize_order(order, created_items)


@router.get("/orders/retail/my", response_model=list[RetailOrderSummaryResponse])
def list_my_retail_orders(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[RetailOrderSummaryResponse]:
    orders = list(
        db.scalars(
            select(RetailOrder)
            .where(RetailOrder.customer_user_id == principal.user_id)
            .order_by(RetailOrder.created_at.desc())
            .limit(50)
        ).all()
    )
    results: list[RetailOrderSummaryResponse] = []
    for order in orders:
        items = list(
            db.scalars(select(RetailOrderItem).where(RetailOrderItem.retail_order_id == order.id)).all()
        )
        results.append(_serialize_order(order, items))
    return results


@router.get("/admin/overview")
def admin_live_overview(
    admin: AuthenticatedPrincipal = Depends(require_admin_permission("payments.read")),
    db: Session = Depends(get_db),
) -> dict:
    """Strictly admin-only real database snapshot for the Admin Console."""
    all_users = list(db.scalars(select(User).order_by(User.created_at.desc()).limit(2000)).all())
    users = [
        u
        for u in all_users
        if not (
            u.account_status == "DEACTIVATED"
            and u.email.endswith("@deleted.hunarlink.local")
        )
    ]
    deactivated_count = len(all_users) - len(users)
    active_user_ids = {u.id for u in users}
    all_sellers = list(db.scalars(select(SellerProfile).order_by(SellerProfile.created_at.desc()).limit(2000)).all())
    sellers = [
        s
        for s in all_sellers
        if s.profile_status != "TERMINATED" and s.user_id in active_user_ids
    ]
    all_applications = list(
        db.scalars(
            select(SellerVerificationApplication)
            .order_by(SellerVerificationApplication.created_at.desc())
            .limit(1000)
        ).all()
    )
    seller_docs = list(
        db.scalars(select(SellerDocument).order_by(SellerDocument.created_at.desc()).limit(1000)).all()
    )
    listings = list(
        db.scalars(select(SellerProductListing).order_by(SellerProductListing.created_at.desc()).limit(1000)).all()
    )
    orders = list(db.scalars(select(RetailOrder).order_by(RetailOrder.created_at.desc()).limit(100)).all())
    admin_creds = list(
        db.scalars(select(AdminCredential).order_by(AdminCredential.created_at.asc())).all()
    )
    role_rows = list(
        db.execute(
            select(UserRoleAssignment.user_id, PlatformRole.code)
            .join(PlatformRole, PlatformRole.id == UserRoleAssignment.platform_role_id)
            .where(UserRoleAssignment.assignment_status == "ACTIVE")
        ).all()
    )
    roles_by_user_id: dict[str, list[str]] = defaultdict(list)
    for uid, rcode in role_rows:
        if rcode not in roles_by_user_id[uid]:
            roles_by_user_id[uid].append(rcode)

    users_by_id = {u.id: u for u in all_users}
    sellers_by_id = {s.id: s for s in all_sellers}
    seller_by_user_id = {s.user_id: s for s in sellers}
    applications = [
        app_row
        for app_row in all_applications
        if app_row.seller_profile_id in sellers_by_id
        and sellers_by_id[app_row.seller_profile_id].user_id in active_user_ids
        and sellers_by_id[app_row.seller_profile_id].profile_status != "TERMINATED"
    ]
    active_admin_user_ids = {ac.user_id for ac in admin_creds if ac.is_active}
    docs_by_app_id: dict[str, list[SellerDocument]] = defaultdict(list)
    for d in seller_docs:
        if d.application_id:
            docs_by_app_id[d.application_id].append(d)

    # Map storage_key -> FileSecurityScan.id so Admin UI can fetch private uploaded cards cleanly
    scan_keys = [d.storage_key for d in seller_docs if d.storage_key]
    scan_id_by_key: dict[str, str] = {}
    if scan_keys:
        for sc in db.scalars(select(FileSecurityScan).where(FileSecurityScan.storage_key.in_(scan_keys))).all():
            scan_id_by_key[sc.storage_key] = sc.id

    try:
        if guardrail_repo.ensure_default_guardrail_rules(db):
            db.commit()
    except Exception:
        db.rollback()

    pending_apps_count = sum(
        1 for a in applications if a.application_status in {"SUBMITTED", "UNDER_REVIEW", "NEEDS_MORE_INFO"}
    )
    incomplete_artisan_users = [
        u
        for u in users
        if "DIRECT_SELLER" in roles_by_user_id.get(u.id, []) and u.id not in seller_by_user_id
    ]

    UserLoginLog.__table__.create(bind=db.get_bind(), checkfirst=True)
    login_logs = list(
        db.scalars(
            select(UserLoginLog).order_by(UserLoginLog.created_at.desc()).limit(500)
        ).all()
    )

    login_stats: dict[tuple[str, str], dict] = {}
    any_login_by_user: set[str] = set()
    for log_row in login_logs:
        if log_row.auth_event_type == "LOGIN":
            any_login_by_user.add(log_row.user_id)
            key = (log_row.user_id, log_row.role_code)
            entry = login_stats.get(key)
            if entry is None:
                login_stats[key] = {"count": 1, "latest": log_row.created_at}
            else:
                entry["count"] += 1
                if log_row.created_at > entry["latest"]:
                    entry["latest"] = log_row.created_at

    admin_cred_by_user_id = {ac.user_id: ac for ac in admin_creds}

    def _build_role_entry(u: User, role_code: str) -> dict:
        stat = login_stats.get((u.id, role_code))
        ac = admin_cred_by_user_id.get(u.id) if role_code == "ADMIN" else None
        sp = seller_by_user_id.get(u.id) if role_code == "DIRECT_SELLER" else None
        legacy_login = None
        if stat is None and u.id not in any_login_by_user:
            legacy_login = (ac.last_login_at if ac else None) or u.last_login_at
        elif role_code == "ADMIN" and ac and ac.last_login_at and (stat is None or ac.last_login_at > stat["latest"]):
            legacy_login = ac.last_login_at
        effective_last_login = (stat["latest"] if stat else None) or legacy_login
        login_count = stat["count"] if stat else (1 if effective_last_login is not None else 0)
        return {
            "user_id": u.id,
            "clerk_user_id": u.clerk_user_id,
            "name": u.display_name or f"{u.first_name} {u.last_name or ''}".strip(),
            "email": u.email,
            "phone": u.phone,
            "account_role": u.account_role,
            "role_code": role_code,
            "account_status": u.account_status,
            "registered_at": u.created_at.isoformat(),
            "last_login_at": effective_last_login.isoformat() if effective_last_login else None,
            "login_count": login_count,
            "has_logged_in": effective_last_login is not None,
            "store_name": sp.store_name if sp else None,
            "seller_profile_id": sp.id if sp else None,
            "verification_status": sp.verification_status if sp else None,
            "profile_status": sp.profile_status if sp else None,
            "admin_active": ac.is_active if ac else None,
        }

    role_groups_spec = [
        ("buyers", "Buyers (CUSTOMER)", {"CUSTOMER"}),
        ("artisans", "Artisans (DIRECT_SELLER)", {"DIRECT_SELLER"}),
        ("wholesale", "Wholesale / Dealers / Suppliers", {"WHOLESALE_BUYER", "DEALER", "SUPPLIER"}),
        ("admins", "Administrators (ADMIN)", {"ADMIN"}),
    ]
    role_directory: dict[str, dict] = {}
    for group_key, group_label, target_codes in role_groups_spec:
        registered_items: list[dict] = []
        seen_uids: set[str] = set()
        for u in users:
            u_roles = set(roles_by_user_id.get(u.id, []))
            if group_key == "admins" and u.id in admin_cred_by_user_id:
                u_roles.add("ADMIN")
            matched = sorted(u_roles & target_codes)
            if not matched:
                continue
            if u.id in seen_uids:
                continue
            seen_uids.add(u.id)
            registered_items.append(_build_role_entry(u, matched[0]))

        logged_in_items = sorted(
            [item for item in registered_items if item["has_logged_in"]],
            key=lambda x: x["last_login_at"] or "",
            reverse=True,
        )
        never_logged_in_items = [item for item in registered_items if not item["has_logged_in"]]
        role_directory[group_key] = {
            "label": group_label,
            "counts": {
                "registered": len(registered_items),
                "logged_in": len(logged_in_items),
                "never_logged_in": len(never_logged_in_items),
                "total_login_events": sum(item["login_count"] for item in registered_items),
            },
            "registered": registered_items,
            "logged_in": logged_in_items,
            "never_logged_in": never_logged_in_items,
        }

    return {
        "admin_user_id": admin.user_id,
        "admin_permissions": sorted(admin.admin_permissions),
        "counts": {
            "users": len(users),
            "deactivated_users": deactivated_count,
            "sellers": len(sellers),
            "pending_applications": pending_apps_count,
            "incomplete_artisan_signups": len(incomplete_artisan_users),
            "listings": len(listings),
            "orders": len(orders),
            "admins": len(admin_creds),
            "logged_in_users": sum(
                1
                for u in users
                if u.last_login_at is not None
                or u.id in any_login_by_user
                or (u.id in admin_cred_by_user_id and admin_cred_by_user_id[u.id].last_login_at is not None)
            ),
            "registered_buyers": role_directory["buyers"]["counts"]["registered"],
            "logged_in_buyers": role_directory["buyers"]["counts"]["logged_in"],
            "registered_artisans": role_directory["artisans"]["counts"]["registered"],
            "logged_in_artisans": role_directory["artisans"]["counts"]["logged_in"],
            "registered_wholesale": role_directory["wholesale"]["counts"]["registered"],
            "logged_in_wholesale": role_directory["wholesale"]["counts"]["logged_in"],
            "registered_admins": role_directory["admins"]["counts"]["registered"],
            "logged_in_admins": role_directory["admins"]["counts"]["logged_in"],
        },
        "role_directory": role_directory,
        "recent_auth_events": [
            {
                "id": ev.id,
                "user_id": ev.user_id,
                "name": (
                    users_by_id[ev.user_id].display_name
                    or f"{users_by_id[ev.user_id].first_name} {users_by_id[ev.user_id].last_name or ''}".strip()
                )
                if ev.user_id in users_by_id
                else ev.email,
                "email": ev.email,
                "role_code": ev.role_code,
                "auth_event_type": ev.auth_event_type,
                "auth_method": ev.auth_method,
                "ip_address": ev.ip_address,
                "created_at": ev.created_at.isoformat(),
            }
            for ev in login_logs[:100]
        ],
        "incomplete_artisan_signups": [
            {
                "user_id": u.id,
                "name": u.display_name or f"{u.first_name} {u.last_name or ''}".strip() or u.email,
                "email": u.email,
                "phone": u.phone,
                "created_at": u.created_at.isoformat(),
            }
            for u in incomplete_artisan_users
        ],
        "artisan_applications": [
            {
                "id": app_row.id,
                "application_number": app_row.application_number,
                "seller_profile_id": app_row.seller_profile_id,
                "store_name": sellers_by_id[app_row.seller_profile_id].store_name
                if app_row.seller_profile_id in sellers_by_id
                else "Artisan Workshop",
                "artisan_name": (
                    users_by_id[sellers_by_id[app_row.seller_profile_id].user_id].display_name
                    or users_by_id[sellers_by_id[app_row.seller_profile_id].user_id].email
                )
                if app_row.seller_profile_id in sellers_by_id
                and sellers_by_id[app_row.seller_profile_id].user_id in users_by_id
                else "Artisan",
                "artisan_email": (
                    users_by_id[sellers_by_id[app_row.seller_profile_id].user_id].email
                )
                if app_row.seller_profile_id in sellers_by_id
                and sellers_by_id[app_row.seller_profile_id].user_id in users_by_id
                else None,
                "artisan_phone": (
                    (app_row.submitted_metadata or {}).get("phone")
                    or (
                        users_by_id[sellers_by_id[app_row.seller_profile_id].user_id].phone
                        if app_row.seller_profile_id in sellers_by_id
                        and sellers_by_id[app_row.seller_profile_id].user_id in users_by_id
                        else None
                    )
                ),
                "craft_specialty": (
                    sellers_by_id[app_row.seller_profile_id].craft_specialty
                    if app_row.seller_profile_id in sellers_by_id
                    else (app_row.submitted_metadata or {}).get("craft_specialty")
                ),
                "workshop_district": app_row.claimed_craft_cluster
                or (
                    sellers_by_id[app_row.seller_profile_id].workshop_district
                    if app_row.seller_profile_id in sellers_by_id
                    else None
                ),
                "verification_path": app_row.verification_path,
                "application_status": app_row.application_status,
                "seller_verification_status": (
                    sellers_by_id[app_row.seller_profile_id].verification_status
                    if app_row.seller_profile_id in sellers_by_id
                    else None
                ),
                "seller_profile_status": (
                    sellers_by_id[app_row.seller_profile_id].profile_status
                    if app_row.seller_profile_id in sellers_by_id
                    else None
                ),
                "claimed_gi_code": app_row.claimed_gi_code,
                "skill_description": (app_row.submitted_metadata or {}).get("skill_description"),
                "artisan_card_scan_id": (app_row.submitted_metadata or {}).get("artisan_card_scan_id")
                or next(
                    (
                        scan_id_by_key.get(d.storage_key)
                        for d in docs_by_app_id.get(app_row.id, [])
                        if scan_id_by_key.get(d.storage_key)
                    ),
                    None,
                ),
                "artisan_card_filename": (app_row.submitted_metadata or {}).get("artisan_card_filename")
                or next(
                    (d.original_filename for d in docs_by_app_id.get(app_row.id, [])),
                    None,
                ),
                "review_decision_notes": app_row.review_decision_notes,
                "created_at": app_row.created_at.isoformat(),
            }
            for app_row in applications
        ],
        "admin_credentials": [
            {
                "id": ac.id,
                "user_id": ac.user_id,
                "name": (
                    (users_by_id[ac.user_id].display_name
                     or f"{users_by_id[ac.user_id].first_name} {users_by_id[ac.user_id].last_name or ''}".strip())
                    if ac.user_id in users_by_id
                    else ac.email
                ),
                "email": ac.email,
                "password_hash": ac.password_hash,
                "is_active": ac.is_active,
                "last_login_at": ac.last_login_at.isoformat() if ac.last_login_at else None,
                "created_at": ac.created_at.isoformat(),
            }
            for ac in admin_creds
        ],
        "users": [
            {
                "id": u.id,
                "clerk_user_id": u.clerk_user_id,
                "email": u.email,
                "name": u.display_name or f"{u.first_name} {u.last_name or ''}".strip(),
                "phone": u.phone,
                "account_role": u.account_role,
                "roles": roles_by_user_id.get(u.id, []),
                "onboarding_state": (
                    "ADMIN"
                    if (
                        u.id in active_admin_user_ids
                        or bool(
                            set(roles_by_user_id.get(u.id, []))
                            & {"SUPER_ADMIN", "OPS_ADMIN", "VERIFICATION_OFFICER", "FINANCE_ADMIN"}
                        )
                        or str(u.clerk_user_id or "").startswith("hl_admin_")
                    )
                    else (
                        seller_by_user_id[u.id].verification_status
                        if u.id in seller_by_user_id
                        else (
                            "STEP_1_ONLY_NO_CARD_YET"
                            if "DIRECT_SELLER" in roles_by_user_id.get(u.id, [])
                            else "BUYER"
                        )
                    )
                ),
                "account_status": u.account_status,
                "last_login_at": (
                    u.last_login_at.isoformat()
                    if u.last_login_at
                    else (
                        admin_cred_by_user_id[u.id].last_login_at.isoformat()
                        if u.id in admin_cred_by_user_id and admin_cred_by_user_id[u.id].last_login_at
                        else None
                    )
                ),
                "has_logged_in": bool(
                    u.last_login_at is not None
                    or u.id in any_login_by_user
                    or (u.id in admin_cred_by_user_id and admin_cred_by_user_id[u.id].last_login_at is not None)
                ),
                "login_count": sum(
                    st["count"] for (uid, _rc), st in login_stats.items() if uid == u.id
                ),
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
        "sellers": [
            {
                "id": s.id,
                "store_name": s.store_name,
                "store_slug": s.store_slug,
                "craft_specialty": s.craft_specialty,
                "workshop_district": s.workshop_district,
                "verification_path": s.verification_path,
                "verification_status": s.verification_status,
                "profile_status": s.profile_status,
                "claimed_gi_code": s.claimed_gi_authorized_user_no,
            }
            for s in sellers
        ],
        "listings": [
            {
                "id": l.id,
                "sku": l.seller_sku,
                "title": l.listing_title,
                "price": str(l.selling_price),
                "currency": l.currency_code,
                "status": l.listing_status,
            }
            for l in listings
        ],
        "orders": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "total_amount": str(o.total_amount),
                "payment_method": o.payment_method,
                "payment_status": o.payment_status,
                "fulfilment_status": o.fulfilment_status,
                "created_at": o.created_at.isoformat(),
            }
            for o in orders
        ],
    }


@router.get("/admin/users-by-role")
def admin_users_by_role(
    role_code: str | None = None,
    activity: str = "all",
    q: str | None = None,
    admin: AuthenticatedPrincipal = Depends(require_admin_permission("payments.read")),
    db: Session = Depends(get_db),
) -> dict:
    """Dedicated admin endpoint separating Registered vs Logged-In users per role."""
    snapshot = admin_live_overview(admin=admin, db=db)
    role_dir = snapshot["role_directory"]
    recent_events = snapshot["recent_auth_events"]
    search_term = (q or "").strip().lower()

    def _matches_user(item: dict) -> bool:
        if not search_term:
            return True
        haystack = " ".join(
            str(v or "")
            for v in (
                item.get("name"),
                item.get("email"),
                item.get("phone"),
                item.get("store_name"),
                item.get("account_role"),
                item.get("role_code"),
                item.get("user_id"),
                item.get("clerk_user_id"),
            )
        ).lower()
        return search_term in haystack

    code_map = {
        "CUSTOMER": "buyers",
        "BUYER": "buyers",
        "DIRECT_SELLER": "artisans",
        "ARTISAN": "artisans",
        "WHOLESALE": "wholesale",
        "WHOLESALE_BUYER": "wholesale",
        "DEALER": "wholesale",
        "SUPPLIER": "wholesale",
        "ADMIN": "admins",
    }
    selected_key = code_map.get((role_code or "").strip().upper()) if role_code else None
    if role_code and selected_key is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unsupported role_code filter. Use CUSTOMER, DIRECT_SELLER, WHOLESALE, or ADMIN.",
        )

    norm_activity = (activity or "all").strip().lower()
    if norm_activity not in {"all", "registered", "logged_in", "never_logged_in"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="activity must be one of: all, registered, logged_in, never_logged_in.",
        )

    result_groups: dict[str, dict] = {}
    for key, group in role_dir.items():
        if selected_key and key != selected_key:
            continue
        if norm_activity == "logged_in":
            rows = group["logged_in"]
        elif norm_activity == "never_logged_in":
            rows = group["never_logged_in"]
        else:
            rows = group["registered"]
        filtered_rows = [row for row in rows if _matches_user(row)]
        result_groups[key] = {
            "label": group["label"],
            "counts": group["counts"],
            "users": filtered_rows,
        }

    filtered_events = [
        ev
        for ev in recent_events
        if (not selected_key or code_map.get(ev["role_code"]) == selected_key)
        and (
            not search_term
            or search_term
            in " ".join(
                str(ev.get(k) or "")
                for k in ("name", "email", "role_code", "auth_method", "ip_address", "user_id")
            ).lower()
        )
    ]
    return {
        "role_filter": selected_key or "all",
        "activity_filter": norm_activity,
        "q": search_term or None,
        "groups": result_groups,
        "recent_auth_events": filtered_events,
    }


def _execute_admin_delete_user(
    *,
    user_id: str,
    payload: AdminDeleteUserRequest,
    request: Request,
    admin: AuthenticatedPrincipal,
    db: Session,
    settings: Settings,
) -> DeleteAccountResponse:
    if not _UUID_RE.match(user_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid user UUID format.",
        )
    if user_id == admin.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrators cannot delete their own admin account here.",
        )
    target = db.scalar(select(User).where(User.id == user_id))
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database.",
        )
    if target.account_status == "DEACTIVATED" and target.email.endswith("@deleted.hunarlink.local"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account has already been deleted.",
        )

    clerk_secret = settings.clerk_secret_key.get_secret_value().strip()
    result = execute_user_deletion(
        db,
        user=target,
        actor_user_id=admin.user_id,
        actor_role="ADMIN",
        reason=payload.reason or f"Deleted by administrator {admin.email}",
        request=request,
        clerk_secret=clerk_secret,
        current_password=None,
        allow_purge_if_clean=True,
        audit_action="ADMIN_USER_DELETED",
        self_delete_mode=False,
    )
    return DeleteAccountResponse(
        deleted=True,
        anonymized=result.anonymized,
        purged=result.purged,
        clerk_deleted=result.clerk_deleted,
        clerk_deleted_count=result.clerk_deleted_count,
        message=result.message,
    )


@router.delete("/admin/users/{user_id}", response_model=DeleteAccountResponse)
def admin_delete_user_rest(
    user_id: str,
    request: Request,
    payload: AdminDeleteUserRequest | None = Body(default=None),
    admin: AuthenticatedPrincipal = Depends(require_admin_permission("guardrails.decide")),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DeleteAccountResponse:
    """Safely delete/anonymize a user in DB AND automatically delete them from Clerk."""
    return _execute_admin_delete_user(
        user_id=user_id,
        payload=payload or AdminDeleteUserRequest(),
        request=request,
        admin=admin,
        db=db,
        settings=settings,
    )


@router.post("/admin/users/{user_id}/delete", response_model=DeleteAccountResponse)
def admin_delete_user_post(
    user_id: str,
    request: Request,
    payload: AdminDeleteUserRequest | None = Body(default=None),
    admin: AuthenticatedPrincipal = Depends(require_admin_permission("guardrails.decide")),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DeleteAccountResponse:
    """POST alias for deleting a user cleanly from DB and Clerk."""
    return _execute_admin_delete_user(
        user_id=user_id,
        payload=payload or AdminDeleteUserRequest(),
        request=request,
        admin=admin,
        db=db,
        settings=settings,
    )


_GUILD_CATEGORIES: dict[str, tuple[str, str, bool]] = {
    "pashmina": ("PASHMINA", "Pashmina Textiles", True),
    "walnut": ("WALNUT", "Walnut Woodcarving", True),
    "papier-mache": ("PAPIER_MACHE", "Papier-Mache Art", True),
    "silk-rugs": ("SILK_RUGS", "Silk-on-Silk Rugs", True),
}


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (value or "craft").lower()).strip("-")
    return (base or "craft")[:90]


def _resolve_or_stage_studio_product(
    db: Session,
    *,
    principal: AuthenticatedPrincipal,
    payload: SellerStudioListingInput,
    persist_product: bool,
) -> tuple[str, str, str]:
    """Resolve real DB Category/Product/Variant IDs for Seller Studio ASIGS evaluation."""
    guild_key = (payload.guild or "pashmina").strip().lower()
    cat_code, cat_name, is_gi_cat = _GUILD_CATEGORIES.get(
        guild_key, ("PASHMINA", "Pashmina Textiles", True)
    )
    sku = (
        payload.seller_sku.strip()
        if payload.seller_sku and payload.seller_sku.strip()
        else f"HL-{cat_code[:6]}-{uuid.uuid4().hex[:6].upper()}"
    )

    if not persist_product:
        existing_var = db.scalar(
            select(ProductVariant)
            .join(Product, Product.id == ProductVariant.product_id)
            .where(Product.is_active == True, Product.approval_status == "APPROVED")  # noqa: E712
            .limit(1)
        )
        if existing_var is not None:
            return existing_var.product_id, existing_var.id, sku

    cat = db.scalar(select(Category).where(Category.code == cat_code))
    if cat is None:
        cat = Category(
            id=new_uuid(),
            code=cat_code,
            name=cat_name,
            slug=guild_key if guild_key in _GUILD_CATEGORIES else _slugify(cat_name),
            is_gi_eligible_category=is_gi_cat,
            is_active=True,
        )
        db.add(cat)
        db.flush()

    unique_suffix = uuid.uuid4().hex[:8]
    prod = Product(
        id=new_uuid(),
        category_id=cat.id,
        sku_root=f"PRD-{cat_code[:4]}-{unique_suffix.upper()}",
        name=payload.title.strip()[:220],
        slug=f"{_slugify(payload.title)}-{unique_suffix}",
        short_description=(payload.description or payload.title).strip()[:450],
        description=(payload.description or payload.title).strip(),
        gi_status="PENDING_REVIEW",
        approval_status="APPROVED",
        is_active=True,
        created_by_user_id=principal.user_id,
    )
    db.add(prod)
    db.flush()

    mrp_val = payload.compare_at_mrp if payload.compare_at_mrp is not None else payload.selling_price
    variant = ProductVariant(
        id=new_uuid(),
        product_id=prod.id,
        variant_sku=f"VAR-{cat_code[:4]}-{unique_suffix.upper()}",
        variant_name="Standard Craft Edition",
        base_mrp=mrp_val,
        currency_code=payload.currency_code.upper(),
        is_active=True,
    )
    db.add(variant)
    db.flush()
    return prod.id, variant.id, sku


@router.get("/seller/studio/listings")
def list_my_studio_listings(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return the signed-in artisan's live DB listings (all statuses)."""
    seller = db.scalar(select(SellerProfile).where(SellerProfile.user_id == principal.user_id))
    if seller is None:
        return []
    rows = db.execute(
        select(SellerProductListing, Product, Category)
        .join(Product, Product.id == SellerProductListing.product_id)
        .join(Category, Category.id == Product.category_id)
        .where(SellerProductListing.seller_profile_id == seller.id)
        .order_by(SellerProductListing.created_at.desc())
    ).all()
    return [
        {
            "listing_id": l.id,
            "product_id": l.product_id,
            "product_variant_id": l.product_variant_id,
            "seller_sku": l.seller_sku,
            "title": l.listing_title,
            "description": p.description or p.short_description or "",
            "guild": c.slug,
            "guild_label": c.name,
            "selling_price": str(l.selling_price),
            "compare_at_mrp": str(l.compare_at_mrp) if l.compare_at_mrp is not None else None,
            "currency_code": l.currency_code,
            "listing_status": l.listing_status,
            "gi_status": p.gi_status,
            "created_at": l.created_at.isoformat(),
        }
        for l, p, c in rows
    ]


@router.post("/seller/studio/validate", response_model=GuardrailResponse)
def validate_studio_listing(
    payload: SellerStudioListingInput,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> GuardrailResponse:
    """Dry-run an Artisan Studio craft through all 10 ASIGS Guardrail layers."""
    product_id, variant_id, sku = _resolve_or_stage_studio_product(
        db, principal=principal, payload=payload, persist_product=False
    )
    listing_in = SellerListingInput(
        product_id=product_id,
        product_variant_id=variant_id,
        seller_sku=sku,
        listing_title=payload.title,
        description=payload.description,
        technique=payload.technique,
        dimensions=payload.dimensions,
        origin_district=payload.origin_district,
        purity_metric=payload.purity_metric,
        selling_price=payload.selling_price,
        compare_at_mrp=payload.compare_at_mrp,
        currency_code=payload.currency_code,
        stock_quantity=payload.stock_quantity,
        min_order_qty=payload.min_order_qty,
        requested_gi_status=payload.requested_gi_status,
        requested_listing_status=payload.requested_listing_status,
    )
    corr_id = getattr(request.state, "correlation_id", "") or str(uuid.uuid4())
    return guardrail_service.evaluate_seller_listing(
        db,
        principal=principal,
        payload=listing_in,
        correlation_id=corr_id,
        create_record=False,
    )


@router.post(
    "/seller/studio/listings",
    response_model=GuardrailResponse,
    status_code=status.HTTP_201_CREATED,
)
def publish_studio_listing(
    payload: SellerStudioListingInput,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> GuardrailResponse:
    """Persist an Artisan Studio craft through all 10 ASIGS Guardrail layers into the live DB."""
    corr_id = getattr(request.state, "correlation_id", "") or str(uuid.uuid4())

    # First dry-run to avoid creating orphan Product rows on BLOCK
    dry_prod_id, dry_var_id, sku = _resolve_or_stage_studio_product(
        db, principal=principal, payload=payload, persist_product=False
    )
    dry_in = SellerListingInput(
        product_id=dry_prod_id,
        product_variant_id=dry_var_id,
        seller_sku=sku,
        listing_title=payload.title,
        description=payload.description,
        technique=payload.technique,
        dimensions=payload.dimensions,
        origin_district=payload.origin_district,
        purity_metric=payload.purity_metric,
        selling_price=payload.selling_price,
        compare_at_mrp=payload.compare_at_mrp,
        currency_code=payload.currency_code,
        stock_quantity=payload.stock_quantity,
        min_order_qty=payload.min_order_qty,
        requested_gi_status=payload.requested_gi_status,
        requested_listing_status=payload.requested_listing_status,
    )
    dry_res = guardrail_service.evaluate_seller_listing(
        db,
        principal=principal,
        payload=dry_in,
        correlation_id=corr_id,
        create_record=False,
    )
    if dry_res.outcome == GuardrailOutcome.BLOCK:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=dry_res.model_dump(mode="json"),
        )

    product_id, variant_id, final_sku = _resolve_or_stage_studio_product(
        db, principal=principal, payload=payload, persist_product=True
    )
    listing_in = SellerListingInput(
        product_id=product_id,
        product_variant_id=variant_id,
        seller_sku=final_sku,
        listing_title=payload.title,
        description=payload.description,
        technique=payload.technique,
        dimensions=payload.dimensions,
        origin_district=payload.origin_district,
        purity_metric=payload.purity_metric,
        selling_price=payload.selling_price,
        compare_at_mrp=payload.compare_at_mrp,
        currency_code=payload.currency_code,
        stock_quantity=payload.stock_quantity,
        min_order_qty=payload.min_order_qty,
        requested_gi_status=payload.requested_gi_status,
        requested_listing_status=payload.requested_listing_status,
    )
    res = guardrail_service.evaluate_seller_listing(
        db,
        principal=principal,
        payload=listing_in,
        correlation_id=corr_id,
        create_record=True,
    )
    if res.outcome == GuardrailOutcome.BLOCK:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=res.model_dump(mode="json"),
        )
    return res


@router.post("/admin/listings/{listing_id}/moderate")
def admin_moderate_listing(
    listing_id: str,
    payload: dict,
    request: Request,
    admin: AuthenticatedPrincipal = Depends(require_admin_permission("guardrails.decide")),
    db: Session = Depends(get_db),
) -> dict:
    """Allow an authorized Admin to approve (`ACTIVE`), pause (`PAUSED`), or reject (`REJECTED`) a listing."""
    target_status = str(payload.get("listing_status") or "").strip().upper()
    if target_status not in {"ACTIVE", "PAUSED", "REJECTED"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="listing_status must be ACTIVE, PAUSED, or REJECTED.",
        )
    listing = db.scalar(select(SellerProductListing).where(SellerProductListing.id == listing_id))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found.")

    prev = listing.listing_status
    listing.listing_status = target_status
    record_audit_log(
        db,
        actor_user_id=admin.user_id,
        actor_role="ADMIN",
        action=f"ADMIN_LISTING_{target_status}",
        target_type="seller_product_listings",
        target_id=listing.id,
        correlation_id=getattr(request.state, "correlation_id", "") or str(uuid.uuid4()),
        previous_values={"listing_status": prev},
        new_values={"listing_status": target_status},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return {
        "listing_id": listing.id,
        "previous_status": prev,
        "listing_status": listing.listing_status,
        "moderated_by": admin.user_id,
    }


@router.post("/admin/artisan-applications/{application_id}/decision")
def admin_decide_artisan_application(
    application_id: str,
    payload: dict,
    request: Request,
    admin: AuthenticatedPrincipal = Depends(require_admin_permission("guardrails.decide")),
    db: Session = Depends(get_db),
) -> dict:
    """Approve or Reject a staged Artisan Verification Application from `/admin`.

    - `APPROVE`: promotes `SellerVerificationApplication.application_status = 'APPROVED'`,
      sets `SellerProfile.verification_status = 'APPROVED'` and `SellerProfile.profile_status = 'ACTIVE'`,
      marks linked `SellerDocument`s `ACCEPTED`, and ensures active `DIRECT_SELLER` role assignment.
      The artisan immediately unlocks `/seller` and appears in `/api/v1/artisans` under their unique UUID!
    - `REJECT`: sets `application_status = 'REJECTED'`, `SellerProfile.verification_status = 'REJECTED'`,
      `SellerProfile.profile_status = 'DRAFT'`, and marks linked documents `REJECTED`.
    """
    decision = str(payload.get("decision") or "").strip().upper()
    notes = str(payload.get("notes") or "").strip()[:1000] or None
    if decision not in {"APPROVE", "REJECT"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="decision must be APPROVE or REJECT.",
        )

    app_row = db.scalar(
        select(SellerVerificationApplication).where(
            SellerVerificationApplication.id == application_id
        )
    )
    if app_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artisan verification application not found.",
        )

    seller = db.scalar(
        select(SellerProfile).where(SellerProfile.id == app_row.seller_profile_id)
    )
    if seller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked seller profile not found.",
        )

    if seller.user_id == admin.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrators cannot self-approve their own seller application.",
        )

    prev_app_status = app_row.application_status
    prev_seller_ver = seller.verification_status
    prev_seller_prof = seller.profile_status

    docs = list(
        db.scalars(
            select(SellerDocument).where(SellerDocument.application_id == app_row.id)
        ).all()
    )

    if decision == "APPROVE":
        app_row.application_status = "APPROVED"
        seller.verification_status = "APPROVED"
        seller.profile_status = "ACTIVE"
        for d in docs:
            d.verification_status = "ACCEPTED"
            d.reviewed_by_user_id = admin.user_id
            d.review_notes = notes or "Verified by HunarLink Admin"

        # Ensure DIRECT_SELLER role is active
        ds_role = db.scalar(select(PlatformRole).where(PlatformRole.code == "DIRECT_SELLER"))
        if ds_role is None:
            ds_role = PlatformRole(
                id=new_uuid(), code="DIRECT_SELLER", name="Direct Artisan Seller", is_active=True
            )
            db.add(ds_role)
            db.flush()
        assign = db.scalar(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == seller.user_id,
                UserRoleAssignment.platform_role_id == ds_role.id,
            )
        )
        if assign is None:
            db.add(
                UserRoleAssignment(
                    id=new_uuid(),
                    user_id=seller.user_id,
                    platform_role_id=ds_role.id,
                    assignment_status="ACTIVE",
                    granted_at=utcnow(),
                )
            )
        else:
            assign.assignment_status = "ACTIVE"
    else:
        app_row.application_status = "REJECTED"
        seller.verification_status = "REJECTED"
        seller.profile_status = "DRAFT"
        for d in docs:
            d.verification_status = "REJECTED"
            d.reviewed_by_user_id = admin.user_id
            d.review_notes = notes or "Rejected by HunarLink Admin"

    app_row.reviewed_by_user_id = admin.user_id
    app_row.review_decision_notes = notes or (
        "Verified & promoted to live artisan directory"
        if decision == "APPROVE"
        else "Application rejected during admin verification"
    )

    record_audit_log(
        db,
        actor_user_id=admin.user_id,
        actor_role="ADMIN",
        action=f"ADMIN_ARTISAN_APPLICATION_{decision}",
        target_type="seller_verification_applications",
        target_id=app_row.id,
        reason=app_row.review_decision_notes,
        correlation_id=getattr(request.state, "correlation_id", "") or str(uuid.uuid4()),
        previous_values={
            "application_status": prev_app_status,
            "seller_verification_status": prev_seller_ver,
            "seller_profile_status": prev_seller_prof,
        },
        new_values={
            "application_status": app_row.application_status,
            "seller_verification_status": seller.verification_status,
            "seller_profile_status": seller.profile_status,
        },
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return {
        "application_id": app_row.id,
        "application_number": app_row.application_number,
        "application_status": app_row.application_status,
        "seller_profile_id": seller.id,
        "store_name": seller.store_name,
        "verification_status": seller.verification_status,
        "profile_status": seller.profile_status,
        "artisan_page_url": f"/artisan?id={seller.id}",
        "reviewed_by": admin.user_id,
        "review_decision_notes": app_row.review_decision_notes,
    }


@router.post("/admin/sellers/{seller_id}/verify")
def admin_verify_seller(
    seller_id: str,
    payload: dict,
    admin: AuthenticatedPrincipal = Depends(require_admin_permission("guardrails.decide")),
    db: Session = Depends(get_db),
) -> dict:
    """Allow an authorized Admin to APPROVE or REJECT an artisan's verification status in DB."""
    decision = str(payload.get("decision") or "").strip().upper()
    if decision not in {"APPROVED", "REJECTED"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="decision must be APPROVED or REJECTED.",
        )
    seller = db.scalar(select(SellerProfile).where(SellerProfile.id == seller_id))
    if seller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artisan profile not found.")

    prev_verify = seller.verification_status
    seller.verification_status = decision
    seller.profile_status = "ACTIVE" if decision == "APPROVED" else "DRAFT"

    latest_app = db.scalar(
        select(SellerVerificationApplication)
        .where(SellerVerificationApplication.seller_profile_id == seller.id)
        .order_by(SellerVerificationApplication.created_at.desc())
        .limit(1)
    )
    if latest_app is not None:
        latest_app.application_status = decision
        latest_app.reviewed_by_user_id = admin.user_id

    db.commit()
    return {
        "seller_id": seller.id,
        "previous_verification_status": prev_verify,
        "verification_status": seller.verification_status,
        "profile_status": seller.profile_status,
        "verified_by": admin.user_id,
    }
