"""Automated tests for CraftProof Passports & Deterministic Demand Bridge Cluster Pooling.

Tests run cleanly in pure deterministic mode (zero LLM or external API calls)
and enforce all hard trust invariants.
"""
from __future__ import annotations

from decimal import Decimal

from app.models.base import new_uuid
from app.models.core_models import SellerProfile
from app.models.craftproof_models import ArtisanCapability
from tests.conftest import (
    create_user_with_roles,
    seed_marketplace_entities,
    set_authenticated_principal,
)


def test_ai_routes_completely_removed(app_and_client):
    _, client = app_and_client
    assert client.get("/api/v1/ai/status").status_code == 404
    assert client.post("/api/v1/ai/artisan-doc/prescreen", json={}).status_code == 404
    assert client.post("/api/v1/ai/artisan-copilot/draft", json={}).status_code == 404
    assert client.post("/api/v1/ai/craft-audit/listing", json={}).status_code == 404
    assert client.post("/api/v1/ai/buyer-assistant/ask", json={}).status_code == 404


def test_craft_passport_lifecycle_qr_and_human_only_verification(app_and_client, db_session):
    app, client = app_and_client
    env = seed_marketplace_entities(db_session)
    listing = env["active_listing"]

    # 1. Seller creates passport — every claim MUST start SELLER_DECLARED
    set_authenticated_principal(app, env["seller_principal"])
    res = client.post(
        f"/api/v1/seller/passports/for-listing/{listing.id}",
        json={
            "materials_summary": "100% Handspun Changthangi Pashmina",
            "manufacturing_process": "Traditional Kani wooden bobbin twill weave",
            "origin_location": "Budgam, Jammu & Kashmir",
            "craft_days_estimated": 65,
        },
    )
    assert res.status_code == 201, res.text
    passport = res.json()
    passport_code = passport["passport_code"]
    assert passport_code.startswith("HL-CP-")
    assert passport["overall_trust_level"] == "SELLER_DECLARED"
    assert len(passport["verified_claims"]) == 0
    assert len(passport["unverified_claims"]) >= 4
    assert passport["fair_craft_breakdown"]["estimated_craft_days"] == 65

    # 2. Public QR SVG renders without authentication
    set_authenticated_principal(app, None)
    qr_res = client.get(f"/api/v1/passports/{passport_code}/qr.svg")
    assert qr_res.status_code == 200
    assert "image/svg+xml" in qr_res.headers["content-type"]
    assert "<svg" in qr_res.text and "craftproof-qr-svg" in qr_res.text

    # 3. Public lookup finds passport by code
    lookup_res = client.get(f"/api/v1/passports/lookup?q={passport_code}")
    assert lookup_res.status_code == 200
    assert lookup_res.json()["count"] >= 1

    # 4. Seller attaches evidence to Material claim -> status becomes EVIDENCE_SUBMITTED
    claim_id = passport["unverified_claims"][0]["claim_id"]
    set_authenticated_principal(app, env["seller_principal"])
    ev_res = client.post(
        f"/api/v1/seller/passports/claims/{claim_id}/evidence",
        json={
            "evidence_type": "WORKSHOP_PHOTO",
            "external_reference_url": "https://example.org/workshop-loom-evidence.jpg",
            "caption": "Handloom weaving frame in Budgam workshop",
        },
    )
    assert ev_res.status_code == 201, ev_res.text
    assert ev_res.json()["verification_status"] == "EVIDENCE_SUBMITTED"

    # 5. Seller MUST be blocked (403) from verifying their own claim!
    forbid_res = client.post(
        f"/api/v1/admin/passports/claims/{claim_id}/decision",
        json={
            "decision_status": "HUMAN_VERIFIED",
            "decision_notes": "Seller trying to self-verify.",
        },
    )
    assert forbid_res.status_code == 403

    # 6. Human Admin verifies the claim -> passport upgrades live & timeline records HUMAN_ADMIN
    set_authenticated_principal(app, env["admin_principal"])
    admin_q = client.get("/api/v1/admin/passports/claims?status_filter=EVIDENCE_SUBMITTED")
    assert admin_q.status_code == 200
    assert any(c["claim_id"] == claim_id for c in admin_q.json()["items"])

    decide_res = client.post(
        f"/api/v1/admin/passports/claims/{claim_id}/decision",
        json={
            "decision_status": "HUMAN_VERIFIED",
            "decision_notes": "Workshop loom photo & raw wool invoice reviewed by HunarLink desk.",
            "verified_by_authority": "HunarLink Kashmir Craft Desk",
        },
    )
    assert decide_res.status_code == 200, decide_res.text
    decided = decide_res.json()
    assert decided["verification_status"] == "HUMAN_VERIFIED"
    assert decided["overall_trust_level"] == "HUMAN_VERIFIED"
    assert len(decided["passport"]["verified_claims"]) == 1


def test_demand_bridge_multi_artisan_cluster_pooling(app_and_client, db_session):
    app, client = app_and_client
    seed_marketplace_entities(db_session)

    # Seed 3 small walnut wood workshops whose individual capacities (35, 30, 25) cannot solo 85 units
    walnut_sellers = []
    for idx, (name, district, cap_units, price_lo, price_hi) in enumerate(
        [
            ("Anantnag Heritage Walnut Guild", "Anantnag", 35, 2100, 2600),
            ("Chinar Chisel Atelier", "Srinagar", 30, 2200, 2750),
            ("Budgam Master Carvers", "Budgam", 25, 2000, 2500),
        ],
        1,
    ):
        u, p = create_user_with_roles(
            db_session,
            email=f"walnut{idx}@example.com",
            full_name=f"Master Carver {idx}",
            roles=["DIRECT_SELLER"],
        )
        sp = SellerProfile(
            id=new_uuid(),
            user_id=u.id,
            store_name=name,
            store_slug=f"walnut-workshop-{idx}",
            craft_specialty="Walnut Wood Carving",
            workshop_district=district,
            verification_path="GI",
            profile_status="ACTIVE",
            verification_status="APPROVED",
        )
        db_session.add(sp)
        db_session.flush()
        db_session.add(
            ArtisanCapability(
                seller_profile_id=sp.id,
                category_slug="walnut-wood",
                craft_techniques_json=["Walnut Wood Carving"],
                monthly_capacity_units=cap_units,
                min_order_qty=5,
                standard_lead_time_days=20,
                unit_price_min_inr=Decimal(str(price_lo)),
                unit_price_max_inr=Decimal(str(price_hi)),
                supports_custom_design=True,
                accepts_wholesale=True,
                availability_status="AVAILABLE",
            )
        )
        walnut_sellers.append((u, p, sp))
    db_session.commit()

    # Step 1: Deterministically parse natural-language bulk brief
    parse_res = client.post(
        "/api/v1/demand-bridge/parse",
        json={
            "raw_request_text": "Need 85 hand-carved walnut jewelry boxes for corporate gifting within 25 days, budget 2000 to 2800 INR per unit, prefer GI verified artisans."
        },
    )
    assert parse_res.status_code == 200, parse_res.text
    assert parse_res.json()["parser_mode"] == "deterministic"
    parsed = parse_res.json()["structured_requirements"]
    assert parsed["category_slug"] == "walnut-wood"
    assert parsed["requested_quantity"] == 85
    assert parsed["budget_max_inr"] == 2800

    # Step 2: Deterministic Match -> MUST automatically form MULTI_ARTISAN_CLUSTER summing to 85 units!
    match_res = client.post(
        "/api/v1/demand-bridge/match",
        json={
            "raw_request_text": "Need 85 hand-carved walnut jewelry boxes within 25 days, budget 2000-2800 INR",
            "buyer_name": "Taj Corporate Gifting",
            "buyer_email": "sourcing@tajdemo.in",
            "category_slug": "walnut-wood",
            "requested_quantity": 85,
            "budget_min_inr": 2000,
            "budget_max_inr": 2800,
            "target_delivery_days": 25,
            "requires_verified_claims": True,
            "allow_cluster_pooling": True,
        },
    )
    assert match_res.status_code == 201, match_res.text
    mdata = match_res.json()
    assert mdata["fulfillment_mode"] == "MULTI_ARTISAN_CLUSTER"
    cluster = mdata["cluster_plan"]
    assert cluster is not None
    assert cluster["cluster_size"] == 3
    assert cluster["total_allocated_quantity"] == 85
    assert cluster["coverage_pct"] == 100.0

    # Step 3: Dispatch inquiries to the entire cluster
    disp_res = client.post(
        f"/api/v1/demand-bridge/requests/{mdata['demand_request_id']}/dispatch-inquiries",
        json={"buyer_name": "Taj Corporate Gifting", "buyer_email": "sourcing@tajdemo.in"},
    )
    assert disp_res.status_code == 200
    assert disp_res.json()["contacted_count"] == 3

    # Step 4: First walnut artisan logs into Seller Studio and accepts their cluster allocation!
    set_authenticated_principal(app, walnut_sellers[0][1])
    offers_res = client.get("/api/v1/seller/demand-bridge/offers")
    assert offers_res.status_code == 200
    offers = offers_res.json()["items"]
    assert len(offers) == 1
    assert offers[0]["is_cluster_member"] is True
    assert offers[0]["allocated_quantity"] > 0

    accept_res = client.post(
        f"/api/v1/seller/demand-bridge/offers/{offers[0]['match_id']}/respond",
        json={"decision": "ACCEPTED", "response_note": "Workshop ready to carve 35 walnut boxes in 19 days."},
    )
    assert accept_res.status_code == 200
    assert accept_res.json()["match_status"] == "ACCEPTED"
