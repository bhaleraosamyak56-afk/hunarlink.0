"""ASIGS Guardrail Service orchestrating all 10 validation & escalation layers."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit_log
from app.core.auth import AuthenticatedPrincipal
from app.core.config import Settings
from app.models.base import new_uuid
from app.models.core_models import (
    Category,
    DealerAssignment,
    DealerProfile,
    Product,
    ProductVariant,
    SellerProductListing,
    SellerProfile,
    SellerVerificationApplication,
    SupplierLot,
    SupplierProfile,
    Warehouse,
)
from app.models.guardrail_models import FileSecurityScan, GuardrailCase
from app.modules.guardrails import repository
from app.modules.guardrails.providers.malware_scanner import MalwareScanner
from app.modules.guardrails.rules.commercial import (
    validate_currency,
    validate_date_window,
    validate_retail_pricing,
    validate_wholesale_price_tiers,
)
from app.modules.guardrails.rules.documents import validate_and_store_private_document
from app.modules.guardrails.rules.duplicates import (
    check_and_record_duplicate,
    compute_normalized_fingerprint,
)
from app.modules.guardrails.rules.gi_claims import evaluate_verification_application
from app.modules.guardrails.rules.identity import check_identity_and_profile
from app.modules.guardrails.rules.input_validation import (
    validate_optional_gstin,
    validate_safe_text,
    validate_sku,
)
from app.modules.guardrails.rules.ownership import (
    ALLOWED_ASSIGNMENT_TRANSITIONS,
    assert_not_self_approval,
    assert_owner_or_admin,
    assert_valid_transition,
)
from app.modules.guardrails.rules.products import validate_seller_listing_product_rules
from app.modules.guardrails.schemas import (
    AdminCaseDecisionInput,
    DealerAssignmentResponseInput,
    DealerProfileValidateInput,
    DealerWholesaleListingInput,
    FieldIssue,
    FileUploadResponse,
    GuardrailOutcome,
    GuardrailResponse,
    SellerListingInput,
    SupplierLotInput,
    VerificationAssessInput,
    merge_outcome,
)


def _compute_outcome(issues: list[FieldIssue]) -> GuardrailOutcome:
    outcome = GuardrailOutcome.PASS
    for issue in issues:
        outcome = merge_outcome(outcome, issue.severity)
    return outcome


def _build_response(
    *,
    outcome: GuardrailOutcome,
    issues: list[FieldIssue],
    correlation_id: str,
    review_case_id: str | None = None,
    created_resource_id: str | None = None,
    business_status: str | None = None,
) -> GuardrailResponse:
    return GuardrailResponse(
        outcome=outcome,
        triggered_rule_codes=sorted({i.rule_code for i in issues}),
        field_errors=[i for i in issues if i.severity == GuardrailOutcome.BLOCK],
        warnings=[i for i in issues if i.severity != GuardrailOutcome.BLOCK],
        review_case_id=review_case_id,
        correlation_id=correlation_id,
        created_resource_id=created_resource_id,
        business_status=business_status,
    )


def evaluate_seller_listing(
    db: Session,
    *,
    principal: AuthenticatedPrincipal,
    payload: SellerListingInput,
    correlation_id: str,
    create_record: bool,
) -> GuardrailResponse:
    seller = db.scalar(select(SellerProfile).where(SellerProfile.user_id == principal.user_id))
    issues: list[FieldIssue] = []

    issues.extend(
        check_identity_and_profile(
            principal=principal,
            required_role="DIRECT_SELLER",
            profile_id=seller.id if seller else None,
            profile_status=seller.profile_status if seller else None,
            verification_status=seller.verification_status if seller else None,
            claimed_profile_id=payload.claimed_seller_profile_id,
            require_approved_verification=True,
        )
    )
    issues.extend(validate_seller_listing_product_rules(db, payload))

    variant = db.scalar(select(ProductVariant).where(ProductVariant.id == payload.product_variant_id))
    issues.extend(
        validate_retail_pricing(
            selling_price=payload.selling_price,
            compare_at_mrp=payload.compare_at_mrp,
            reference_mrp=variant.base_mrp if variant else None,
            currency_code=payload.currency_code,
        )
    )

    fingerprint = compute_normalized_fingerprint(
        {
            "seller_id": seller.id if seller else principal.user_id,
            "product_variant_id": payload.product_variant_id,
            "listing_title": payload.listing_title,
        }
    )
    outcome_before_dup = _compute_outcome(issues)
    if outcome_before_dup != GuardrailOutcome.BLOCK:
        issues.extend(
            check_and_record_duplicate(
                db,
                actor_user_id=principal.user_id,
                scope="seller_listing",
                fingerprint_hash=fingerprint,
                target_type="seller_product_listings",
                target_id=None,
                persist=False,
            )
        )

    outcome = _compute_outcome(issues)
    created_id: str | None = None
    business_status: str | None = None
    review_case_id: str | None = None

    if create_record and outcome != GuardrailOutcome.BLOCK and seller is not None:
        listing = SellerProductListing(
            id=new_uuid(),
            seller_profile_id=seller.id,
            product_id=payload.product_id,
            product_variant_id=payload.product_variant_id,
            seller_sku=payload.seller_sku.strip(),
            listing_title=payload.listing_title.strip(),
            selling_price=payload.selling_price,
            compare_at_mrp=payload.compare_at_mrp,
            currency_code=payload.currency_code.upper(),
            min_order_qty=payload.min_order_qty,
            max_order_qty=payload.max_order_qty,
            listing_status="PENDING_APPROVAL",
        )
        db.add(listing)
        db.flush()
        created_id = listing.id
        business_status = listing.listing_status

        # Record fingerprint for future duplicate detection
        check_and_record_duplicate(
            db,
            actor_user_id=principal.user_id,
            scope="seller_listing",
            fingerprint_hash=fingerprint,
            target_type="seller_product_listings",
            target_id=listing.id,
            persist=True,
        )

    check = repository.persist_guardrail_check(
        db,
        actor_user_id=principal.user_id,
        workflow_name="seller_listing_create" if create_record else "seller_listing_validate",
        target_type="seller_product_listings",
        target_id=created_id,
        outcome=outcome,
        issues=issues,
        payload_for_hash=payload.model_dump(mode="json"),
        correlation_id=correlation_id,
    )

    if create_record and outcome == GuardrailOutcome.REVIEW_REQUIRED:
        case = repository.create_guardrail_case(
            db,
            check=check,
            submitted_by_user_id=principal.user_id,
            reason_codes=sorted({i.rule_code for i in issues}),
            evidence_refs=[{"listing_id": created_id}],
            correlation_id=correlation_id,
        )
        review_case_id = case.id

    db.commit()
    return _build_response(
        outcome=outcome,
        issues=issues,
        correlation_id=correlation_id,
        review_case_id=review_case_id,
        created_resource_id=created_id,
        business_status=business_status,
    )


def evaluate_supplier_lot(
    db: Session,
    *,
    principal: AuthenticatedPrincipal,
    payload: SupplierLotInput,
    correlation_id: str,
    create_record: bool,
) -> GuardrailResponse:
    supplier = db.scalar(select(SupplierProfile).where(SupplierProfile.user_id == principal.user_id))
    issues: list[FieldIssue] = []

    issues.extend(
        check_identity_and_profile(
            principal=principal,
            required_role="SUPPLIER",
            profile_id=supplier.id if supplier else None,
            profile_status=supplier.profile_status if supplier else None,
            verification_status=supplier.verification_status if supplier else None,
            claimed_profile_id=payload.claimed_supplier_profile_id,
            require_approved_verification=True,
        )
    )
    issues.extend(validate_safe_text("lot_title", payload.lot_title, required=True, min_len=3, max_len=220))
    issues.extend(validate_safe_text("lot_description", payload.lot_description, required=False, max_len=5000))
    issues.extend(validate_currency(payload.currency_code))
    issues.extend(validate_date_window(payload.available_from_date, payload.available_until_date))

    category = db.scalar(select(Category).where(Category.id == payload.category_id, Category.is_active == True))  # noqa: E712
    if category is None:
        issues.append(
            FieldIssue(
                field="category_id",
                rule_code="LOT_INVALID_CATEGORY",
                severity=GuardrailOutcome.BLOCK,
                message="Referenced category does not exist or is inactive.",
            )
        )

    fingerprint = compute_normalized_fingerprint(
        {
            "supplier_id": supplier.id if supplier else principal.user_id,
            "category_id": payload.category_id,
            "lot_title": payload.lot_title,
            "available_from_date": payload.available_from_date.isoformat(),
        }
    )
    if _compute_outcome(issues) != GuardrailOutcome.BLOCK:
        issues.extend(
            check_and_record_duplicate(
                db,
                actor_user_id=principal.user_id,
                scope="supplier_lot",
                fingerprint_hash=fingerprint,
                target_type="supplier_lots",
                target_id=None,
                persist=False,
            )
        )

    outcome = _compute_outcome(issues)
    created_id: str | None = None
    business_status: str | None = None
    review_case_id: str | None = None

    if create_record and outcome != GuardrailOutcome.BLOCK and supplier is not None:
        lot = SupplierLot(
            id=new_uuid(),
            lot_number=f"LOT-{uuid.uuid4().hex[:10].upper()}",
            supplier_profile_id=supplier.id,
            category_id=payload.category_id,
            product_id=payload.product_id,
            product_variant_id=payload.product_variant_id,
            lot_title=payload.lot_title.strip(),
            lot_description=payload.lot_description,
            offered_quantity=payload.offered_quantity,
            remaining_quantity=payload.offered_quantity,
            unit_of_measure=payload.unit_of_measure.upper(),
            expected_unit_price=payload.expected_unit_price,
            currency_code=payload.currency_code.upper(),
            is_gi_claimed=payload.is_gi_claimed,
            available_from_date=payload.available_from_date,
            available_until_date=payload.available_until_date,
            lot_status="SUBMITTED",
        )
        db.add(lot)
        db.flush()
        created_id = lot.id
        business_status = lot.lot_status

        check_and_record_duplicate(
            db,
            actor_user_id=principal.user_id,
            scope="supplier_lot",
            fingerprint_hash=fingerprint,
            target_type="supplier_lots",
            target_id=lot.id,
            persist=True,
        )

    check = repository.persist_guardrail_check(
        db,
        actor_user_id=principal.user_id,
        workflow_name="supplier_lot_create" if create_record else "supplier_lot_validate",
        target_type="supplier_lots",
        target_id=created_id,
        outcome=outcome,
        issues=issues,
        payload_for_hash=payload.model_dump(mode="json"),
        correlation_id=correlation_id,
    )

    if create_record and outcome == GuardrailOutcome.REVIEW_REQUIRED:
        case = repository.create_guardrail_case(
            db,
            check=check,
            submitted_by_user_id=principal.user_id,
            reason_codes=sorted({i.rule_code for i in issues}),
            evidence_refs=[{"supplier_lot_id": created_id}],
            correlation_id=correlation_id,
        )
        review_case_id = case.id

    db.commit()
    return _build_response(
        outcome=outcome,
        issues=issues,
        correlation_id=correlation_id,
        review_case_id=review_case_id,
        created_resource_id=created_id,
        business_status=business_status,
    )


def validate_dealer_profile(
    db: Session,
    *,
    principal: AuthenticatedPrincipal,
    payload: DealerProfileValidateInput,
    correlation_id: str,
) -> GuardrailResponse:
    issues: list[FieldIssue] = []
    if not principal.has_role("DEALER"):
        issues.append(
            FieldIssue(
                field="role",
                rule_code="ID_MISSING_ROLE",
                severity=GuardrailOutcome.BLOCK,
                message="Authenticated account lacks required platform role 'DEALER'.",
            )
        )
    issues.extend(validate_safe_text("dealership_name", payload.dealership_name, required=True, min_len=2, max_len=180))
    issues.extend(validate_safe_text("city", payload.city, required=True, min_len=2, max_len=100))
    issues.extend(validate_safe_text("state_province", payload.state_province, required=True, min_len=2, max_len=100))
    issues.extend(validate_optional_gstin(payload.gstin))
    issues.extend(validate_currency(payload.currency_code))

    outcome = _compute_outcome(issues)
    repository.persist_guardrail_check(
        db,
        actor_user_id=principal.user_id,
        workflow_name="dealer_profile_validate",
        target_type="dealer_profiles",
        target_id=None,
        outcome=outcome,
        issues=issues,
        payload_for_hash=payload.model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    db.commit()
    return _build_response(outcome=outcome, issues=issues, correlation_id=correlation_id)


def validate_dealer_wholesale_listing(
    db: Session,
    *,
    principal: AuthenticatedPrincipal,
    payload: DealerWholesaleListingInput,
    correlation_id: str,
) -> GuardrailResponse:
    dealer = db.scalar(select(DealerProfile).where(DealerProfile.user_id == principal.user_id))
    issues: list[FieldIssue] = []

    issues.extend(
        check_identity_and_profile(
            principal=principal,
            required_role="DEALER",
            profile_id=dealer.id if dealer else None,
            profile_status=dealer.profile_status if dealer else None,
            verification_status=dealer.verification_status if dealer else None,
            require_approved_verification=True,
        )
    )
    issues.extend(validate_safe_text("listing_title", payload.listing_title, required=True, min_len=3, max_len=220))
    issues.extend(validate_sku("dealer_sku", payload.dealer_sku))

    if dealer is not None:
        wh = db.scalar(
            select(Warehouse).where(
                Warehouse.id == payload.warehouse_id,
                Warehouse.dealer_profile_id == dealer.id,
                Warehouse.is_active == True,  # noqa: E712
            )
        )
        if wh is None:
            issues.append(
                FieldIssue(
                    field="warehouse_id",
                    rule_code="DEALER_WAREHOUSE_NOT_OWNED",
                    severity=GuardrailOutcome.BLOCK,
                    message="Warehouse does not belong to the authenticated dealer or is inactive.",
                )
            )

    product = db.scalar(select(Product).where(Product.id == payload.product_id, Product.is_active == True))  # noqa: E712
    variant = db.scalar(
        select(ProductVariant).where(
            ProductVariant.id == payload.product_variant_id,
            ProductVariant.product_id == payload.product_id,
            ProductVariant.is_active == True,  # noqa: E712
        )
    )
    if product is None or variant is None:
        issues.append(
            FieldIssue(
                field="product_variant_id",
                rule_code="PROD_VARIANT_INVALID",
                severity=GuardrailOutcome.BLOCK,
                message="Product or product variant is invalid or inactive.",
            )
        )

    issues.extend(
        validate_wholesale_price_tiers(
            base_unit_price=payload.base_unit_price,
            minimum_order_quantity=payload.minimum_order_quantity,
            tiers=payload.price_tiers,
            currency_code=payload.currency_code,
        )
    )

    outcome = _compute_outcome(issues)
    repository.persist_guardrail_check(
        db,
        actor_user_id=principal.user_id,
        workflow_name="dealer_wholesale_listing_validate",
        target_type="dealer_wholesale_listings",
        target_id=None,
        outcome=outcome,
        issues=issues,
        payload_for_hash=payload.model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    db.commit()
    return _build_response(outcome=outcome, issues=issues, correlation_id=correlation_id)


def respond_to_dealer_assignment(
    db: Session,
    *,
    principal: AuthenticatedPrincipal,
    assignment_id: str,
    payload: DealerAssignmentResponseInput,
    correlation_id: str,
) -> dict:
    dealer = db.scalar(select(DealerProfile).where(DealerProfile.user_id == principal.user_id))
    assignment = db.scalar(select(DealerAssignment).where(DealerAssignment.id == assignment_id))
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer assignment not found.")
    if dealer is None or assignment.dealer_profile_id != dealer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dealer cannot accept or decline an assignment addressed to another dealer.",
        )

    next_status = "ACCEPTED" if payload.action == "ACCEPT" else "DECLINED"
    assert_valid_transition(
        transitions=ALLOWED_ASSIGNMENT_TRANSITIONS,
        current_status=assignment.assignment_status,
        next_status=next_status,
        entity_label="dealer_assignment",
    )
    prev = assignment.assignment_status
    assignment.assignment_status = next_status
    record_audit_log(
        db,
        actor_user_id=principal.user_id,
        actor_role="DEALER",
        action=f"DEALER_ASSIGNMENT_{payload.action}",
        target_type="dealer_assignments",
        target_id=assignment.id,
        reason=payload.notes or f"Dealer {payload.action.lower()}ed invitation",
        previous_values={"assignment_status": prev},
        new_values={"assignment_status": next_status},
        correlation_id=correlation_id,
    )
    db.commit()
    return {"assignment_id": assignment.id, "assignment_status": assignment.assignment_status}


def upload_private_document(
    db: Session,
    *,
    principal: AuthenticatedPrincipal,
    owner_scope: str,
    original_filename: str,
    claimed_content_type: str | None,
    payload: bytes,
    settings: Settings,
    correlation_id: str,
) -> FileUploadResponse:
    scanner = MalwareScanner(mode=settings.malware_scanner_mode)
    stored = validate_and_store_private_document(
        original_filename=original_filename,
        payload=payload,
        owner_scope=owner_scope,
        uploader_user_id=principal.user_id,
        storage_root=settings.private_storage_path,
        max_size_bytes=settings.max_upload_size_bytes,
        malware_scanner=scanner,
    )

    dup_issues = check_and_record_duplicate(
        db,
        actor_user_id=principal.user_id,
        scope="uploaded_file",
        fingerprint_hash=stored.sha256_hash,
        target_type="file_security_scans",
        target_id=None,
        persist=False,
    )

    scan_row = FileSecurityScan(
        id=new_uuid(),
        uploader_user_id=principal.user_id,
        owner_scope=owner_scope,
        storage_key=stored.storage_key,
        original_filename=original_filename[:255],
        claimed_content_type=claimed_content_type,
        detected_mime_type=stored.detected_mime_type,
        file_size_bytes=stored.file_size_bytes,
        sha256_hash=stored.sha256_hash,
        scanner_engine=stored.scanner_engine,
        scan_status=stored.scan_status,
        scan_details=stored.scan_details,
    )
    db.add(scan_row)
    db.flush()

    check_and_record_duplicate(
        db,
        actor_user_id=principal.user_id,
        scope="uploaded_file",
        fingerprint_hash=stored.sha256_hash,
        target_type="file_security_scans",
        target_id=scan_row.id,
        persist=True,
    )

    review_case_id: str | None = None
    if dup_issues:
        check = repository.persist_guardrail_check(
            db,
            actor_user_id=principal.user_id,
            workflow_name="private_document_upload",
            target_type="file_security_scans",
            target_id=scan_row.id,
            outcome=GuardrailOutcome.REVIEW_REQUIRED,
            issues=dup_issues,
            payload_for_hash={"sha256": stored.sha256_hash, "owner_scope": owner_scope},
            correlation_id=correlation_id,
        )
        case = repository.create_guardrail_case(
            db,
            check=check,
            submitted_by_user_id=principal.user_id,
            reason_codes=[i.rule_code for i in dup_issues],
            evidence_refs=[{"file_scan_id": scan_row.id}],
            correlation_id=correlation_id,
        )
        review_case_id = case.id

    db.commit()
    return FileUploadResponse(
        scan_id=scan_row.id,
        storage_key=scan_row.storage_key,
        detected_mime_type=scan_row.detected_mime_type,
        file_size_bytes=scan_row.file_size_bytes,
        sha256_hash=scan_row.sha256_hash,
        scan_status=scan_row.scan_status,
        scanner_engine=scan_row.scanner_engine,
        duplicate_hash_detected=bool(dup_issues),
        review_case_id=review_case_id,
    )


def retrieve_private_document(
    db: Session,
    *,
    principal: AuthenticatedPrincipal,
    scan_id: str,
    settings: Settings,
    ip_address: str | None = None,
    user_agent: str | None = None,
    correlation_id: str | None = None,
) -> tuple[FileSecurityScan, Path]:
    scan_row = repository.get_file_scan(db, scan_id)
    if scan_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    assert_owner_or_admin(
        owner_user_id=scan_row.uploader_user_id,
        actor_user_id=principal.user_id,
        is_admin=principal.has_permission("guardrails.read") or principal.has_permission("sellers.review"),
        resource_label="private document",
    )

    if scan_row.scan_status == "INFECTED":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Quarantined document cannot be downloaded.")

    resolved_root = settings.private_storage_path.resolve()
    file_path = (resolved_root / scan_row.storage_key).resolve()
    if resolved_root not in file_path.parents or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found.")

    record_audit_log(
        db,
        actor_user_id=principal.user_id,
        actor_role="ADMIN" if principal.is_active_admin else "USER",
        action="KYC_DOCUMENT_VIEWED",
        target_type="file_security_scans",
        target_id=scan_row.id,
        correlation_id=correlation_id or str(uuid.uuid4()),
        new_values={
            "owner_scope": scan_row.owner_scope,
            "uploader_user_id": scan_row.uploader_user_id,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.commit()
    return scan_row, file_path


def run_verification_assessment(
    db: Session,
    *,
    principal: AuthenticatedPrincipal,
    payload: VerificationAssessInput,
    correlation_id: str,
) -> GuardrailResponse:
    app_row = db.scalar(
        select(SellerVerificationApplication).where(
            SellerVerificationApplication.id == payload.application_id
        )
    )
    if app_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification application not found.")

    seller = db.scalar(select(SellerProfile).where(SellerProfile.id == app_row.seller_profile_id))
    if seller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller profile not found.")

    assert_owner_or_admin(
        owner_user_id=seller.user_id,
        actor_user_id=principal.user_id,
        is_admin=principal.has_permission("sellers.review") or principal.has_permission("gi.review"),
        resource_label="verification application",
    )

    outcome, issues = evaluate_verification_application(
        db,
        application=app_row,
        evidence_scan_ids=payload.evidence_scan_ids,
    )

    check = repository.persist_guardrail_check(
        db,
        actor_user_id=principal.user_id,
        workflow_name="verification_assessment",
        target_type="seller_verification_applications",
        target_id=app_row.id,
        outcome=outcome,
        issues=issues,
        payload_for_hash=payload.model_dump(mode="json"),
        correlation_id=correlation_id,
    )

    review_case_id: str | None = None
    if outcome == GuardrailOutcome.REVIEW_REQUIRED:
        case = repository.create_guardrail_case(
            db,
            check=check,
            submitted_by_user_id=seller.user_id,
            reason_codes=sorted({i.rule_code for i in issues}),
            evidence_refs=[{"application_id": app_row.id}],
            correlation_id=correlation_id,
        )
        review_case_id = case.id

    db.commit()
    return _build_response(
        outcome=outcome,
        issues=issues,
        correlation_id=correlation_id,
        review_case_id=review_case_id,
        created_resource_id=None,
        business_status=app_row.application_status,
    )


def decide_guardrail_case(
    db: Session,
    *,
    principal: AuthenticatedPrincipal,
    case_id: str,
    payload: AdminCaseDecisionInput,
    correlation_id: str,
    ip_address: str | None = None,
) -> GuardrailCase:
    case = repository.get_guardrail_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guardrail case not found.")

    assert_not_self_approval(
        submitter_user_id=case.submitted_by_user_id,
        reviewer_user_id=principal.user_id,
    )
    prev_status = case.case_status
    repository.record_case_decision(
        db,
        case=case,
        admin_user_id=principal.user_id,
        decision=payload.decision,
        reason=payload.reason,
        correlation_id=correlation_id,
    )
    if case.target_type == "seller_product_listings" and case.target_id:
        linked_listing = db.scalar(
            select(SellerProductListing).where(SellerProductListing.id == case.target_id)
        )
        if linked_listing is not None:
            if payload.decision == "APPROVE":
                linked_listing.listing_status = "ACTIVE"
            elif payload.decision == "REJECT":
                linked_listing.listing_status = "REJECTED"

    record_audit_log(
        db,
        actor_user_id=principal.user_id,
        actor_role="ADMIN",
        action=f"GUARDRAIL_CASE_{payload.decision}",
        target_type="guardrail_cases",
        target_id=case.id,
        reason=payload.reason,
        previous_values={"case_status": prev_status},
        new_values={"case_status": case.case_status},
        correlation_id=correlation_id,
        ip_address=ip_address,
    )
    db.commit()
    return case
