"""CraftProof Digital Craft Passport, Claims, Evidence & Verification Service.

Core Trust Invariant:
  - Sellers can only declare claims (`SELLER_DECLARED`) and submit evidence (`EVIDENCE_SUBMITTED`).
  - Only human Admins (or explicitly recorded third-party registry checks) transition claims to verified states.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.core_models import (
    Category,
    Product,
    ProductImage,
    SellerProductListing,
    SellerProfile,
)
from app.models.craftproof_models import (
    VERIFIED_CLAIM_STATUSES,
    CraftClaimEvidence,
    CraftPassport,
    CraftProductClaim,
    CraftVerificationEvent,
)
from app.models.guardrail_models import FileSecurityScan
from app.modules.craftproof.qr import make_passport_serial
from app.modules.craftproof.schemas import (
    AdminClaimDecisionIn,
    AttachEvidenceIn,
    CreateClaimIn,
    CreatePassportIn,
)

# Deterministic craft labor & physical authenticity guide by category keyword
_CRAFT_PROFILES: dict[str, dict[str, Any]] = {
    "pashmina": {
        "default_days": 45,
        "daily_labor_inr": 380,
        "raw_material_pct": 0.34,
        "middleman_markup_factor": 2.35,
        "physical_checks": [
            "Inspect weave under bright light: genuine handspun Pashmina shows subtle micro-irregularities in yarn thickness unlike uniform power-loom viscose.",
            "Check the fringes: authentic hand-woven shawls have hand-twisted fringes that feel dry, warm, and soft — never slick, glossy, or static-prone.",
            "Feel the warmth-to-weight ratio: real Changthangi cashmere (12–16 microns) feels feather-light yet warms immediately against skin.",
        ],
    },
    "kani": {
        "default_days": 75,
        "daily_labor_inr": 420,
        "raw_material_pct": 0.30,
        "middleman_markup_factor": 2.50,
        "physical_checks": [
            "Turn the shawl over: true Kani weave uses interlocking wooden bobbins (tujis) creating neat, tight color-locked tapestry floats — NOT loose snaggable jacquard threads.",
            "Examine motifs along edges: hand-woven Kani patterns follow the warp/weft grain cleanly without embroidered back-stitching.",
        ],
    },
    "sozni": {
        "default_days": 40,
        "daily_labor_inr": 360,
        "raw_material_pct": 0.32,
        "middleman_markup_factor": 2.30,
        "physical_checks": [
            "Check the reverse of the embroidery: master Kashmiri Sozni needlework is remarkably clean and almost reversible with fine, even needle stitches.",
            "Look for tiny natural stitch variations — machine embroidery shows rigid tension puckering and synthetic sheen.",
        ],
    },
    "walnut": {
        "default_days": 22,
        "daily_labor_inr": 450,
        "raw_material_pct": 0.35,
        "middleman_markup_factor": 2.25,
        "physical_checks": [
            "Inspect carved recesses closely: hand-chiseled Kashmiri walnut shows crisp varied chisel tool marks and deep undercuts impossible on a 3-axis CNC router.",
            "Check wood grain continuity & natural matte wax polish — real seasoned Juglans regia walnut has dark swirling grain rather than painted uniform brown stain.",
        ],
    },
    "carpet": {
        "default_days": 95,
        "daily_labor_inr": 440,
        "raw_material_pct": 0.30,
        "middleman_markup_factor": 2.60,
        "physical_checks": [
            "Flip the carpet and count knots along a 1-inch strip: authentic Kashmiri hand-knotted carpets show individual asymmetrical Persian knots (Farsi Baf) on the reverse.",
            "Verify fringes are extensions of the warp threads running through the rug — never glued or stitched on separately.",
        ],
    },
    "papier": {
        "default_days": 14,
        "daily_labor_inr": 350,
        "raw_material_pct": 0.25,
        "middleman_markup_factor": 2.20,
        "physical_checks": [
            "Tap gently: genuine sakhta papier-mâché (hand-molded paper pulp) feels unexpectedly light yet rigid compared to heavy resin/plastic molds.",
            "Inspect brushwork under magnification: real naqqashi hand-painting shows layered mineral/gold-leaf strokes rather than flat printed decals.",
        ],
    },
    "copper": {
        "default_days": 12,
        "daily_labor_inr": 420,
        "raw_material_pct": 0.38,
        "middleman_markup_factor": 2.10,
        "physical_checks": [
            "Inspect engraved naqqashi grooves: hand-chiseled copper shows crisp light-catching facets and subtle hand-hammered contour inside the vessel.",
            "Check for tin-lining (kalai) inside serving ware such as samovars and bowls, traditional to Kashmiri tram work.",
        ],
    },
    "saffron": {
        "default_days": 10,
        "daily_labor_inr": 400,
        "raw_material_pct": 0.55,
        "middleman_markup_factor": 2.00,
        "physical_checks": [
            "Cold-water float test: real Pampore Mongra saffron stigmas slowly release golden-yellow color over 10–15 minutes while keeping their deep crimson shape; dyed fakes bleed red instantly.",
            "Aroma & shape: trumpet-shaped deep crimson strands with earthy honey-hay aroma and bitter-floral taste (never sweet).",
        ],
    },
    "default": {
        "default_days": 18,
        "daily_labor_inr": 380,
        "raw_material_pct": 0.32,
        "middleman_markup_factor": 2.25,
        "physical_checks": [
            "Inspect fine craft details for organic hand-made variations rather than identical factory mold seams.",
            "Cross-check the Craft Passport code on the physical tag against the live HunarLink verification timeline.",
        ],
    },
}


def _match_craft_profile(text_blob: str) -> dict[str, Any]:
    low = (text_blob or "").lower()
    for key in ("kani", "sozni", "pashmina", "walnut", "carpet", "papier", "copper", "saffron"):
        if key in low:
            return _CRAFT_PROFILES[key]
    return _CRAFT_PROFILES["default"]


def build_fair_craft_breakdown(
    *,
    selling_price_inr: float,
    craft_text: str,
    craft_days: int | None = None,
    origin_location: str | None = None,
) -> dict[str, Any]:
    """Deterministic Fair-Craft Value Breakdown explaining why genuine handmade costs what it does."""
    profile = _match_craft_profile(craft_text)
    price = max(float(selling_price_inr or 0), 100.0)
    days = craft_days if (craft_days and craft_days > 0) else int(profile["default_days"])

    # Keep days economically consistent if not explicitly provided
    if craft_days is None:
        estimated_from_price = max(3, min(180, round((price * 0.62) / float(profile["daily_labor_inr"]))))
        days = max(3, round((days + estimated_from_price) / 2))

    raw_materials_inr = round(price * float(profile["raw_material_pct"]))
    platform_logistics_inr = round(price * 0.08)
    artisan_labor_inr = max(100, round(price - raw_materials_inr - platform_logistics_inr))
    implied_daily_earning_inr = max(150, round(artisan_labor_inr / max(days, 1)))
    estimated_retail_with_middlemen = round(price * float(profile["middleman_markup_factor"]))
    middleman_saved_inr = max(0, estimated_retail_with_middlemen - round(price))

    return {
        "selling_price_inr": round(price),
        "estimated_craft_days": days,
        "artisan_labor_share_inr": artisan_labor_inr,
        "raw_materials_loom_inr": raw_materials_inr,
        "logistics_verification_inr": platform_logistics_inr,
        "implied_daily_craft_earning_inr": implied_daily_earning_inr,
        "estimated_middleman_retail_inr": estimated_retail_with_middlemen,
        "middleman_markup_avoided_inr": middleman_saved_inr,
        "direct_to_artisan_pct": round(((artisan_labor_inr + raw_materials_inr) / price) * 100, 1),
        "fairness_summary": (
            f"Approx. {days} artisan work-days in {origin_location or 'Jammu & Kashmir'} "
            f"(~INR {implied_daily_earning_inr:,}/day craft labor + raw materials, "
            f"saving ~INR {middleman_saved_inr:,} vs typical 3-tier middleman retail)."
        ),
        "physical_inspection_guide": profile["physical_checks"],
    }


def compute_overall_trust_level(claims: list[CraftProductClaim]) -> str:
    """Deterministically derive passport overall trust badge from its atomic claims."""
    if not claims:
        return "SELLER_DECLARED"
    statuses = {c.verification_status for c in claims}
    if "THIRD_PARTY_VERIFIED" in statuses:
        return "THIRD_PARTY_VERIFIED"
    if "HUMAN_VERIFIED" in statuses:
        return "HUMAN_VERIFIED"
    if "UNDER_REVIEW" in statuses:
        return "UNDER_REVIEW"
    if "EVIDENCE_SUBMITTED" in statuses:
        return "EVIDENCE_SUBMITTED"
    if statuses == {"REJECTED"}:
        return "REJECTED"
    if statuses == {"NOT_ESTABLISHED"}:
        return "NOT_ESTABLISHED"
    return "SELLER_DECLARED"


def _make_passport_code(listing_id: str, sku: str | None = None) -> str:
    digest = hashlib.sha256(f"{listing_id}:{sku or ''}".encode("utf-8")).hexdigest().upper()
    return f"HL-CP-{digest[:8]}"


def _slugify(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (value or "craft").lower()).strip("-")
    return s[:180] or "craft"


def _extract_loom_days(product: Product) -> int | None:
    attrs = product.attributes_json or {}
    for key in ("craft_days", "days", "loom_days"):
        val = attrs.get(key)
        if isinstance(val, (int, float)) and val > 0:
            return int(val)
    hours = attrs.get("loom_hours") or attrs.get("hours")
    if isinstance(hours, (int, float)) and hours > 0:
        return max(1, round(float(hours) / 8.0))
    return None


def ensure_passport_for_listing(
    db: Session,
    *,
    listing: SellerProductListing,
    product: Product | None = None,
    seller: SellerProfile | None = None,
    actor_user_id: str | None = None,
    custom_input: CreatePassportIn | None = None,
    preserve_existing_gi_verification: bool = False,
) -> CraftPassport:
    """Return existing CraftPassport for listing or create an honest SELLER_DECLARED passport."""
    existing = db.scalar(select(CraftPassport).where(CraftPassport.listing_id == listing.id))
    if existing is not None:
        return existing

    if product is None:
        product = db.scalar(select(Product).where(Product.id == listing.product_id))
    if seller is None:
        seller = db.scalar(select(SellerProfile).where(SellerProfile.id == listing.seller_profile_id))
    if product is None or seller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing product or artisan profile not found.",
        )

    passport_code = _make_passport_code(listing.id, listing.seller_sku)
    public_slug = f"{_slugify(product.slug or listing.listing_title)}-{passport_code[-6:].lower()}"
    serial_number = make_passport_serial(passport_code, listing.id)

    origin_loc = (
        (custom_input.origin_location if custom_input and custom_input.origin_location else None)
        or product.origin_district
        or seller.workshop_district
        or "Jammu & Kashmir"
    )
    materials = (
        (custom_input.materials_summary if custom_input and custom_input.materials_summary else None)
        or product.material_composition
        or "Artisan-declared heritage craft material"
    )
    process = (
        (custom_input.manufacturing_process if custom_input and custom_input.manufacturing_process else None)
        or product.craft_technique
        or seller.craft_specialty
        or "Traditional hand-crafted workshop process"
    )
    days = (
        (custom_input.craft_days_estimated if custom_input and custom_input.craft_days_estimated else None)
        or _extract_loom_days(product)
    )
    story = (
        (custom_input.artisan_story if custom_input and custom_input.artisan_story else None)
        or seller.bio
        or product.short_description
        or product.description
    )

    craft_blob = f"{product.name} {process} {materials} {seller.craft_specialty or ''}"
    fair_breakdown = build_fair_craft_breakdown(
        selling_price_inr=float(listing.selling_price),
        craft_text=craft_blob,
        craft_days=days,
        origin_location=origin_loc,
    )

    passport = CraftPassport(
        passport_code=passport_code,
        listing_id=listing.id,
        product_id=product.id,
        seller_profile_id=seller.id,
        public_slug=public_slug,
        serial_number=serial_number,
        overall_trust_level="SELLER_DECLARED",
        materials_summary=materials,
        manufacturing_process=process,
        origin_location=origin_loc,
        craft_days_estimated=fair_breakdown["estimated_craft_days"],
        artisan_story=story,
        fair_craft_breakdown_json=fair_breakdown,
        is_public=True,
    )
    db.add(passport)
    db.flush()

    # Build atomic claims — strictly SELLER_DECLARED unless backfill preserves pre-verified GI registry records
    claims_to_create: list[tuple[str, str, str, str, str | None]] = []
    if custom_input and custom_input.claims:
        for c in custom_input.claims:
            claims_to_create.append(
                (c.claim_type, c.claim_title, c.claim_value, "SELLER_DECLARED", None)
            )
    else:
        claims_to_create.append(("MATERIAL", "Primary Material", materials, "SELLER_DECLARED", None))
        claims_to_create.append(("ORIGIN", "Craft Origin Cluster", origin_loc, "SELLER_DECLARED", None))
        claims_to_create.append(("TECHNIQUE", "Craft Technique", process, "SELLER_DECLARED", None))
        claims_to_create.append(
            (
                "HANDMADE",
                "Handmade Production Effort",
                f"Estimated {fair_breakdown['estimated_craft_days']} artisan work-days at {seller.store_name}",
                "SELLER_DECLARED",
                None,
            )
        )
        gi_code = (
            (product.attributes_json or {}).get("gi_code")
            or seller.claimed_gi_authorized_user_no
        )
        if gi_code:
            gi_verified = (
                preserve_existing_gi_verification
                and product.gi_status == "VERIFIED"
                and seller.verification_status == "APPROVED"
                and seller.verification_path == "GI"
            )
            claims_to_create.append(
                (
                    "GI_TAG",
                    "Geographical Indication (GI) Registration",
                    f"GI Authorized Code: {gi_code}",
                    "THIRD_PARTY_VERIFIED" if gi_verified else "SELLER_DECLARED",
                    "Craft Development Institute / GI Registry Seed" if gi_verified else None,
                )
            )

    created_claims: list[CraftProductClaim] = []
    now = utcnow()
    for c_type, c_title, c_val, c_status, authority in claims_to_create:
        claim = CraftProductClaim(
            passport_id=passport.id,
            claim_type=c_type,
            claim_title=c_title,
            claim_value=c_val,
            claim_source="THIRD_PARTY_IMPORT" if c_status == "THIRD_PARTY_VERIFIED" else "SELLER_DECLARED",
            verification_status=c_status,
            verified_by_authority=authority,
            verified_at=now if c_status in VERIFIED_CLAIM_STATUSES else None,
            decision_notes=(
                "Synced from approved HunarLink GI Artisan record."
                if c_status == "THIRD_PARTY_VERIFIED"
                else None
            ),
        )
        db.add(claim)
        created_claims.append(claim)
    db.flush()

    passport.overall_trust_level = compute_overall_trust_level(created_claims)
    db.add(
        CraftVerificationEvent(
            passport_id=passport.id,
            claim_id=None,
            event_type="PASSPORT_CREATED",
            from_status=None,
            to_status=passport.overall_trust_level,
            actor_type="SELLER" if actor_user_id else "SYSTEM",
            actor_user_id=actor_user_id,
            summary=f"Digital Craft Passport {passport.passport_code} created with {len(created_claims)} atomic craft claims.",
            metadata_json={"claim_count": len(created_claims), "listing_id": listing.id},
            is_legal_proof=False,
        )
    )
    for cl in created_claims:
        if cl.verification_status == "THIRD_PARTY_VERIFIED":
            db.add(
                CraftVerificationEvent(
                    passport_id=passport.id,
                    claim_id=cl.id,
                    event_type="THIRD_PARTY_RECORDED",
                    from_status="SELLER_DECLARED",
                    to_status="THIRD_PARTY_VERIFIED",
                    actor_type="THIRD_PARTY",
                    actor_user_id=None,
                    summary=f"Existing GI record linked for '{cl.claim_title}' ({cl.claim_value}).",
                    metadata_json={"authority": cl.verified_by_authority},
                    is_legal_proof=True,
                )
            )
    db.flush()
    return passport


def add_seller_claim(
    db: Session,
    *,
    passport: CraftPassport,
    seller_user_id: str,
    payload: CreateClaimIn,
) -> CraftProductClaim:
    """Seller declares a new atomic claim — ALWAYS initialized as SELLER_DECLARED."""
    claim = CraftProductClaim(
        passport_id=passport.id,
        claim_type=payload.claim_type,
        claim_title=payload.claim_title.strip(),
        claim_value=payload.claim_value.strip(),
        claim_source="SELLER_DECLARED",
        verification_status="SELLER_DECLARED",
    )
    db.add(claim)
    db.flush()

    db.add(
        CraftVerificationEvent(
            passport_id=passport.id,
            claim_id=claim.id,
            event_type="CLAIM_DECLARED",
            from_status=None,
            to_status="SELLER_DECLARED",
            actor_type="SELLER",
            actor_user_id=seller_user_id,
            summary=f"Artisan declared {claim.claim_type} claim: '{claim.claim_title}' = '{claim.claim_value}'.",
            metadata_json={"claim_type": claim.claim_type},
            is_legal_proof=False,
        )
    )
    db.flush()
    return claim


def attach_claim_evidence(
    db: Session,
    *,
    claim: CraftProductClaim,
    passport: CraftPassport,
    uploader_user_id: str,
    payload: AttachEvidenceIn,
) -> CraftClaimEvidence:
    """Attach scanned evidence file or reference URL; transitions SELLER_DECLARED -> EVIDENCE_SUBMITTED."""
    if not payload.file_scan_id and not payload.external_reference_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either a scanned file (`file_scan_id`) or `external_reference_url`.",
        )

    storage_key = None
    original_filename = None
    sha256_hash = None
    if payload.file_scan_id:
        scan = db.scalar(select(FileSecurityScan).where(FileSecurityScan.id == payload.file_scan_id))
        if scan is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referenced uploaded evidence scan was not found.",
            )
        if scan.uploader_user_id != uploader_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only attach evidence files uploaded by your own account.",
            )
        storage_key = scan.storage_key
        original_filename = scan.original_filename
        sha256_hash = scan.sha256_hash

    evidence = CraftClaimEvidence(
        claim_id=claim.id,
        passport_id=passport.id,
        evidence_type=payload.evidence_type,
        file_scan_id=payload.file_scan_id,
        storage_key=storage_key,
        original_filename=original_filename,
        external_reference_url=payload.external_reference_url,
        sha256_hash=sha256_hash,
        caption=payload.caption,
        uploaded_by_user_id=uploader_user_id,
    )
    db.add(evidence)

    prev_status = claim.verification_status
    if claim.verification_status in ("SELLER_DECLARED", "NOT_ESTABLISHED", "REJECTED"):
        claim.verification_status = "EVIDENCE_SUBMITTED"
        claim.updated_at = utcnow()

    db.flush()
    all_claims = list(
        db.scalars(select(CraftProductClaim).where(CraftProductClaim.passport_id == passport.id)).all()
    )
    passport.overall_trust_level = compute_overall_trust_level(all_claims)
    passport.updated_at = utcnow()

    db.add(
        CraftVerificationEvent(
            passport_id=passport.id,
            claim_id=claim.id,
            event_type="EVIDENCE_ATTACHED",
            from_status=prev_status,
            to_status=claim.verification_status,
            actor_type="SELLER",
            actor_user_id=uploader_user_id,
            summary=(
                f"Evidence ({payload.evidence_type}) attached to '{claim.claim_title}'"
                + (f" [{original_filename}]" if original_filename else "")
                + ". Awaiting human verification."
            ),
            metadata_json={
                "evidence_id": evidence.id,
                "evidence_type": payload.evidence_type,
                "sha256_hash": sha256_hash,
            },
            is_legal_proof=False,
        )
    )
    db.flush()
    return evidence


def apply_human_admin_decision(
    db: Session,
    *,
    claim: CraftProductClaim,
    admin_user_id: str,
    payload: AdminClaimDecisionIn,
) -> tuple[CraftProductClaim, CraftPassport]:
    """Human Admin verification decision — the ONLY authorized path to HUMAN/THIRD_PARTY_VERIFIED."""
    passport = db.scalar(select(CraftPassport).where(CraftPassport.id == claim.passport_id))
    if passport is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passport not found.")

    prev_status = claim.verification_status
    claim.verification_status = payload.decision_status
    claim.verified_by_user_id = admin_user_id
    claim.verified_by_authority = (
        payload.verified_by_authority
        or (
            "HunarLink Human Verification Desk"
            if payload.decision_status == "HUMAN_VERIFIED"
            else payload.verified_by_authority
        )
    )
    claim.decision_notes = payload.decision_notes.strip()
    claim.verified_at = utcnow() if payload.decision_status in VERIFIED_CLAIM_STATUSES else None
    claim.updated_at = utcnow()

    db.flush()
    all_claims = list(
        db.scalars(select(CraftProductClaim).where(CraftProductClaim.passport_id == passport.id)).all()
    )
    passport.overall_trust_level = compute_overall_trust_level(all_claims)
    passport.updated_at = utcnow()

    actor_type = "THIRD_PARTY" if payload.decision_status == "THIRD_PARTY_VERIFIED" else "HUMAN_ADMIN"
    event_type = (
        "THIRD_PARTY_RECORDED"
        if payload.decision_status == "THIRD_PARTY_VERIFIED"
        else "HUMAN_REVIEW_DECISION"
    )
    db.add(
        CraftVerificationEvent(
            passport_id=passport.id,
            claim_id=claim.id,
            event_type=event_type,
            from_status=prev_status,
            to_status=payload.decision_status,
            actor_type=actor_type,
            actor_user_id=admin_user_id,
            summary=(
                f"Human Reviewer set '{claim.claim_title}' to {payload.decision_status}: "
                f"{claim.decision_notes}"
            ),
            metadata_json={
                "verified_by_authority": claim.verified_by_authority,
                **(payload.metadata or {}),
            },
            is_legal_proof=bool(payload.decision_status == "THIRD_PARTY_VERIFIED"),
        )
    )
    db.flush()
    return claim, passport


def serialize_passport_public(
    db: Session,
    passport: CraftPassport,
    *,
    api_prefix: str = "/api/v1",
    signature_valid: bool | None = None,
    include_qr_signature: str | None = None,
) -> dict[str, Any]:
    """Return full public Craft Passport clearly separating Verified Facts vs Artisan Declarations."""
    serial_number = passport.serial_number or make_passport_serial(
        passport.passport_code, passport.listing_id
    )
    product = db.scalar(select(Product).where(Product.id == passport.product_id))
    listing = db.scalar(select(SellerProductListing).where(SellerProductListing.id == passport.listing_id))
    seller = db.scalar(select(SellerProfile).where(SellerProfile.id == passport.seller_profile_id))
    category = (
        db.scalar(select(Category).where(Category.id == product.category_id))
        if product is not None
        else None
    )
    primary_img = (
        db.scalar(
            select(ProductImage)
            .where(ProductImage.product_id == product.id)
            .order_by(ProductImage.is_primary.desc(), ProductImage.sort_order.asc())
        )
        if product is not None
        else None
    )

    claims = list(
        db.scalars(
            select(CraftProductClaim)
            .where(CraftProductClaim.passport_id == passport.id)
            .order_by(CraftProductClaim.created_at.asc())
        ).all()
    )
    evidences = list(
        db.scalars(
            select(CraftClaimEvidence)
            .where(CraftClaimEvidence.passport_id == passport.id)
            .order_by(CraftClaimEvidence.created_at.asc())
        ).all()
    )
    events = list(
        db.scalars(
            select(CraftVerificationEvent)
            .where(CraftVerificationEvent.passport_id == passport.id)
            .order_by(CraftVerificationEvent.created_at.desc())
        ).all()
    )

    evidence_by_claim: dict[str, list[dict[str, Any]]] = {}
    for ev in evidences:
        evidence_by_claim.setdefault(ev.claim_id, []).append(
            {
                "evidence_id": ev.id,
                "evidence_type": ev.evidence_type,
                "original_filename": ev.original_filename,
                "external_reference_url": ev.external_reference_url,
                "sha256_hash": ev.sha256_hash,
                "caption": ev.caption,
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
            }
        )

    serialized_claims: list[dict[str, Any]] = []
    verified_claims: list[dict[str, Any]] = []
    unverified_claims: list[dict[str, Any]] = []

    for cl in claims:
        is_verified = cl.verification_status in VERIFIED_CLAIM_STATUSES
        item = {
            "claim_id": cl.id,
            "claim_type": cl.claim_type,
            "claim_title": cl.claim_title,
            "claim_value": cl.claim_value,
            "claim_source": cl.claim_source,
            "verification_status": cl.verification_status,
            "is_independently_verified": is_verified,
            "verified_by_authority": cl.verified_by_authority,
            "verified_at": cl.verified_at.isoformat() if cl.verified_at else None,
            "decision_notes": cl.decision_notes,
            "evidence": evidence_by_claim.get(cl.id, []),
            "updated_at": cl.updated_at.isoformat() if cl.updated_at else None,
        }
        serialized_claims.append(item)
        if is_verified:
            verified_claims.append(item)
        else:
            unverified_claims.append(item)

    overall_trust = compute_overall_trust_level(claims)
    fair_craft = passport.fair_craft_breakdown_json or build_fair_craft_breakdown(
        selling_price_inr=float(listing.selling_price) if listing else 0.0,
        craft_text=f"{product.name if product else ''} {passport.manufacturing_process or ''}",
        craft_days=passport.craft_days_estimated,
        origin_location=passport.origin_location,
    )

    payload_out = {
        "passport_id": passport.id,
        "passport_code": passport.passport_code,
        "serial_number": serial_number,
        "public_slug": passport.public_slug,
        "public_url_path": f"/passport/{passport.passport_code}",
        "qr_svg_url": f"{api_prefix}/passports/{passport.passport_code}/qr.svg",
        "scan_telemetry": {
            "scan_count": int(getattr(passport, "scan_count", 0) or 0),
            "first_scanned_at": (
                passport.first_scanned_at.isoformat()
                if getattr(passport, "first_scanned_at", None)
                else None
            ),
        },
        "qr_verification": {
            "signature_checked": signature_valid is not None,
            "signature_valid": signature_valid,
            "status": (
                "SIGNED_VALID"
                if signature_valid is True
                else ("SIGNATURE_MISMATCH" if signature_valid is False else "PUBLIC_LOOKUP")
            ),
        },
        "overall_trust_level": overall_trust,
        "trust_disclosure": (
            "This Digital Craft Passport explicitly separates Seller-Declared statements "
            "from Human-Verified or Third-Party Verified facts. Verification is granted "
            "strictly by Human Administrators or recorded third-party authorities."
        ),
        "summary_counts": {
            "total_claims": len(serialized_claims),
            "verified_count": len(verified_claims),
            "unverified_count": len(unverified_claims),
            "evidence_count": len(evidences),
        },
        "product": {
            "product_id": product.id if product else passport.product_id,
            "listing_id": listing.id if listing else passport.listing_id,
            "name": product.name if product else (listing.listing_title if listing else "Craft"),
            "slug": product.slug if product else None,
            "category_name": category.name if category else None,
            "category_slug": category.slug if category else None,
            "selling_price_inr": float(listing.selling_price) if listing else None,
            "compare_at_mrp_inr": float(listing.compare_at_mrp) if (listing and listing.compare_at_mrp) else None,
            "image_url": primary_img.storage_key if primary_img else None,
            "gi_status": product.gi_status if product else None,
            "materials_summary": passport.materials_summary,
            "manufacturing_process": passport.manufacturing_process,
            "origin_location": passport.origin_location,
            "craft_days_estimated": passport.craft_days_estimated,
        },
        "artisan": {
            "seller_profile_id": seller.id if seller else passport.seller_profile_id,
            "store_name": seller.store_name if seller else None,
            "store_slug": seller.store_slug if seller else None,
            "craft_specialty": seller.craft_specialty if seller else None,
            "workshop_district": seller.workshop_district if seller else None,
            "verification_path": seller.verification_path if seller else None,
            "verification_status": seller.verification_status if seller else None,
            "claimed_gi_code": seller.claimed_gi_authorized_user_no if seller else None,
            "story": passport.artisan_story,
        },
        "verified_claims": verified_claims,
        "unverified_claims": unverified_claims,
        "all_claims": serialized_claims,
        "fair_craft_breakdown": fair_craft,
        "verification_timeline": [
            {
                "event_id": ev.id,
                "claim_id": ev.claim_id,
                "event_type": ev.event_type,
                "from_status": ev.from_status,
                "to_status": ev.to_status,
                "actor_type": ev.actor_type,
                "summary": ev.summary,
                "is_legal_proof": bool(ev.is_legal_proof),
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
            }
            for ev in events
        ],
        "created_at": passport.created_at.isoformat() if passport.created_at else None,
        "updated_at": passport.updated_at.isoformat() if passport.updated_at else None,
    }
    if include_qr_signature:
        payload_out["qr_signature"] = include_qr_signature
        payload_out["signed_passport_url_path"] = (
            f"/passport/{passport.passport_code}?sig={include_qr_signature}"
        )
    return payload_out


def resolve_passport_by_code_or_slug(db: Session, code_or_slug: str) -> CraftPassport | None:
    needle = code_or_slug.strip()
    return db.scalar(
        select(CraftPassport).where(
            or_(
                CraftPassport.passport_code == needle,
                CraftPassport.public_slug == needle,
            )
        )
    )


def resolve_or_create_passport_by_product(db: Session, product_ref: str) -> CraftPassport | None:
    """Resolve CraftPassport by product_id, product slug, listing_id, or SKU (lazy-creating if needed)."""
    needle = product_ref.strip()
    listing = db.scalar(
        select(SellerProductListing).where(
            or_(
                SellerProductListing.id == needle,
                SellerProductListing.product_id == needle,
                SellerProductListing.seller_sku == needle,
            )
        )
    )
    if listing is None:
        product = db.scalar(
            select(Product).where(
                or_(Product.id == needle, Product.slug == needle, Product.sku_root == needle)
            )
        )
        if product is not None:
            listing = db.scalar(
                select(SellerProductListing).where(SellerProductListing.product_id == product.id)
            )
    if listing is None:
        return None
    passport = ensure_passport_for_listing(
        db,
        listing=listing,
        preserve_existing_gi_verification=True,
    )
    db.commit()
    return passport
