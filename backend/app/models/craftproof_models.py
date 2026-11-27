"""SQLAlchemy 2.x models for CraftProof Passports, Claims, Evidence & Demand Bridge.

Added via Alembic revision `0004_add_craftproof_and_demand_bridge` (strictly additive —
zero modifications to existing core or ASIGS tables).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, UUIDChar, new_uuid, utcnow

CLAIM_STATUSES = (
    "SELLER_DECLARED",
    "EVIDENCE_SUBMITTED",
    "UNDER_REVIEW",
    "HUMAN_VERIFIED",
    "THIRD_PARTY_VERIFIED",
    "NOT_ESTABLISHED",
    "REJECTED",
)

VERIFIED_CLAIM_STATUSES = frozenset({"HUMAN_VERIFIED", "THIRD_PARTY_VERIFIED"})


class CraftPassport(Base):
    __tablename__ = "craft_passports"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    passport_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    listing_id: Mapped[str] = mapped_column(
        UUIDChar(), ForeignKey("seller_product_listings.id"), unique=True, nullable=False
    )
    product_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("products.id"), nullable=False)
    seller_profile_id: Mapped[str] = mapped_column(
        UUIDChar(), ForeignKey("seller_profiles.id"), nullable=False
    )
    public_slug: Mapped[str] = mapped_column(String(260), unique=True, nullable=False)
    overall_trust_level: Mapped[str] = mapped_column(
        String(32), default="SELLER_DECLARED", nullable=False
    )
    materials_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    manufacturing_process: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin_location: Mapped[str | None] = mapped_column(String(180), nullable=True)
    craft_days_estimated: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artisan_story: Mapped[str | None] = mapped_column(Text, nullable=True)
    fair_craft_breakdown_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )


class CraftProductClaim(Base):
    __tablename__ = "craft_product_claims"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    passport_id: Mapped[str] = mapped_column(
        UUIDChar(), ForeignKey("craft_passports.id"), nullable=False
    )
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)
    claim_title: Mapped[str] = mapped_column(String(160), nullable=False)
    claim_value: Mapped[str] = mapped_column(String(500), nullable=False)
    claim_source: Mapped[str] = mapped_column(String(32), default="SELLER_DECLARED", nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(32), default="SELLER_DECLARED", nullable=False
    )
    verified_by_user_id: Mapped[str | None] = mapped_column(
        UUIDChar(), ForeignKey("users.id"), nullable=True
    )
    verified_by_authority: Mapped[str | None] = mapped_column(String(180), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    decision_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    ai_advisory_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )


class CraftClaimEvidence(Base):
    __tablename__ = "craft_claim_evidence"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    claim_id: Mapped[str] = mapped_column(
        UUIDChar(), ForeignKey("craft_product_claims.id"), nullable=False
    )
    passport_id: Mapped[str] = mapped_column(
        UUIDChar(), ForeignKey("craft_passports.id"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(40), nullable=False)
    file_scan_id: Mapped[str | None] = mapped_column(UUIDChar(), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_reference_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sha256_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(500), nullable=True)
    uploaded_by_user_id: Mapped[str] = mapped_column(
        UUIDChar(), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class CraftVerificationEvent(Base):
    __tablename__ = "craft_verification_events"
    __table_args__ = (
        CheckConstraint(
            "NOT (actor_type = 'AI_ADVISORY' AND (to_status IN ('HUMAN_VERIFIED', 'THIRD_PARTY_VERIFIED') OR is_legal_proof = 1))",
            name="chk_cve_ai_never_verifies",
        ),
    )

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    passport_id: Mapped[str] = mapped_column(
        UUIDChar(), ForeignKey("craft_passports.id"), nullable=False
    )
    claim_id: Mapped[str | None] = mapped_column(
        UUIDChar(), ForeignKey("craft_product_claims.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        UUIDChar(), ForeignKey("users.id"), nullable=True
    )
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_legal_proof: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class ArtisanCapability(Base):
    __tablename__ = "artisan_capabilities"
    __table_args__ = (
        UniqueConstraint("seller_profile_id", "category_slug", name="uq_artisan_cap_seller_cat"),
    )

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    seller_profile_id: Mapped[str] = mapped_column(
        UUIDChar(), ForeignKey("seller_profiles.id"), nullable=False
    )
    category_slug: Mapped[str] = mapped_column(String(140), nullable=False)
    craft_techniques_json: Mapped[list] = mapped_column(JSON, nullable=False)
    monthly_capacity_units: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    min_order_qty: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    standard_lead_time_days: Mapped[int] = mapped_column(Integer, default=18, nullable=False)
    unit_price_min_inr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("1500.00"), nullable=False
    )
    unit_price_max_inr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("12000.00"), nullable=False
    )
    supports_custom_design: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    accepts_wholesale: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    availability_status: Mapped[str] = mapped_column(
        String(24), default="AVAILABLE", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )


class BuyerDemandRequest(Base):
    __tablename__ = "buyer_demand_requests"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    request_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    buyer_user_id: Mapped[str | None] = mapped_column(
        UUIDChar(), ForeignKey("users.id"), nullable=True
    )
    buyer_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    buyer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_request_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_requirements_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    category_slug: Mapped[str | None] = mapped_column(String(140), nullable=True)
    requested_quantity: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    budget_min_inr: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    budget_max_inr: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    target_delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requires_verified_claims: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_cluster_pooling: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fulfillment_mode: Mapped[str] = mapped_column(
        String(32), default="SINGLE_ARTISAN", nullable=False
    )
    request_status: Mapped[str] = mapped_column(String(24), default="MATCHED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class DemandArtisanMatch(Base):
    __tablename__ = "demand_artisan_matches"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    demand_request_id: Mapped[str] = mapped_column(
        UUIDChar(), ForeignKey("buyer_demand_requests.id"), nullable=False
    )
    seller_profile_id: Mapped[str] = mapped_column(
        UUIDChar(), ForeignKey("seller_profiles.id"), nullable=False
    )
    match_rank: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_cluster_member: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allocated_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    match_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    score_breakdown_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    match_reasons_json: Mapped[list] = mapped_column(JSON, nullable=False)
    estimated_unit_price_inr: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    estimated_lead_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_status: Mapped[str] = mapped_column(String(24), default="SUGGESTED", nullable=False)
    artisan_response_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )
