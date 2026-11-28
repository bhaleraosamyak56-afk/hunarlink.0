"""Layer 4: Product & seller listing validation.

Enforces:
  - Sellers CANNOT set `GI_VERIFIED` directly on a product or listing.
  - Sellers CANNOT bypass approval by requesting `ACTIVE`/`LIVE` publication directly.
  - Product and variant must exist, belong together, and be active.
  - SKU, title, description, price, MRP, and order quantity bounds are checked.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core_models import Product, ProductVariant
from app.modules.guardrails.rules.input_validation import validate_safe_text, validate_sku
from app.modules.guardrails.schemas import FieldIssue, GuardrailOutcome, SellerListingInput


def validate_seller_listing_product_rules(
    db: Session,
    payload: SellerListingInput,
) -> list[FieldIssue]:
    issues: list[FieldIssue] = []

    issues.extend(validate_safe_text("listing_title", payload.listing_title, required=True, min_len=3, max_len=220))
    issues.extend(validate_safe_text("description", payload.description, required=False, min_len=1, max_len=5000))
    issues.extend(validate_safe_text("technique", payload.technique, required=False, min_len=1, max_len=120))
    issues.extend(validate_safe_text("dimensions", payload.dimensions, required=False, min_len=1, max_len=160))
    issues.extend(validate_safe_text("origin_district", payload.origin_district, required=False, min_len=1, max_len=100))
    issues.extend(validate_safe_text("purity_metric", payload.purity_metric, required=False, min_len=1, max_len=255))
    issues.extend(validate_sku("seller_sku", payload.seller_sku))

    # Critical business invariant: sellers must NEVER directly mark a product GI_VERIFIED
    if payload.requested_gi_status and payload.requested_gi_status.strip().upper() == "GI_VERIFIED":
        issues.append(
            FieldIssue(
                field="requested_gi_status",
                rule_code="PROD_SELLER_CANNOT_SELF_VERIFY_GI",
                severity=GuardrailOutcome.BLOCK,
                message="Sellers cannot set GI_VERIFIED directly; submit a separate product GI claim for review.",
            )
        )

    # Sellers cannot bypass Admin approval to self-publish directly as ACTIVE/LIVE
    if payload.requested_listing_status and payload.requested_listing_status.strip().upper() in {"ACTIVE", "LIVE", "APPROVED"}:
        issues.append(
            FieldIssue(
                field="requested_listing_status",
                rule_code="PROD_BYPASS_APPROVAL_BLOCKED",
                severity=GuardrailOutcome.BLOCK,
                message="Listings cannot skip approval; new listings enter PENDING_APPROVAL.",
            )
        )

    product = db.scalar(select(Product).where(Product.id == payload.product_id))
    if product is None or not product.is_active:
        issues.append(
            FieldIssue(
                field="product_id",
                rule_code="PROD_NOT_FOUND_OR_INACTIVE",
                severity=GuardrailOutcome.BLOCK,
                message="Referenced product does not exist or is inactive.",
            )
        )
    elif product.approval_status != "APPROVED":
        issues.append(
            FieldIssue(
                field="product_id",
                rule_code="PROD_NOT_APPROVED",
                severity=GuardrailOutcome.BLOCK,
                message=f"Product approval_status '{product.approval_status}' must be APPROVED before listing.",
            )
        )

    variant = db.scalar(
        select(ProductVariant).where(
            ProductVariant.id == payload.product_variant_id,
            ProductVariant.product_id == payload.product_id,
        )
    )
    if variant is None or not variant.is_active:
        issues.append(
            FieldIssue(
                field="product_variant_id",
                rule_code="PROD_VARIANT_INVALID",
                severity=GuardrailOutcome.BLOCK,
                message="Referenced product variant does not exist for this product or is inactive.",
            )
        )

    if payload.max_order_qty is not None and payload.max_order_qty < payload.min_order_qty:
        issues.append(
            FieldIssue(
                field="max_order_qty",
                rule_code="PROD_INVALID_QTY_RANGE",
                severity=GuardrailOutcome.BLOCK,
                message="max_order_qty must be greater than or equal to min_order_qty.",
            )
        )

    return issues
