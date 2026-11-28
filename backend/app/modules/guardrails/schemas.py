"""Shared ASIGS guardrail outcomes, field-level error structures, and request/response DTOs."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GuardrailOutcome(str, Enum):
    """Guardrail decision outcomes (kept strictly separate from business statuses)."""

    PASS = "PASS"
    WARNING = "WARNING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCK = "BLOCK"


OUTCOME_SEVERITY = {
    GuardrailOutcome.PASS: 0,
    GuardrailOutcome.WARNING: 1,
    GuardrailOutcome.REVIEW_REQUIRED: 2,
    GuardrailOutcome.BLOCK: 3,
}


def merge_outcome(current: GuardrailOutcome, candidate: GuardrailOutcome) -> GuardrailOutcome:
    if OUTCOME_SEVERITY[candidate] > OUTCOME_SEVERITY[current]:
        return candidate
    return current


class FieldIssue(BaseModel):
    field: str
    rule_code: str
    severity: GuardrailOutcome
    message: str


class GuardrailResponse(BaseModel):
    outcome: GuardrailOutcome
    triggered_rule_codes: list[str] = Field(default_factory=list)
    field_errors: list[FieldIssue] = Field(default_factory=list)
    warnings: list[FieldIssue] = Field(default_factory=list)
    review_case_id: str | None = None
    correlation_id: str
    created_resource_id: str | None = None
    business_status: str | None = None


class SellerListingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(..., min_length=36, max_length=36)
    product_variant_id: str = Field(..., min_length=36, max_length=36)
    seller_sku: str = Field(..., min_length=2, max_length=100)
    listing_title: str = Field(..., min_length=3, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    technique: str | None = Field(default=None, max_length=120)
    dimensions: str | None = Field(default=None, max_length=160)
    origin_district: str | None = Field(default=None, max_length=100)
    purity_metric: str | None = Field(default=None, max_length=255)
    selling_price: Decimal = Field(..., gt=Decimal("0"))
    compare_at_mrp: Decimal | None = Field(default=None, gt=Decimal("0"))
    currency_code: str = Field(default="INR", min_length=3, max_length=3)
    stock_quantity: int = Field(default=0, ge=0)
    min_order_qty: int = Field(default=1, ge=1)
    max_order_qty: int | None = Field(default=None, ge=1)
    # Intentionally accepted as optional field so the guardrail can explicitly BLOCK
    # any seller attempt to self-assign GI_VERIFIED or bypass approval!
    requested_gi_status: str | None = Field(default=None, max_length=40)
    requested_listing_status: str | None = Field(default=None, max_length=40)
    claimed_seller_profile_id: str | None = Field(default=None, max_length=64)


class SupplierLotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(..., min_length=36, max_length=36)
    product_id: str | None = Field(default=None, min_length=36, max_length=36)
    product_variant_id: str | None = Field(default=None, min_length=36, max_length=36)
    lot_title: str = Field(..., min_length=3, max_length=220)
    lot_description: str | None = Field(default=None, max_length=5000)
    offered_quantity: Decimal = Field(..., gt=Decimal("0"))
    unit_of_measure: str = Field(default="PCS", min_length=1, max_length=32)
    expected_unit_price: Decimal = Field(..., gt=Decimal("0"))
    currency_code: str = Field(default="INR", min_length=3, max_length=3)
    is_gi_claimed: bool = Field(default=False)
    available_from_date: date
    available_until_date: date | None = None
    claimed_supplier_profile_id: str | None = Field(default=None, max_length=64)


class DealerProfileValidateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dealership_name: str = Field(..., min_length=2, max_length=180)
    city: str = Field(..., min_length=2, max_length=100)
    state_province: str = Field(..., min_length=2, max_length=100)
    gstin: str | None = Field(default=None, max_length=20)
    monthly_procurement_capacity: Decimal | None = Field(default=None, ge=Decimal("0"))
    currency_code: str = Field(default="INR", min_length=3, max_length=3)


class WholesalePriceTierInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_quantity: Decimal = Field(..., gt=Decimal("0"))
    max_quantity: Decimal | None = Field(default=None, gt=Decimal("0"))
    unit_price: Decimal = Field(..., gt=Decimal("0"))


class DealerWholesaleListingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(..., min_length=36, max_length=36)
    product_variant_id: str = Field(..., min_length=36, max_length=36)
    warehouse_id: str = Field(..., min_length=36, max_length=36)
    dealer_sku: str = Field(..., min_length=2, max_length=100)
    listing_title: str = Field(..., min_length=3, max_length=220)
    base_unit_price: Decimal = Field(..., gt=Decimal("0"))
    currency_code: str = Field(default="INR", min_length=3, max_length=3)
    minimum_order_quantity: Decimal = Field(..., gt=Decimal("0"))
    lead_time_days: int = Field(default=14, ge=1, le=365)
    price_tiers: list[WholesalePriceTierInput] = Field(default_factory=list)


class DealerAssignmentResponseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(..., pattern="^(ACCEPT|DECLINE)$")
    notes: str | None = Field(default=None, max_length=1000)


class VerificationAssessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(..., min_length=36, max_length=36)
    evidence_scan_ids: list[str] = Field(default_factory=list)
    untrusted_claim_text: str | None = Field(default=None, max_length=4000)


class AdminCaseDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(..., pattern="^(APPROVE|REJECT|ESCALATE)$")
    reason: str = Field(..., min_length=5, max_length=1000)


class FileUploadResponse(BaseModel):
    scan_id: str
    storage_key: str
    detected_mime_type: str
    file_size_bytes: int
    sha256_hash: str
    scan_status: str
    scanner_engine: str
    duplicate_hash_detected: bool
    review_case_id: str | None = None


class GuardrailCaseSummary(BaseModel):
    id: str
    case_number: str
    workflow_name: str
    target_type: str
    target_id: str | None
    guardrail_outcome: str
    case_status: str
    reason_codes: list[str]
    evidence_refs: list[Any]
    decision_reason: str | None
    created_at: datetime
