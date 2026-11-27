"""Layer 5: Deterministic GI vs Non-GI verification guardrails.

Enforces:
  - NON_GI applications use Admin manual review only.
  - GI applications without supporting evidence enter REVIEW_REQUIRED (never auto-approved).
  - GI applications with evidence perform deterministic GI reference lookups and ALWAYS
    route to mandatory human Admin approval (never auto-approved).
  - Seller verification and product GI verification remain separate decisions.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core_models import (
    GIReferenceRecord,
    SellerVerificationApplication,
)
from app.modules.guardrails.schemas import FieldIssue, GuardrailOutcome


def evaluate_verification_application(
    db: Session,
    *,
    application: SellerVerificationApplication,
    evidence_scan_ids: list[str],
) -> tuple[GuardrailOutcome, list[FieldIssue]]:
    issues: list[FieldIssue] = []

    # HARD INVARIANT: Non-GI path uses Admin manual review only
    if application.verification_path == "NON_GI":
        issues.append(
            FieldIssue(
                field="verification_path",
                rule_code="GI_NON_GI_MANUAL_ONLY",
                severity=GuardrailOutcome.REVIEW_REQUIRED,
                message="Non-GI seller applications follow manual Admin review.",
            )
        )
        return GuardrailOutcome.REVIEW_REQUIRED, issues

    # GI path requires supporting evidence
    if not evidence_scan_ids:
        issues.append(
            FieldIssue(
                field="evidence_scan_ids",
                rule_code="GI_MISSING_EVIDENCE",
                severity=GuardrailOutcome.REVIEW_REQUIRED,
                message="GI verification claim lacks supporting evidence documents; routed to human review.",
            )
        )
        return GuardrailOutcome.REVIEW_REQUIRED, issues

    # Lookup trusted GI reference record (if dataset is populated)
    ref_record = None
    if application.claimed_gi_code:
        ref_record = db.scalar(
            select(GIReferenceRecord).where(
                GIReferenceRecord.gi_registration_number == application.claimed_gi_code.strip(),
                GIReferenceRecord.is_active == True,  # noqa: E712
            )
        )

    if ref_record is None:
        issues.append(
            FieldIssue(
                field="claimed_gi_code",
                rule_code="GI_REFERENCE_NOT_FOUND_MANUAL_REVIEW",
                severity=GuardrailOutcome.REVIEW_REQUIRED,
                message="Claimed GI code did not match an active GI reference record; routed to human Admin review.",
            )
        )
        return GuardrailOutcome.REVIEW_REQUIRED, issues

    if (
        application.claimed_craft_cluster
        and ref_record.authorized_geographic_area
        and application.claimed_craft_cluster.strip().lower()
        not in ref_record.authorized_geographic_area.lower()
    ):
        issues.append(
            FieldIssue(
                field="claimed_craft_cluster",
                rule_code="GI_AREA_CONFLICT_MANUAL_REVIEW",
                severity=GuardrailOutcome.REVIEW_REQUIRED,
                message="Claimed workshop cluster differs from reference GI geographic area; routed to human Admin review.",
            )
        )
        return GuardrailOutcome.REVIEW_REQUIRED, issues

    # Even when reference fields match, human Admin approval remains mandatory.
    issues.append(
        FieldIssue(
            field="claimed_gi_code",
            rule_code="GI_REFERENCE_MATCH_PENDING_HUMAN_DECISION",
            severity=GuardrailOutcome.REVIEW_REQUIRED,
            message="GI reference check complete; human Admin approval is still required.",
        )
    )
    return GuardrailOutcome.REVIEW_REQUIRED, issues
