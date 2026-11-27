"""FastAPI Router for CraftProof Digital Craft Passports, Claims, Evidence & QR Codes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthenticatedPrincipal,
    get_current_principal,
    require_platform_role,
)
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models.core_models import Product, SellerProductListing, SellerProfile
from app.models.craftproof_models import (
    CraftClaimEvidence,
    CraftPassport,
    CraftProductClaim,
)
from app.modules.craftproof.qr import generate_passport_qr_svg
from app.modules.craftproof.schemas import (
    AdminClaimDecisionIn,
    AttachEvidenceIn,
    CreateClaimIn,
    CreatePassportIn,
)
from app.modules.craftproof.service import (
    add_seller_claim,
    apply_human_admin_decision,
    attach_claim_evidence,
    ensure_passport_for_listing,
    resolve_or_create_passport_by_product,
    resolve_passport_by_code_or_slug,
    serialize_passport_public,
)

router = APIRouter(tags=["CraftProof Passports"])


# ---------------------------------------------------------------------------
# Public Craft Passport & QR Endpoints (Zero Login Required for QR Scanning!)
# ---------------------------------------------------------------------------
@router.get("/passports/lookup")
def lookup_passports(
    q: str = Query(min_length=1, max_length=120),
    limit: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Live DB search across Craft Passports by passport code, GI code, product name, or artisan."""
    needle = f"%{q.strip()}%"
    passports = list(
        db.scalars(
            select(CraftPassport)
            .join(Product, Product.id == CraftPassport.product_id)
            .join(SellerProfile, SellerProfile.id == CraftPassport.seller_profile_id)
            .where(
                CraftPassport.is_public == True,  # noqa: E712
                or_(
                    CraftPassport.passport_code.ilike(needle),
                    CraftPassport.public_slug.ilike(needle),
                    Product.name.ilike(needle),
                    Product.slug.ilike(needle),
                    Product.sku_root.ilike(needle),
                    SellerProfile.store_name.ilike(needle),
                    SellerProfile.claimed_gi_authorized_user_no.ilike(needle),
                ),
            )
            .limit(limit)
        ).all()
    )

    # Also match claim values (e.g., GI registration code typed in GiVerifyModal)
    if len(passports) < limit:
        claim_passport_ids = list(
            db.scalars(
                select(CraftProductClaim.passport_id)
                .where(CraftProductClaim.claim_value.ilike(needle))
                .limit(limit)
            ).all()
        )
        seen = {p.id for p in passports}
        for pid in claim_passport_ids:
            if pid not in seen:
                p = db.scalar(select(CraftPassport).where(CraftPassport.id == pid))
                if p and p.is_public:
                    passports.append(p)
                    seen.add(pid)

    items = [
        serialize_passport_public(db, p, api_prefix=settings.api_v1_prefix)
        for p in passports[:limit]
    ]
    return {"query": q.strip(), "count": len(items), "items": items}


@router.get("/passports/by-product/{product_ref}")
def get_passport_by_product(
    product_ref: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Resolve (or lazily initialize) the public Craft Passport for any product or listing."""
    passport = resolve_or_create_passport_by_product(db, product_ref)
    if passport is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No product or Craft Passport found for this identifier.",
        )
    return serialize_passport_public(db, passport, api_prefix=settings.api_v1_prefix)


@router.get("/passports/{code_or_slug}/qr.svg")
def get_passport_qr_svg(
    code_or_slug: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Return a scannable SVG QR code linking straight to the public Craft Passport page."""
    passport = resolve_passport_by_code_or_slug(db, code_or_slug)
    if passport is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Craft Passport not found.")

    base = (settings.frontend_base_url or "http://localhost:5173").rstrip("/")
    passport_url = f"{base}/passport/{passport.passport_code}"
    svg_bytes = generate_passport_qr_svg(passport_url)
    return Response(
        content=svg_bytes,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/passports/{code_or_slug}")
def get_passport_public(
    code_or_slug: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Public Craft Passport endpoint separating verified facts from artisan declarations."""
    passport = resolve_passport_by_code_or_slug(db, code_or_slug)
    if passport is None or not passport.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Craft Passport not found.",
        )
    return serialize_passport_public(db, passport, api_prefix=settings.api_v1_prefix)


# ---------------------------------------------------------------------------
# Seller Endpoints (Declare Claims & Attach Evidence — NEVER Self-Verify!)
# ---------------------------------------------------------------------------
@router.post("/seller/passports/for-listing/{listing_id}", status_code=status.HTTP_201_CREATED)
def create_or_get_seller_passport(
    listing_id: str,
    payload: CreatePassportIn | None = None,
    principal: AuthenticatedPrincipal = Depends(
        require_platform_role("DIRECT_SELLER", "ADMIN")
    ),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Create or retrieve a Craft Passport for a seller's listing (all new claims = SELLER_DECLARED)."""
    listing = db.scalar(select(SellerProductListing).where(SellerProductListing.id == listing_id))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found.")

    seller = db.scalar(select(SellerProfile).where(SellerProfile.id == listing.seller_profile_id))
    if not principal.is_active_admin and (seller is None or seller.user_id != principal.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage Craft Passports for your own listings.",
        )

    passport = ensure_passport_for_listing(
        db,
        listing=listing,
        seller=seller,
        actor_user_id=principal.user_id,
        custom_input=payload,
        preserve_existing_gi_verification=False,
    )
    db.commit()
    return serialize_passport_public(db, passport, api_prefix=settings.api_v1_prefix)


@router.post("/seller/passports/{passport_id}/claims", status_code=status.HTTP_201_CREATED)
def create_seller_claim(
    passport_id: str,
    payload: CreateClaimIn,
    principal: AuthenticatedPrincipal = Depends(
        require_platform_role("DIRECT_SELLER", "ADMIN")
    ),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Add a new SELLER_DECLARED craft claim to a seller's own Craft Passport."""
    passport = db.scalar(select(CraftPassport).where(CraftPassport.id == passport_id))
    if passport is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passport not found.")
    seller = db.scalar(select(SellerProfile).where(SellerProfile.id == passport.seller_profile_id))
    if not principal.is_active_admin and (seller is None or seller.user_id != principal.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your Craft Passport.")

    claim = add_seller_claim(
        db,
        passport=passport,
        seller_user_id=principal.user_id,
        payload=payload,
    )
    db.commit()
    return {
        "claim_id": claim.id,
        "verification_status": claim.verification_status,
        "passport": serialize_passport_public(db, passport, api_prefix=settings.api_v1_prefix),
    }


@router.post("/seller/passports/claims/{claim_id}/evidence", status_code=status.HTTP_201_CREATED)
def upload_seller_claim_evidence(
    claim_id: str,
    payload: AttachEvidenceIn,
    principal: AuthenticatedPrincipal = Depends(
        require_platform_role("DIRECT_SELLER", "ADMIN")
    ),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Attach supporting evidence to a craft claim (transitions to EVIDENCE_SUBMITTED for Admin review)."""
    claim = db.scalar(select(CraftProductClaim).where(CraftProductClaim.id == claim_id))
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
    passport = db.scalar(select(CraftPassport).where(CraftPassport.id == claim.passport_id))
    if passport is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passport not found.")
    seller = db.scalar(select(SellerProfile).where(SellerProfile.id == passport.seller_profile_id))
    if not principal.is_active_admin and (seller is None or seller.user_id != principal.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owning artisan can submit evidence for this claim.",
        )

    ev = attach_claim_evidence(
        db,
        claim=claim,
        passport=passport,
        uploader_user_id=principal.user_id,
        payload=payload,
    )
    db.commit()
    return {
        "evidence_id": ev.id,
        "claim_id": claim.id,
        "verification_status": claim.verification_status,
        "passport": serialize_passport_public(db, passport, api_prefix=settings.api_v1_prefix),
    }


# ---------------------------------------------------------------------------
# Human Admin Claim Verification Endpoints (Sole Authority to Verify Claims)
# ---------------------------------------------------------------------------
@router.get("/admin/passports/claims")
def admin_list_craft_claims(
    status_filter: str | None = Query(default=None),
    limit: int = Query(default=60, ge=1, le=200),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Admin review queue for CraftProof product claims and evidence hashes."""
    if not principal.is_active_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to review CraftProof claims.",
        )

    stmt = (
        select(CraftProductClaim, CraftPassport, Product, SellerProfile)
        .join(CraftPassport, CraftPassport.id == CraftProductClaim.passport_id)
        .join(Product, Product.id == CraftPassport.product_id)
        .join(SellerProfile, SellerProfile.id == CraftPassport.seller_profile_id)
    )
    if status_filter:
        stmt = stmt.where(CraftProductClaim.verification_status == status_filter.upper())
    rows = db.execute(
        stmt.order_by(CraftProductClaim.updated_at.desc()).limit(limit)
    ).all()

    items = []
    for cl, cp, prod, seller in rows:
        evs = list(
            db.scalars(
                select(CraftClaimEvidence).where(CraftClaimEvidence.claim_id == cl.id)
            ).all()
        )
        items.append(
            {
                "claim_id": cl.id,
                "passport_id": cp.id,
                "passport_code": cp.passport_code,
                "product_name": prod.name,
                "product_slug": prod.slug,
                "artisan_store_name": seller.store_name,
                "artisan_district": seller.workshop_district,
                "artisan_verification_path": seller.verification_path,
                "claim_type": cl.claim_type,
                "claim_title": cl.claim_title,
                "claim_value": cl.claim_value,
                "verification_status": cl.verification_status,
                "verified_by_authority": cl.verified_by_authority,
                "decision_notes": cl.decision_notes,
                "evidence_count": len(evs),
                "evidence": [
                    {
                        "evidence_id": e.id,
                        "evidence_type": e.evidence_type,
                        "original_filename": e.original_filename,
                        "external_reference_url": e.external_reference_url,
                        "sha256_hash": e.sha256_hash,
                        "caption": e.caption,
                    }
                    for e in evs
                ],
                "updated_at": cl.updated_at.isoformat() if cl.updated_at else None,
            }
        )
    return {"count": len(items), "items": items}


@router.post("/admin/passports/claims/{claim_id}/decision")
def admin_decide_craft_claim(
    claim_id: str,
    payload: AdminClaimDecisionIn,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Human Admin approves, rejects, or marks a CraftProof claim as third-party verified."""
    if not principal.is_active_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active human Administrators may verify or reject CraftProof claims.",
        )

    claim = db.scalar(select(CraftProductClaim).where(CraftProductClaim.id == claim_id))
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")

    updated_claim, updated_passport = apply_human_admin_decision(
        db,
        claim=claim,
        admin_user_id=principal.user_id,
        payload=payload,
    )
    db.commit()
    return {
        "claim_id": updated_claim.id,
        "verification_status": updated_claim.verification_status,
        "overall_trust_level": updated_passport.overall_trust_level,
        "passport": serialize_passport_public(db, updated_passport, api_prefix=settings.api_v1_prefix),
    }
