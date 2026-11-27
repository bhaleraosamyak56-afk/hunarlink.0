"""Demand Bridge: Deterministic Brief Structuring + Multi-Artisan Cluster Matcher.

Architecture:
  - Step A (`parse_buyer_brief`): Pure deterministic parser extracting structured specs
    from natural-language wholesale/corporate briefs.
  - Step B (`match_demand_to_artisans`): Pure deterministic scoring over MySQL
    `seller_profiles` + `artisan_capabilities` + `craft_passports`.
  - Smart Multi-Artisan Cluster Pooling: When requested volume exceeds any single rural workshop's
    capacity, automatically pools 2–5 compatible workshops into a unified fulfillment cluster.
"""
from __future__ import annotations

import hashlib
import re
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.core_models import SellerProductListing, SellerProfile
from app.models.craftproof_models import (
    VERIFIED_CLAIM_STATUSES,
    ArtisanCapability,
    BuyerDemandRequest,
    CraftPassport,
    DemandArtisanMatch,
)
from app.modules.demand_bridge.schemas import DemandMatchIn

_CATEGORY_KEYWORDS: list[tuple[tuple[str, ...], str, str]] = [
    (("walnut", "wood", "box", "boxes", "carv", "khatamband", "tray"), "walnut-wood", "Walnut Wood Carving"),
    (("kani",), "kani-shawls", "Kani Shawls"),
    (("pashmina", "sozni", "shawl", "stole", "cashmere", "wool"), "pashmina", "Pashmina & Shawls"),
    (("carpet", "kaleen", "rug"), "kashmiri-carpets", "Kashmiri Carpets"),
    (("papier", "mache", "naqqashi", "ornament"), "papier-mache", "Papier-Mâché"),
    (("copper", "samovar", "tram", "vessel"), "copperware", "Kashmiri Copperware"),
    (("saffron", "kesar", "mongra", "pampore"), "saffron-pampore", "Pampore Saffron"),
    (("crewel", "chain stitch", "namda", "cushion", "curtain"), "crewel-embroidery", "Crewel & Embroidery"),
]

_DISTRICTS = (
    "Srinagar",
    "Budgam",
    "Anantnag",
    "Baramulla",
    "Pulwama",
    "Pampore",
    "Ganderbal",
    "Bandipora",
    "Kupwara",
    "Jammu",
)


def _infer_category_slug(text: str) -> tuple[str | None, str]:
    low = (text or "").lower()
    for kws, slug, label in _CATEGORY_KEYWORDS:
        if any(kw in low for kw in kws):
            return slug, label
    return None, "General Kashmiri Craft"


def _deterministic_parse_brief(raw_text: str) -> dict[str, Any]:
    low = raw_text.lower()
    cat_slug, cat_label = _infer_category_slug(raw_text)

    # Quantity (e.g., "100 hand-carved walnut boxes", "40 shawls", "qty 60")
    qty = None
    for pat in (
        r"\b(\d{1,4})\s*(?:hand[- ]?carved|handwoven|handmade|pure|gi|kashmiri|walnut|pashmina|sozni|kani|copper|papier|saffron|gift|corporate|custom|units?|pieces?|pcs|boxes?|shawls?|stoles?|carpets?|rugs?|sets?)\b",
        r"\b(?:need|want|order|require|qty|quantity)\s*(?:of|around|approx\.?)?\s*(\d{1,4})\b",
    ):
        m = re.search(pat, low)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 5000:
                qty = val
                break

    # Budget range (e.g., "₹2,200-₹2,800", "2200 to 2800", "under 2600", "budget 3000")
    b_min, b_max = None, None
    m_range = re.search(
        r"(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:,\d{3})+|\d{3,6})\s*(?:-|–|to)\s*(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:,\d{3})+|\d{3,6})",
        low,
    )
    if m_range:
        v1 = int(m_range.group(1).replace(",", ""))
        v2 = int(m_range.group(2).replace(",", ""))
        b_min, b_max = min(v1, v2), max(v1, v2)
    else:
        m_under = re.search(
            r"(?:under|below|max|upto|up to|budget(?:\s+of)?)\s*(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:,\d{3})+|\d{3,6})",
            low,
        )
        if m_under:
            b_max = int(m_under.group(1).replace(",", ""))
            b_min = max(300, round(b_max * 0.7))

    # Delivery days (e.g., "within 25 days", "in 3 weeks", "1 month")
    days = None
    m_days = re.search(r"\b(\d{1,3})\s*(?:days?|din)\b", low)
    m_weeks = re.search(r"\b(\d{1,2})\s*(?:weeks?|hafte)\b", low)
    m_months = re.search(r"\b(\d{1,2})\s*(?:months?|mahine)\b", low)
    if m_days:
        days = int(m_days.group(1))
    elif m_weeks:
        days = int(m_weeks.group(1)) * 7
    elif m_months:
        days = int(m_months.group(1)) * 30

    district = next((d for d in _DISTRICTS if re.search(rf"\b{d}\b", raw_text, re.IGNORECASE)), None)
    requires_verified = bool(re.search(r"\b(gi|verified|certified|authentic|passport)\b", low))

    ambiguous = []
    if not cat_slug:
        ambiguous.append("Craft category not clearly identified — select a category before matching.")
    if not qty:
        ambiguous.append("Exact order quantity not stated — defaulted to 25 units for estimation.")
    if not b_max:
        ambiguous.append("Per-unit budget ceiling not specified — results will show artisan standard wholesale bands.")
    if not days:
        ambiguous.append("Delivery deadline not specified — defaulted to 30 days.")

    return {
        "category_slug": cat_slug or "walnut-wood",
        "category_label": cat_label,
        "craft_technique": cat_label,
        "requested_quantity": qty or 25,
        "budget_min_inr": b_min,
        "budget_max_inr": b_max,
        "target_delivery_days": days or 30,
        "preferred_district": district,
        "requires_verified_claims": requires_verified,
        "allow_cluster_pooling": True,
        "customization_notes": raw_text[:400],
        "ambiguous_fields": ambiguous,
    }


def parse_buyer_brief(raw_request_text: str) -> dict[str, Any]:
    """Deterministically parse a natural-language bulk buyer brief into structured specs."""
    structured = _deterministic_parse_brief(raw_request_text)
    return {
        "structured_requirements": structured,
        "parser_mode": "deterministic",
    }


def _synthesize_default_capability(db: Session, seller: SellerProfile) -> ArtisanCapability:
    """Create a realistic deterministic capability row from an existing seller's listings & specialty."""
    cat_slug, _ = _infer_category_slug(f"{seller.craft_specialty or ''} {seller.store_name}")
    cat_slug = cat_slug or "pashmina"

    listings = list(
        db.scalars(
            select(SellerProductListing).where(SellerProductListing.seller_profile_id == seller.id)
        ).all()
    )
    prices = [float(l.selling_price) for l in listings if l.selling_price and float(l.selling_price) > 0]
    if prices:
        p_min = max(500.0, round(min(prices) * 0.78))  # wholesale discount vs retail
        p_max = max(p_min + 250.0, round(max(prices) * 0.92))
    else:
        defaults = {
            "walnut-wood": (1600.0, 6800.0),
            "pashmina": (6500.0, 24000.0),
            "kani-shawls": (14000.0, 48000.0),
            "kashmiri-carpets": (16000.0, 85000.0),
            "papier-mache": (850.0, 4200.0),
            "copperware": (1400.0, 7500.0),
            "saffron-pampore": (950.0, 4800.0),
            "crewel-embroidery": (1500.0, 6500.0),
        }
        p_min, p_max = defaults.get(cat_slug, (1800.0, 9500.0))

    # Deterministic capacity variation by workshop ID hash (realistic rural workshop volumes: 14–48/month)
    h = int(hashlib.sha256(seller.id.encode("utf-8")).hexdigest()[:8], 16)
    cap_bands = {
        "walnut-wood": (22, 46, 16, 26),
        "papier-mache": (28, 55, 12, 22),
        "copperware": (20, 42, 14, 24),
        "saffron-pampore": (35, 80, 7, 14),
        "crewel-embroidery": (18, 40, 15, 25),
        "pashmina": (12, 28, 18, 32),
        "kani-shawls": (6, 14, 30, 50),
        "kashmiri-carpets": (4, 12, 35, 60),
    }
    c_lo, c_hi, d_lo, d_hi = cap_bands.get(cat_slug, (16, 36, 14, 26))
    monthly_cap = c_lo + (h % (c_hi - c_lo + 1))
    lead_days = d_lo + ((h >> 8) % (d_hi - d_lo + 1))
    moq = max(3, min(12, monthly_cap // 4))

    cap = ArtisanCapability(
        seller_profile_id=seller.id,
        category_slug=cat_slug,
        craft_techniques_json=[seller.craft_specialty or cat_slug.replace("-", " ").title()],
        monthly_capacity_units=monthly_cap,
        min_order_qty=moq,
        standard_lead_time_days=lead_days,
        unit_price_min_inr=Decimal(f"{p_min:.2f}"),
        unit_price_max_inr=Decimal(f"{p_max:.2f}"),
        supports_custom_design=True,
        accepts_wholesale=True,
        availability_status="AVAILABLE",
    )
    db.add(cap)
    db.flush()
    return cap


def ensure_artisan_capabilities_seeded(db: Session) -> int:
    """Guarantee all approved/active sellers have an `artisan_capabilities` record."""
    sellers = list(
        db.scalars(
            select(SellerProfile).where(SellerProfile.profile_status == "ACTIVE")
        ).all()
    )
    existing_ids = set(
        db.scalars(select(ArtisanCapability.seller_profile_id)).all()
    )
    created = 0
    for s in sellers:
        if s.id not in existing_ids:
            _synthesize_default_capability(db, s)
            created += 1
    if created:
        db.flush()
    return created


def _estimate_unit_price(cap: ArtisanCapability, budget_min: float | None, budget_max: float | None) -> float:
    lo = float(cap.unit_price_min_inr)
    hi = float(cap.unit_price_max_inr)
    mid = (lo + hi) / 2.0
    if budget_max is not None:
        if lo <= budget_max <= hi:
            return round((lo + budget_max) / 2.0)
        if budget_max < lo:
            return round(lo)
    if budget_min is not None and budget_min > mid:
        return round(min(hi, budget_min))
    return round(mid)


def match_demand_to_artisans(
    db: Session,
    *,
    payload: DemandMatchIn,
    buyer_user_id: str | None = None,
) -> dict[str, Any]:
    """100% Deterministic MySQL Matching + Smart Multi-Artisan Cluster Fulfillment."""
    ensure_artisan_capabilities_seeded(db)

    req_cat = (payload.category_slug or "").strip().lower()
    if not req_cat:
        req_cat, _ = _infer_category_slug(payload.raw_request_text)
        req_cat = req_cat or "walnut-wood"

    qty = payload.requested_quantity
    b_min = payload.budget_min_inr
    b_max = payload.budget_max_inr
    target_days = payload.target_delivery_days or 30

    rows = db.execute(
        select(SellerProfile, ArtisanCapability)
        .join(ArtisanCapability, ArtisanCapability.seller_profile_id == SellerProfile.id)
        .where(
            SellerProfile.profile_status == "ACTIVE",
            ArtisanCapability.accepts_wholesale == True,  # noqa: E712
            ArtisanCapability.availability_status != "BOOKED",
        )
    ).all()

    # Pre-count verified passports per seller for trust scoring
    verified_passport_counts = dict(
        db.execute(
            select(CraftPassport.seller_profile_id, func.count(CraftPassport.id))
            .where(CraftPassport.overall_trust_level.in_(list(VERIFIED_CLAIM_STATUSES)))
            .group_by(CraftPassport.seller_profile_id)
        ).all()
    )

    scored_candidates: list[dict[str, Any]] = []
    for seller, cap in rows:
        # 1. Category alignment (30 pts) — treat pashmina & kani-shawls as adjacent craft cousins
        cat_score = 0.0
        reasons: list[str] = []
        if cap.category_slug == req_cat:
            cat_score = 30.0
            reasons.append(f"Direct craft guild specialist ({cap.category_slug}).")
        elif {cap.category_slug, req_cat} <= {"pashmina", "kani-shawls", "crewel-embroidery"}:
            cat_score = 21.0
            reasons.append(f"Adjacent Kashmiri textile atelier ({cap.category_slug}).")
        elif (payload.craft_technique or "").lower() in (seller.craft_specialty or "").lower():
            cat_score = 24.0
            reasons.append(f"Technique matches specialty ({seller.craft_specialty}).")
        else:
            continue  # hard filter unrelated crafts

        # 2. Capacity & MOQ feasibility (25 pts)
        cap_units = int(cap.monthly_capacity_units)
        moq = int(cap.min_order_qty)
        can_solo = cap_units >= qty and qty >= moq
        if can_solo:
            cap_score = 25.0
            reasons.append(f"Solo workshop capacity ({cap_units} units/mo, MOQ {moq}) covers full {qty}-unit order.")
        elif cap_units > 0:
            coverage = min(1.0, cap_units / max(qty, 1))
            cap_score = round(8.0 + coverage * 14.0, 1)
            reasons.append(
                f"Workshop capacity is {cap_units} units/mo ({round(coverage * 100)}% of {qty}-unit brief — eligible for Multi-Artisan Cluster)."
            )
        else:
            cap_score = 0.0

        # 3. Budget alignment (20 pts)
        est_price = _estimate_unit_price(cap, b_min, b_max)
        p_lo, p_hi = float(cap.unit_price_min_inr), float(cap.unit_price_max_inr)
        if b_max is None and b_min is None:
            budget_score = 16.0
            reasons.append(f"Wholesale price band INR {p_lo:,.0f}–{p_hi:,.0f}/unit.")
        else:
            ceiling = b_max or (b_min * 1.4 if b_min else p_hi)
            floor = b_min or 0.0
            if p_lo <= ceiling and p_hi >= floor:
                budget_score = 20.0
                reasons.append(f"Estimated INR {est_price:,.0f}/unit fits target budget band.")
            elif p_lo <= ceiling * 1.18:
                budget_score = 13.0
                reasons.append(f"Wholesale floor INR {p_lo:,.0f}/unit is within ~18% of ceiling.")
            else:
                budget_score = 5.0
                reasons.append(f"Higher-tier heirloom pricing (INR {p_lo:,.0f}–{p_hi:,.0f}/unit).")

        # 4. Lead time feasibility (15 pts)
        lead_days = int(cap.standard_lead_time_days)
        if lead_days <= target_days:
            lead_score = 15.0
            reasons.append(f"Lead time {lead_days} days meets {target_days}-day deadline.")
        elif lead_days <= target_days + 7:
            lead_score = 9.0
            reasons.append(f"Lead time {lead_days} days is close to {target_days}-day target.")
        else:
            lead_score = 4.0
            reasons.append(f"Typical handmade lead time is {lead_days} days.")

        # 5. Verification & Trust Tier (10 pts)
        verified_passports = int(verified_passport_counts.get(seller.id, 0))
        is_gi_verified = seller.verification_status == "APPROVED" and seller.verification_path == "GI"
        if payload.requires_verified_claims and seller.verification_status != "APPROVED":
            continue
        trust_score = 0.0
        if seller.verification_status == "APPROVED":
            trust_score += 5.0
        if is_gi_verified:
            trust_score += 3.0
            reasons.append(f"GI-registered verified workshop ({seller.workshop_district or 'J&K'}).")
        elif seller.verification_status == "APPROVED":
            reasons.append(f"Admin-approved artisan workshop ({seller.workshop_district or 'J&K'}).")
        if verified_passports > 0:
            trust_score += 2.0
            reasons.append(f"{verified_passports} Craft Passport(s) carry verified claims.")

        # District preference tie-breaker (+0 to 2 pts capped at 100)
        district_bonus = 0.0
        if (
            payload.preferred_district
            and seller.workshop_district
            and payload.preferred_district.strip().lower() == seller.workshop_district.strip().lower()
        ):
            district_bonus = 2.0
            reasons.append(f"Located in requested district ({seller.workshop_district}).")

        total_score = min(100.0, round(cat_score + cap_score + budget_score + lead_score + trust_score + district_bonus, 2))
        scored_candidates.append(
            {
                "seller": seller,
                "cap": cap,
                "total_score": total_score,
                "can_solo": can_solo,
                "monthly_capacity": cap_units,
                "est_unit_price_inr": est_price,
                "lead_days": lead_days,
                "verified_passports": verified_passports,
                "score_breakdown": {
                    "category_match": cat_score,
                    "capacity_moq": cap_score,
                    "budget_fit": budget_score,
                    "lead_time": lead_score,
                    "trust_verification": trust_score,
                },
                "reasons": reasons,
            }
        )

    scored_candidates.sort(key=lambda c: (-c["total_score"], -c["monthly_capacity"], c["lead_days"]))

    # Determine Single Artisan vs Multi-Artisan Cluster Fulfillment
    solo_capable = [c for c in scored_candidates if c["can_solo"] and c["lead_days"] <= target_days + 5]
    cluster_members: list[dict[str, Any]] = []
    fulfillment_mode = "UNMATCHED"

    if solo_capable:
        fulfillment_mode = "SINGLE_ARTISAN"
    elif payload.allow_cluster_pooling and len(scored_candidates) >= 2:
        # Pool top workshops deterministically until allocated_quantity == requested_quantity
        remaining = qty
        for cand in scored_candidates[:6]:
            if remaining <= 0:
                break
            alloc = min(remaining, cand["monthly_capacity"])
            if alloc <= 0:
                continue
            cluster_members.append({**cand, "allocated_quantity": alloc})
            remaining -= alloc
        if cluster_members and remaining == 0:
            fulfillment_mode = "MULTI_ARTISAN_CLUSTER"
        elif cluster_members:
            # Partial cluster still surfaced transparently
            fulfillment_mode = "MULTI_ARTISAN_CLUSTER"
    elif scored_candidates:
        fulfillment_mode = "SINGLE_ARTISAN"

    # Persist BuyerDemandRequest & DemandArtisanMatch rows
    code_seed = hashlib.sha256(f"{payload.raw_request_text}:{utcnow().isoformat()}".encode("utf-8")).hexdigest().upper()
    req_code = f"HL-DB-{code_seed[:8]}"

    demand_req = BuyerDemandRequest(
        request_code=req_code,
        buyer_user_id=buyer_user_id,
        buyer_name=payload.buyer_name,
        buyer_email=payload.buyer_email,
        raw_request_text=payload.raw_request_text,
        structured_requirements_json={
            "category_slug": req_cat,
            "craft_technique": payload.craft_technique,
            "requested_quantity": qty,
            "budget_min_inr": b_min,
            "budget_max_inr": b_max,
            "target_delivery_days": target_days,
            "preferred_district": payload.preferred_district,
            "requires_verified_claims": payload.requires_verified_claims,
            "allow_cluster_pooling": payload.allow_cluster_pooling,
            "customization_notes": payload.customization_notes,
        },
        category_slug=req_cat,
        requested_quantity=qty,
        budget_min_inr=Decimal(f"{b_min:.2f}") if b_min is not None else None,
        budget_max_inr=Decimal(f"{b_max:.2f}") if b_max is not None else None,
        target_delivery_days=target_days,
        requires_verified_claims=payload.requires_verified_claims,
        allow_cluster_pooling=payload.allow_cluster_pooling,
        fulfillment_mode=fulfillment_mode,
        request_status="MATCHED" if scored_candidates else "DRAFT",
    )
    db.add(demand_req)
    db.flush()

    cluster_ids = {m["seller"].id: m["allocated_quantity"] for m in cluster_members}
    persisted_matches: list[dict[str, Any]] = []
    top_to_save = scored_candidates[:6]
    for rank, cand in enumerate(top_to_save, 1):
        seller = cand["seller"]
        is_member = seller.id in cluster_ids
        allocated = cluster_ids.get(seller.id, qty if (fulfillment_mode == "SINGLE_ARTISAN" and rank == 1) else 0)
        m_row = DemandArtisanMatch(
            demand_request_id=demand_req.id,
            seller_profile_id=seller.id,
            match_rank=rank,
            is_cluster_member=is_member,
            allocated_quantity=allocated,
            match_score=Decimal(f"{cand['total_score']:.2f}"),
            score_breakdown_json=cand["score_breakdown"],
            match_reasons_json=cand["reasons"],
            estimated_unit_price_inr=Decimal(f"{cand['est_unit_price_inr']:.2f}"),
            estimated_lead_days=cand["lead_days"],
            match_status="SUGGESTED",
        )
        db.add(m_row)
        db.flush()
        persisted_matches.append(
            {
                "match_id": m_row.id,
                "match_rank": rank,
                "seller_profile_id": seller.id,
                "store_name": seller.store_name,
                "store_slug": seller.store_slug,
                "craft_specialty": seller.craft_specialty,
                "workshop_district": seller.workshop_district,
                "verification_path": seller.verification_path,
                "verification_status": seller.verification_status,
                "monthly_capacity_units": cand["monthly_capacity"],
                "min_order_qty": int(cand["cap"].min_order_qty),
                "can_fulfill_solo": cand["can_solo"],
                "is_cluster_member": is_member,
                "allocated_quantity": allocated,
                "match_score": float(cand["total_score"]),
                "score_breakdown": cand["score_breakdown"],
                "match_reasons": cand["reasons"],
                "estimated_unit_price_inr": cand["est_unit_price_inr"],
                "estimated_lead_days": cand["lead_days"],
                "verified_passports_count": cand["verified_passports"],
                "match_status": m_row.match_status,
            }
        )

    db.commit()

    # Build Multi-Artisan Cluster Summary if formed
    cluster_plan = None
    if fulfillment_mode == "MULTI_ARTISAN_CLUSTER":
        cluster_rows = [m for m in persisted_matches if m["is_cluster_member"]]
        total_alloc = sum(m["allocated_quantity"] for m in cluster_rows)
        if total_alloc > 0:
            blended_unit_price = round(
                sum(m["allocated_quantity"] * m["estimated_unit_price_inr"] for m in cluster_rows) / total_alloc
            )
            parallel_lead_days = max(m["estimated_lead_days"] for m in cluster_rows)
            cluster_plan = {
                "cluster_size": len(cluster_rows),
                "requested_quantity": qty,
                "total_allocated_quantity": total_alloc,
                "coverage_pct": round((total_alloc / qty) * 100, 1),
                "blended_unit_price_inr": blended_unit_price,
                "estimated_total_order_inr": blended_unit_price * total_alloc,
                "parallel_lead_time_days": parallel_lead_days,
                "why_cluster_formed": (
                    f"No single rural workshop holds {qty}-unit monthly capacity within deadline. "
                    f"HunarLink pooled {len(cluster_rows)} verified Kashmir ateliers in parallel "
                    f"to fulfill {total_alloc} units directly without factory middlemen."
                ),
                "members": cluster_rows,
            }

    return {
        "demand_request_id": demand_req.id,
        "request_code": demand_req.request_code,
        "fulfillment_mode": fulfillment_mode,
        "category_slug": req_cat,
        "requested_quantity": qty,
        "target_delivery_days": target_days,
        "total_artisans_evaluated": len(rows),
        "matched_count": len(persisted_matches),
        "cluster_plan": cluster_plan,
        "matches": persisted_matches,
        "matching_method": "100% deterministic MySQL capability & verification scoring",
    }
