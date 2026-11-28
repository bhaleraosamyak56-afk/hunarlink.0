"""Idempotent database seeder for all 53 verified Kashmiri artisans & 96 craft listings.

Works seamlessly on BOTH MySQL 8.4 LTS (configured via MYSQL_* in backend/.env)
AND local SQLite (configured via DATABASE_URL=sqlite:///./hunarlink_dev.db).

Every artisan and every product/listing receives a deterministic, stable UUIDv5
so links like `/product?id=<uuid>` and `/artisan?id=<uuid>` remain unique and
consistent across deployments while backed 100% by database rows (`users`,
`user_role_assignments`, `seller_profiles`, `seller_verification_applications`,
`seller_documents`, `categories`, `products`, `product_variants`,
`product_images`, and `seller_product_listings`).

Usage (from backend/ directory):
    python scripts/seed_real_artisans.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import uuid
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import create_db_engine
from app.models.base import Base, utcnow
from app.models.core_models import (
    Category,
    PlatformRole,
    Product,
    ProductImage,
    ProductVariant,
    SellerDocument,
    SellerProductListing,
    SellerProfile,
    SellerVerificationApplication,
    User,
    UserRoleAssignment,
)
from app.models.guardrail_models import GuardrailRule

HUNARLINK_UUID_NS = uuid.UUID("7f9d4c10-6b81-4e2f-9a53-2c8d11e04b77")
SEED_JSON_PATH = Path(__file__).resolve().parent / "heritage_catalog_seed.json"
REPO_ROOT = BACKEND_ROOT.parent


def stable_uuid(scope: str, key: str) -> str:
    return str(uuid.uuid5(HUNARLINK_UUID_NS, f"hunarlink:{scope}:{key.strip().lower()}"))


def slugify(raw: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", raw.strip().lower()).strip("-")
    return cleaned or "craft"


CATEGORY_MAP = {
    "pashmina": ("PASHMINA", "Pashmina Textiles", "pashmina", True),
    "walnut": ("WALNUT_WOOD", "Walnut Woodcarving", "walnut", True),
    "papier-mache": ("PAPIER_MACHE", "Papier-Mâché Art", "papier-mache", True),
    "silk-rugs": ("SILK_CARPETS", "Silk-on-Silk Rugs", "silk-rugs", True),
}


def _split_person_name(full_name: str) -> tuple[str, str]:
    clean = re.sub(r"^(Ustadani|Ustad|Master)\s+", "", full_name.strip(), flags=re.IGNORECASE).strip()
    parts = clean.split()
    if len(parts) <= 1:
        return clean or full_name.strip(), ""
    return " ".join(parts[:-1]), parts[-1]


def _derive_bio(name: str, craft: str, district: str, count: int, gi_level: int) -> str:
    gi_phrase = (
        "holding GI Tier-3 provenance verification"
        if gi_level >= 3
        else "registered with the HunarLink Valley Craft Guild"
    )
    piece_word = "1 curated heirloom piece" if count == 1 else f"{count} curated heirloom pieces"
    return (
        f"Independent master workshop led by {name} in {district}, Jammu & Kashmir, "
        f"specialising in {craft} and {gi_phrase}. Currently offering {piece_word} "
        f"direct from the atelier with zero middleman cut."
    )


def seed_artisans_and_catalog(*, session_override: Session | None = None) -> dict[str, int]:
    if not SEED_JSON_PATH.exists():
        raise FileNotFoundError(f"Missing seed dataset: {SEED_JSON_PATH}")

    payload = json.loads(SEED_JSON_PATH.read_text(encoding="utf-8"))
    showcase_list: list[dict] = payload.get("showcase", [])
    products_list: list[dict] = payload.get("products", [])

    showcase_by_name = {
        item["name"].strip().lower(): (idx, item)
        for idx, item in enumerate(showcase_list)
    }

    owns_engine = session_override is None
    if owns_engine:
        settings = get_settings()
        engine = create_db_engine(settings)
        if engine.dialect.name == "sqlite":
            Base.metadata.create_all(bind=engine)
        db_ctx = Session(engine)
        dialect_label = engine.dialect.name.upper()
    else:
        db_ctx = session_override
        dialect_label = "SESSION"

    def _run(db: Session) -> dict[str, int]:
        # 1. Platform Roles
        role_map: dict[str, PlatformRole] = {}
        for idx, (code, name) in enumerate(
            [
                ("CUSTOMER", "Retail Customer"),
                ("DIRECT_SELLER", "Direct Artisan Seller"),
                ("SUPPLIER", "Craft Supplier"),
                ("DEALER", "Wholesale Dealer"),
                ("WHOLESALE_BUYER", "Wholesale Buyer"),
                ("ADMIN", "Platform Admin"),
            ],
            start=1,
        ):
            role = db.scalar(select(PlatformRole).where(PlatformRole.code == code))
            if role is None:
                role = PlatformRole(
                    id=f"10000000-0000-4000-8000-{idx:012d}",
                    code=code,
                    name=name,
                    is_active=True,
                )
                db.add(role)
                db.flush()
            role_map[code] = role

        # 2. Core Guardrail Rules (if absent)
        for rule_code, layer, name, outcome in [
            ("PROD_SELLER_CANNOT_SELF_VERIFY_GI", "PRODUCT", "Block seller self-assignment of GI_VERIFIED", "BLOCK"),
            ("COMM_PRICE_ABOVE_MRP", "COMMERCIAL", "Reject selling price exceeding compare-at MRP", "BLOCK"),
            ("DOC_MIME_SIGNATURE_MISMATCH", "DOCUMENT", "Block spoofed document extension vs magic bytes", "BLOCK"),
        ]:
            if db.scalar(select(GuardrailRule).where(GuardrailRule.rule_code == rule_code)) is None:
                db.add(
                    GuardrailRule(
                        id=stable_uuid("guardrail_rule", rule_code),
                        rule_code=rule_code,
                        layer=layer,
                        name=name,
                        default_outcome=outcome,
                        is_active=True,
                        rule_version="1.0.0",
                    )
                )
        db.flush()

        # 3. Categories
        cat_cache: dict[str, Category] = {}
        for guild_key, (cat_code, cat_name, cat_slug, is_gi) in CATEGORY_MAP.items():
            cat = (
                db.scalar(select(Category).where(Category.code == cat_code))
                or db.scalar(select(Category).where(Category.slug == cat_slug))
            )
            if cat is None:
                cat = Category(
                    id=stable_uuid("category", cat_code),
                    code=cat_code,
                    name=cat_name,
                    slug=cat_slug,
                    is_gi_eligible_category=is_gi,
                    is_active=True,
                )
                db.add(cat)
                db.flush()
            cat_cache[guild_key] = cat

        # Group products by artisan so we compute accurate ratings, reviews & specialties
        by_artisan: dict[str, list[dict]] = defaultdict(list)
        artisan_display_names: dict[str, str] = {}
        for p in products_list:
            raw_name = p["artisan"].strip()
            norm = raw_name.lower()
            artisan_display_names.setdefault(norm, raw_name)
            by_artisan[norm].append(p)

        for norm, (_, sc) in showcase_by_name.items():
            artisan_display_names.setdefault(norm, sc["name"].strip())
            by_artisan.setdefault(norm, [])

        artisan_entities: dict[str, tuple[User, SellerProfile]] = {}
        upserted_artisans = 0
        upserted_listings = 0

        # 4. Seed all 53 verified Artisans (Users + DIRECT_SELLER + SellerProfile + Portrait Document + Application)
        for norm_key, prods in sorted(by_artisan.items()):
            display_name = artisan_display_names[norm_key]
            art_slug = slugify(display_name)
            first_name, last_name = _split_person_name(display_name)
            showcase_entry = showcase_by_name.get(norm_key)
            sc_order = showcase_entry[0] if showcase_entry else 999
            sc_data = showcase_entry[1] if showcase_entry else None

            districts = [p.get("district") for p in prods if p.get("district")]
            main_district = districts[0] if districts else "Srinagar"
            guild_labels = [p.get("guildLabel") for p in prods if p.get("guildLabel")]
            craft_specialty = (
                sc_data["craft"]
                if sc_data and sc_data.get("craft")
                else (guild_labels[0] if guild_labels else "Kashmiri Heritage Craft")
            )
            gi_codes = [p.get("giId") for p in prods if p.get("giId")]
            claimed_gi = gi_codes[0] if gi_codes else f"GI-JK-{art_slug[:8].upper()}"
            max_gi_lvl = max((int(p.get("giLevel") or 2) for p in prods), default=3)

            total_rev_count = sum(int(p.get("reviewCount") or 0) for p in prods)
            if sc_data and sc_data.get("reviews"):
                total_rev_count = max(total_rev_count, len(sc_data["reviews"]))

            if prods:
                weighted_sum = sum(float(p.get("rating") or 4.9) * max(int(p.get("reviewCount") or 1), 1) for p in prods)
                weight_total = sum(max(int(p.get("reviewCount") or 1), 1) for p in prods)
                avg_rating = Decimal(f"{weighted_sum / weight_total:.2f}")
            else:
                avg_rating = Decimal("4.95")

            bio_text = (
                sc_data["bio"]
                if sc_data and sc_data.get("bio")
                else _derive_bio(display_name, craft_specialty, main_district, len(prods), max_gi_lvl)
            )
            credential = (
                sc_data["credential"]
                if sc_data and sc_data.get("credential")
                else f"{'GI Tier-3 Verified' if max_gi_lvl >= 3 else 'GI Registered'} · {main_district} Artisan Cluster"
            )
            # Portrait: 6 showcase masters get their dedicated studio portraits `img/artisans/artisan-01..06.jpg`;
            # every other artisan gets their signature heirloom piece photograph stored in DB.
            top_prod = max(prods, key=lambda x: float(x.get("price") or 0)) if prods else None
            portrait_url = (
                sc_data["portrait"]
                if sc_data and sc_data.get("portrait")
                else (top_prod["image"] if top_prod else "img/artisans/artisan-01.jpg")
            )

            clerk_id = f"clerk_artisan_{art_slug.replace('-', '_')[:90]}"
            email = f"{art_slug[:64]}@artisans.hunarlink.in"
            user_uuid = stable_uuid("artisan_user", art_slug)
            seller_uuid = stable_uuid("seller_profile", art_slug)

            user = (
                db.scalar(select(User).where(User.id == user_uuid))
                or db.scalar(select(User).where(User.clerk_user_id == clerk_id))
                or db.scalar(select(User).where(User.email == email))
            )
            if user is None:
                user = User(
                    id=user_uuid,
                    clerk_user_id=clerk_id,
                    email=email,
                    email_verified=True,
                    first_name=first_name,
                    last_name=last_name or None,
                    display_name=display_name,
                    preferred_currency="INR",
                    account_role="ARTISAN",
                    account_status="ACTIVE",
                )
                db.add(user)
                db.flush()
            else:
                user.display_name = display_name
                user.account_role = "ARTISAN"
                user.account_status = "ACTIVE"
                db.flush()

            has_role = db.scalar(
                select(UserRoleAssignment).where(
                    UserRoleAssignment.user_id == user.id,
                    UserRoleAssignment.platform_role_id == role_map["DIRECT_SELLER"].id,
                )
            )
            if has_role is None:
                db.add(
                    UserRoleAssignment(
                        id=stable_uuid("role_assign_seller", user.id),
                        user_id=user.id,
                        platform_role_id=role_map["DIRECT_SELLER"].id,
                        assignment_status="ACTIVE",
                        granted_at=utcnow(),
                    )
                )
            else:
                has_role.assignment_status = "ACTIVE"
            db.flush()

            store_name = f"{display_name} Heritage Atelier"[:160]
            seller = (
                db.scalar(select(SellerProfile).where(SellerProfile.id == seller_uuid))
                or db.scalar(select(SellerProfile).where(SellerProfile.store_slug == art_slug))
                or db.scalar(select(SellerProfile).where(SellerProfile.user_id == user.id))
            )
            if seller is None:
                seller = SellerProfile(
                    id=seller_uuid,
                    user_id=user.id,
                    store_name=store_name,
                    store_slug=art_slug,
                    craft_specialty=craft_specialty[:160],
                    workshop_district=main_district[:100],
                    verification_path="GI",
                    profile_status="ACTIVE",
                    verification_status="APPROVED",
                    claimed_gi_authorized_user_no=claimed_gi[:120],
                    bio=bio_text,
                    average_rating=avg_rating,
                    total_reviews=total_rev_count,
                )
                db.add(seller)
                db.flush()
                upserted_artisans += 1
            else:
                seller.store_slug = art_slug
                seller.craft_specialty = craft_specialty[:160]
                seller.workshop_district = main_district[:100]
                seller.verification_path = "GI"
                seller.profile_status = "ACTIVE"
                seller.verification_status = "APPROVED"
                seller.claimed_gi_authorized_user_no = claimed_gi[:120]
                seller.bio = bio_text
                seller.average_rating = avg_rating
                seller.total_reviews = total_rev_count
                db.flush()

            app_num = f"HL-VER-{art_slug[:36].upper()}"
            app_meta = {
                "portrait_url": portrait_url,
                "bio": bio_text,
                "credential": credential,
                "since": sc_data.get("since") if sc_data else None,
                "featured_showcase": bool(sc_data is not None),
                "featured_order": sc_order,
                "reviews": sc_data.get("reviews", []) if sc_data else [],
            }
            ver_app = db.scalar(
                select(SellerVerificationApplication).where(
                    SellerVerificationApplication.application_number == app_num
                )
            )
            if ver_app is None:
                ver_app = SellerVerificationApplication(
                    id=stable_uuid("seller_ver_app", art_slug),
                    seller_profile_id=seller.id,
                    application_number=app_num,
                    verification_path="GI",
                    application_status="APPROVED",
                    claimed_gi_code=claimed_gi[:120],
                    claimed_craft_cluster=f"{main_district} Cluster",
                    submitted_metadata=app_meta,
                    review_decision_notes="Verified heritage master artisan record.",
                )
                db.add(ver_app)
                db.flush()
            else:
                ver_app.application_status = "APPROVED"
                ver_app.submitted_metadata = app_meta
                db.flush()

            # Store artisan portrait in `seller_documents` (`ARTISAN_PORTRAIT`)
            # Use unique storage_key per seller (`<portrait_url>#seller=<slug>` when shared, or clean path if unique)
            # Wait: `seller_documents` has UNIQUE(storage_key), and two artisans don't share top_prod image because all 96 product images are unique!
            doc_storage_key = portrait_url
            existing_key_owner = db.scalar(
                select(SellerDocument).where(SellerDocument.storage_key == doc_storage_key)
            )
            if existing_key_owner is not None and existing_key_owner.seller_profile_id != seller.id:
                doc_storage_key = f"{portrait_url}?artisan={art_slug}"

            portrait_doc = db.scalar(
                select(SellerDocument).where(
                    SellerDocument.seller_profile_id == seller.id,
                    SellerDocument.document_type == "ARTISAN_PORTRAIT",
                )
            )
            asset_file = REPO_ROOT / "app" / "public" / portrait_url
            file_bytes = asset_file.stat().st_size if asset_file.exists() else 128000
            digest = hashlib.sha256(doc_storage_key.encode("utf-8")).hexdigest()

            if portrait_doc is None:
                db.add(
                    SellerDocument(
                        id=stable_uuid("seller_portrait_doc", seller.id),
                        seller_profile_id=seller.id,
                        application_id=ver_app.id,
                        document_type="ARTISAN_PORTRAIT",
                        storage_key=doc_storage_key,
                        original_filename=Path(portrait_url).name,
                        detected_mime_type="image/jpeg",
                        file_size_bytes=max(1, file_bytes),
                        sha256_hash=digest,
                        scan_status="CLEAN",
                        verification_status="ACCEPTED",
                        uploaded_by_user_id=user.id,
                    )
                )
            else:
                portrait_doc.storage_key = doc_storage_key
                portrait_doc.verification_status = "ACCEPTED"
                portrait_doc.scan_status = "CLEAN"
            db.flush()

            artisan_entities[norm_key] = (user, seller)

        # 5. Remove obsolete placeholder 4-item demo SKUs (`HL-SILK-001`, `HL-PMAC-001`) if unreferenced
        # and seed all 96 authentic HunarLink catalogue products with deterministic UUIDs
        seeded_skus = {p["id"].strip().upper() for p in products_list}
        stale_listings = db.scalars(
            select(SellerProductListing).where(SellerProductListing.seller_sku.notin_(seeded_skus))
        ).all()
        for sl in stale_listings:
            if sl.seller_sku.startswith("HL-"):
                sl.listing_status = "PAUSED"
        db.flush()

        for p in products_list:
            legacy_code = p["id"].strip().lower()  # e.g. hl-pash-001
            sku_code = legacy_code.upper()
            guild_key = p["guild"].strip().lower()
            cat = cat_cache[guild_key]
            artisan_user, seller = artisan_entities[p["artisan"].strip().lower()]

            prod_uuid = stable_uuid("product", legacy_code)
            variant_uuid = stable_uuid("variant", legacy_code)
            listing_uuid = stable_uuid("listing", legacy_code)
            image_uuid = stable_uuid("product_image", legacy_code)

            prod_slug = f"{slugify(p['title'])}-{legacy_code}"[:240]
            price_dec = Decimal(str(p["price"])).quantize(Decimal("0.01"))
            mrp_dec = Decimal(str(max(p.get("mrp") or p["price"], p["price"]))).quantize(Decimal("0.01"))
            orig_dec = Decimal(str(max(p.get("originalPrice") or mrp_dec, mrp_dec))).quantize(Decimal("0.01"))

            attrs = {
                "legacy_code": legacy_code,
                "guild": guild_key,
                "guild_label": p.get("guildLabel"),
                "technique": p.get("technique"),
                "gi_id": p.get("giId"),
                "gi_level": int(p.get("giLevel") or 3),
                "purity_metric": p.get("purityMetric"),
                "loom_hours": int(p.get("loomHours") or 0),
                "dimensions": p.get("dimensions"),
                "rating": float(p.get("rating") or 4.9),
                "review_count": int(p.get("reviewCount") or 0),
                "original_price": str(orig_dec),
                "image": p["image"],
            }

            prod = (
                db.scalar(select(Product).where(Product.id == prod_uuid))
                or db.scalar(select(Product).where(Product.sku_root == sku_code))
                or db.scalar(select(Product).where(Product.slug == prod_slug))
            )
            if prod is None:
                prod = Product(
                    id=prod_uuid,
                    category_id=cat.id,
                    created_by_user_id=artisan_user.id,
                    sku_root=sku_code,
                    name=p["title"][:220],
                    slug=prod_slug,
                    short_description=(p.get("description") or "")[:480],
                    description=p.get("description") or "",
                    craft_technique=p.get("technique") or guild_key,
                    origin_district=p.get("district") or seller.workshop_district,
                    material_composition=(p.get("purityMetric") or "")[:255],
                    gi_status="GI_VERIFIED" if int(p.get("giLevel") or 0) >= 2 else "UNVERIFIED",
                    approval_status="APPROVED",
                    attributes_json=attrs,
                    is_active=True,
                )
                db.add(prod)
                db.flush()
            else:
                prod.category_id = cat.id
                prod.created_by_user_id = artisan_user.id
                prod.name = p["title"][:220]
                prod.short_description = (p.get("description") or "")[:480]
                prod.description = p.get("description") or ""
                prod.craft_technique = p.get("technique") or guild_key
                prod.origin_district = p.get("district") or seller.workshop_district
                prod.material_composition = (p.get("purityMetric") or "")[:255]
                prod.gi_status = "GI_VERIFIED" if int(p.get("giLevel") or 0) >= 2 else "UNVERIFIED"
                prod.approval_status = "APPROVED"
                prod.attributes_json = attrs
                prod.is_active = True
                db.flush()

            variant_sku = f"{sku_code}-V1"
            variant = (
                db.scalar(select(ProductVariant).where(ProductVariant.id == variant_uuid))
                or db.scalar(select(ProductVariant).where(ProductVariant.variant_sku == variant_sku))
            )
            if variant is None:
                variant = ProductVariant(
                    id=variant_uuid,
                    product_id=prod.id,
                    variant_sku=variant_sku,
                    variant_name=(p.get("dimensions") or "Standard Heirloom Edition")[:160],
                    base_mrp=orig_dec,
                    currency_code="INR",
                    is_active=True,
                )
                db.add(variant)
                db.flush()
            else:
                variant.product_id = prod.id
                variant.variant_name = (p.get("dimensions") or "Standard Heirloom Edition")[:160]
                variant.base_mrp = orig_dec
                variant.is_active = True
                db.flush()

            p_img = db.scalar(
                select(ProductImage).where(
                    ProductImage.product_id == prod.id,
                    ProductImage.is_primary == True,  # noqa: E712
                )
            )
            if p_img is None:
                db.add(
                    ProductImage(
                        id=image_uuid,
                        product_id=prod.id,
                        product_variant_id=variant.id,
                        storage_key=p["image"],
                        alt_text=p["title"][:255],
                        sort_order=0,
                        is_primary=True,
                    )
                )
            else:
                p_img.storage_key = p["image"]
                p_img.alt_text = p["title"][:255]
            db.flush()

            listing = (
                db.scalar(select(SellerProductListing).where(SellerProductListing.id == listing_uuid))
                or db.scalar(select(SellerProductListing).where(SellerProductListing.seller_sku == sku_code))
            )
            stock_qty = max(1, int(p.get("stock") or 5))
            if listing is None:
                listing = SellerProductListing(
                    id=listing_uuid,
                    seller_profile_id=seller.id,
                    product_id=prod.id,
                    product_variant_id=variant.id,
                    seller_sku=sku_code,
                    listing_title=p["title"][:220],
                    selling_price=price_dec,
                    compare_at_mrp=orig_dec,
                    currency_code="INR",
                    min_order_qty=1,
                    max_order_qty=stock_qty,
                    listing_status="ACTIVE",
                )
                db.add(listing)
                upserted_listings += 1
            else:
                listing.seller_profile_id = seller.id
                listing.product_id = prod.id
                listing.product_variant_id = variant.id
                listing.listing_title = p["title"][:220]
                listing.selling_price = price_dec
                listing.compare_at_mrp = orig_dec
                listing.max_order_qty = stock_qty
                listing.listing_status = "ACTIVE"
            db.flush()

        db.commit()
        stats = {
            "total_artisans": len(artisan_entities),
            "total_products": len(products_list),
            "new_artisans": upserted_artisans,
            "new_listings": upserted_listings,
        }
        print(
            f"Seeded {dialect_label} DB cleanly: "
            f"{stats['total_artisans']} verified artisans (unique UUIDs), "
            f"{stats['total_products']} active craft listings (unique UUIDs)."
        )
        return stats

    if owns_engine:
        with db_ctx as db:
            return _run(db)
    return _run(db_ctx)


def seed() -> dict[str, int]:
    """Alias for `seed_artisans_and_catalog()` used by `setup_mysql_and_sync.py`."""
    return seed_artisans_and_catalog()


if __name__ == "__main__":
    seed_artisans_and_catalog()
