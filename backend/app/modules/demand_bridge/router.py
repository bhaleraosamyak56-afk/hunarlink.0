"""FastAPI Router for Demand Bridge (Deterministic Wholesale Brief Parsing & Cluster Matching)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.admin_security import verify_admin_session_token
from app.core.auth import (
    AuthenticatedPrincipal,
    get_token_verifier,
    load_admin_principal_by_user_id,
    load_principal_by_clerk_id,
    require_platform_role,
)
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models.base import utcnow
from app.models.core_models import SellerProfile
from app.models.craftproof_models import BuyerDemandRequest, DemandArtisanMatch
from app.modules.demand_bridge.matcher import match_demand_to_artisans, parse_buyer_brief
from app.modules.demand_bridge.schemas import (
    ArtisanOfferRespondIn,
    DemandMatchIn,
    DemandParseIn,
    DispatchDemandInquiryIn,
)

router = APIRouter(tags=["Demand Bridge"])


def _optional_principal(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedPrincipal | None:
    auth_header = request.headers.get("authorization") or ""
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        admin_claims = verify_admin_session_token(token, settings)
        if admin_claims is not None:
            return load_admin_principal_by_user_id(db, str(admin_claims["sub"]))
        verifier = get_token_verifier(settings)
        claims = verifier.verify(token)
        return load_principal_by_clerk_id(db, str(claims["sub"]))
    except Exception:
        return None


@router.post("/demand-bridge/parse")
def post_parse_demand_brief(
    payload: DemandParseIn,
) -> dict:
    """Step 1: Deterministically parse wholesale brief into structured JSON for buyer confirmation."""
    return parse_buyer_brief(payload.raw_request_text)


@router.post("/demand-bridge/match", status_code=status.HTTP_201_CREATED)
def post_match_demand_bridge(
    payload: DemandMatchIn,
    principal: AuthenticatedPrincipal | None = Depends(_optional_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Step 2: Deterministically score artisans & automatically form Multi-Artisan Cluster when needed."""
    return match_demand_to_artisans(
        db,
        payload=payload,
        buyer_user_id=principal.user_id if principal else None,
    )


@router.post("/demand-bridge/requests/{request_id}/dispatch-inquiries")
def post_dispatch_cluster_inquiries(
    request_id: str,
    payload: DispatchDemandInquiryIn,
    db: Session = Depends(get_db),
) -> dict:
    """Dispatch buyer brief to shortlisted / cluster artisans so offers appear in their Seller Studio."""
    req = db.scalar(select(BuyerDemandRequest).where(BuyerDemandRequest.id == request_id))
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand request not found.")

    if payload.buyer_name:
        req.buyer_name = payload.buyer_name.strip()
    if payload.buyer_email:
        req.buyer_email = payload.buyer_email.strip()

    stmt = select(DemandArtisanMatch).where(DemandArtisanMatch.demand_request_id == req.id)
    if payload.match_ids:
        stmt = stmt.where(DemandArtisanMatch.id.in_(payload.match_ids))
    else:
        # Default: contact all cluster members if cluster formed, else top match
        cluster_rows = list(
            db.scalars(stmt.where(DemandArtisanMatch.is_cluster_member == True)).all()  # noqa: E712
        )
        matches = cluster_rows or list(db.scalars(stmt.order_by(DemandArtisanMatch.match_rank.asc()).limit(1)).all())
    if payload.match_ids:
        matches = list(db.scalars(stmt).all())

    if not matches:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching artisan records found to dispatch.",
        )

    now = utcnow()
    for m in matches:
        if m.match_status in ("SUGGESTED", "SHORTLISTED"):
            m.match_status = "CONTACTED"
            m.updated_at = now
    req.request_status = "INQUIRY_SENT"
    db.commit()

    return {
        "demand_request_id": req.id,
        "request_code": req.request_code,
        "request_status": req.request_status,
        "contacted_count": len(matches),
        "contacted_match_ids": [m.id for m in matches],
    }


@router.get("/demand-bridge/requests")
def list_recent_demand_requests(
    limit: int = 20,
    db: Session = Depends(get_db),
) -> dict:
    """List recent Demand Bridge briefs and cluster allocations (for transparency & Admin visibility)."""
    reqs = list(
        db.scalars(
            select(BuyerDemandRequest)
            .order_by(BuyerDemandRequest.created_at.desc())
            .limit(min(limit, 50))
        ).all()
    )
    items = []
    for r in reqs:
        matches = db.execute(
            select(DemandArtisanMatch, SellerProfile)
            .join(SellerProfile, SellerProfile.id == DemandArtisanMatch.seller_profile_id)
            .where(DemandArtisanMatch.demand_request_id == r.id)
            .order_by(DemandArtisanMatch.match_rank.asc())
        ).all()
        items.append(
            {
                "demand_request_id": r.id,
                "request_code": r.request_code,
                "buyer_name": r.buyer_name,
                "category_slug": r.category_slug,
                "requested_quantity": r.requested_quantity,
                "target_delivery_days": r.target_delivery_days,
                "fulfillment_mode": r.fulfillment_mode,
                "request_status": r.request_status,
                "raw_request_text": r.raw_request_text,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "matches": [
                    {
                        "match_id": m.id,
                        "store_name": s.store_name,
                        "workshop_district": s.workshop_district,
                        "is_cluster_member": bool(m.is_cluster_member),
                        "allocated_quantity": m.allocated_quantity,
                        "match_score": float(m.match_score),
                        "match_status": m.match_status,
                    }
                    for m, s in matches
                ],
            }
        )
    return {"count": len(items), "items": items}


# ---------------------------------------------------------------------------
# Seller Studio: View & Accept/Decline Incoming Bulk / Cluster Offers
# ---------------------------------------------------------------------------
@router.get("/seller/demand-bridge/offers")
def list_seller_cluster_offers(
    principal: AuthenticatedPrincipal = Depends(
        require_platform_role("DIRECT_SELLER", "ADMIN")
    ),
    db: Session = Depends(get_db),
) -> dict:
    """List bulk & multi-artisan cluster allocations assigned to the authenticated artisan."""
    seller = db.scalar(select(SellerProfile).where(SellerProfile.user_id == principal.user_id))
    if seller is None and not principal.is_active_admin:
        return {"count": 0, "items": []}

    stmt = (
        select(DemandArtisanMatch, BuyerDemandRequest, SellerProfile)
        .join(BuyerDemandRequest, BuyerDemandRequest.id == DemandArtisanMatch.demand_request_id)
        .join(SellerProfile, SellerProfile.id == DemandArtisanMatch.seller_profile_id)
        .where(DemandArtisanMatch.match_status.in_(["CONTACTED", "ACCEPTED", "DECLINED", "SHORTLISTED"]))
    )
    if seller is not None and not principal.is_active_admin:
        stmt = stmt.where(DemandArtisanMatch.seller_profile_id == seller.id)

    rows = db.execute(stmt.order_by(DemandArtisanMatch.updated_at.desc()).limit(40)).all()
    return {
        "count": len(rows),
        "items": [
            {
                "match_id": m.id,
                "demand_request_id": r.id,
                "request_code": r.request_code,
                "buyer_name": r.buyer_name or "Verified B2B Buyer",
                "buyer_email": r.buyer_email,
                "category_slug": r.category_slug,
                "raw_request_text": r.raw_request_text,
                "total_order_quantity": r.requested_quantity,
                "allocated_quantity": m.allocated_quantity,
                "is_cluster_member": bool(m.is_cluster_member),
                "fulfillment_mode": r.fulfillment_mode,
                "estimated_unit_price_inr": float(m.estimated_unit_price_inr) if m.estimated_unit_price_inr else None,
                "estimated_lead_days": m.estimated_lead_days,
                "match_score": float(m.match_score),
                "match_reasons": m.match_reasons_json,
                "match_status": m.match_status,
                "artisan_response_note": m.artisan_response_note,
                "artisan_store_name": s.store_name,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m, r, s in rows
        ],
    }


@router.post("/seller/demand-bridge/offers/{match_id}/respond")
def respond_to_cluster_offer(
    match_id: str,
    payload: ArtisanOfferRespondIn,
    principal: AuthenticatedPrincipal = Depends(
        require_platform_role("DIRECT_SELLER", "ADMIN")
    ),
    db: Session = Depends(get_db),
) -> dict:
    """Allow an artisan workshop to accept or decline a bulk/cluster allocation."""
    match = db.scalar(select(DemandArtisanMatch).where(DemandArtisanMatch.id == match_id))
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster offer not found.")

    seller = db.scalar(select(SellerProfile).where(SellerProfile.id == match.seller_profile_id))
    if not principal.is_active_admin and (seller is None or seller.user_id != principal.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the matched artisan workshop may respond to this offer.",
        )

    match.match_status = payload.decision
    match.artisan_response_note = (payload.response_note or "").strip() or None
    match.updated_at = utcnow()
    db.commit()
    return {
        "match_id": match.id,
        "match_status": match.match_status,
        "artisan_response_note": match.artisan_response_note,
    }
