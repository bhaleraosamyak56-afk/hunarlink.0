"""Layer 2: Safe input validation preserving Kashmiri/Urdu/Hindi/English local text.

Important: Avoid naive keyword blocklists that cause false positives on benign
handicraft descriptions (e.g., 'select grade walnut', 'carved knife box',
'drop-spindle spun wool', 'traditional script calligraphy').
"""
from __future__ import annotations

import re

from app.modules.guardrails.rules.content_moderation import validate_content_policy
from app.modules.guardrails.schemas import FieldIssue, GuardrailOutcome

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
ACTIVE_HTML_SCRIPT_RE = re.compile(
    r"<\s*script\b|javascript\s*:|on(?:load|error|click)\s*=",
    re.IGNORECASE,
)
SKU_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,99}$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")


def validate_safe_text(
    field: str,
    value: str | None,
    *,
    required: bool = False,
    min_len: int = 1,
    max_len: int = 5000,
) -> list[FieldIssue]:
    issues: list[FieldIssue] = []
    if value is None or not value.strip():
        if required:
            issues.append(
                FieldIssue(
                    field=field,
                    rule_code="INPUT_REQUIRED",
                    severity=GuardrailOutcome.BLOCK,
                    message=f"Field '{field}' is required and cannot be blank.",
                )
            )
        return issues

    stripped = value.strip()
    if len(stripped) < min_len or len(stripped) > max_len:
        issues.append(
            FieldIssue(
                field=field,
                rule_code="INPUT_LENGTH_OUT_OF_RANGE",
                severity=GuardrailOutcome.BLOCK,
                message=f"Field '{field}' must be between {min_len} and {max_len} characters.",
            )
        )

    if CONTROL_CHARS_RE.search(value):
        issues.append(
            FieldIssue(
                field=field,
                rule_code="INPUT_INVALID_CONTROL_CHARS",
                severity=GuardrailOutcome.BLOCK,
                message=f"Field '{field}' contains disallowed control characters.",
            )
        )

    if ACTIVE_HTML_SCRIPT_RE.search(value):
        issues.append(
            FieldIssue(
                field=field,
                rule_code="INPUT_ACTIVE_SCRIPT_TAG",
                severity=GuardrailOutcome.BLOCK,
                message=f"Field '{field}' cannot include embedded script or HTML event handlers.",
            )
        )

    issues.extend(validate_content_policy(field, value))

    return issues


def validate_sku(field: str, sku: str) -> list[FieldIssue]:
    issues: list[FieldIssue] = []
    if not SKU_RE.match(sku.strip()):
        issues.append(
            FieldIssue(
                field=field,
                rule_code="INPUT_INVALID_SKU",
                severity=GuardrailOutcome.BLOCK,
                message="SKU must start with an alphanumeric character and use only letters, digits, '.', '_', or '-'.",
            )
        )
    issues.extend(validate_content_policy(field, sku))
    return issues


def validate_optional_gstin(gstin: str | None) -> list[FieldIssue]:
    if not gstin:
        return []
    if not GSTIN_RE.match(gstin.strip().upper()):
        return [
            FieldIssue(
                field="gstin",
                rule_code="INPUT_INVALID_GSTIN",
                severity=GuardrailOutcome.BLOCK,
                message="GSTIN format is invalid (expected 15-character Indian GSTIN).",
            )
        ]
    return []
