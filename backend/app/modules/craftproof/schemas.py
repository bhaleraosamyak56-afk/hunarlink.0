"""Strict Pydantic DTOs for CraftProof Digital Passports, Claims & Verification."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ClaimType = Literal[
    "MATERIAL",
    "ORIGIN",
    "TECHNIQUE",
    "HANDMADE",
    "GI_TAG",
    "CERTIFICATION",
    "OTHER",
]

ClaimStatus = Literal[
    "SELLER_DECLARED",
    "EVIDENCE_SUBMITTED",
    "UNDER_REVIEW",
    "HUMAN_VERIFIED",
    "THIRD_PARTY_VERIFIED",
    "NOT_ESTABLISHED",
    "REJECTED",
]

AdminDecisionStatus = Literal[
    "UNDER_REVIEW",
    "HUMAN_VERIFIED",
    "THIRD_PARTY_VERIFIED",
    "NOT_ESTABLISHED",
    "REJECTED",
]

EvidenceType = Literal[
    "WORKSHOP_PHOTO",
    "LOOM_VIDEO_FRAME",
    "LAB_REPORT",
    "GI_CERTIFICATE",
    "ARTISAN_CARD",
    "INVOICE_RAW_MATERIAL",
    "THIRD_PARTY_REGISTRY",
    "OTHER",
]


class CreateClaimIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_type: ClaimType
    claim_title: str = Field(min_length=3, max_length=160)
    claim_value: str = Field(min_length=2, max_length=500)


class CreatePassportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    materials_summary: str | None = Field(default=None, max_length=2000)
    manufacturing_process: str | None = Field(default=None, max_length=2000)
    origin_location: str | None = Field(default=None, max_length=180)
    craft_days_estimated: int | None = Field(default=None, ge=1, le=730)
    artisan_story: str | None = Field(default=None, max_length=3000)
    claims: list[CreateClaimIn] = Field(default_factory=list, max_length=20)


class AttachEvidenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: EvidenceType
    file_scan_id: str | None = Field(default=None, max_length=64)
    external_reference_url: str | None = Field(default=None, max_length=512)
    caption: str | None = Field(default=None, max_length=500)


class AdminClaimDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_status: AdminDecisionStatus
    decision_notes: str = Field(min_length=5, max_length=1000)
    verified_by_authority: str | None = Field(default=None, max_length=180)
    metadata: dict[str, Any] | None = None
