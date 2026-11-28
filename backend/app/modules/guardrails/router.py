"""FastAPI router exposing ASIGS validation, upload, procurement ownership & Admin endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthenticatedPrincipal,
    get_current_principal,
    require_admin_permission,
    require_platform_role,
)
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import SlidingWindowRateLimiter
from app.models.core_models import SupplierLot, SupplierProfile
from app.modules.guardrails import repository, service
from app.modules.guardrails.rules.ownership import assert_owner_or_admin
from app.modules.guardrails.schemas import (
    AdminCaseDecisionInput,
    DealerAssignmentResponseInput,
    DealerProfileValidateInput,
    DealerWholesaleListingInput,
    FileUploadResponse,
    GuardrailCaseSummary,
    GuardrailOutcome,
    GuardrailResponse,
    SellerListingInput,
    SupplierLotInput,
    VerificationAssessInput,
)

router = APIRouter(tags=["ASIGS Guardrails"])
_document_upload_limiter = SlidingWindowRateLimiter(max_requests=20, window_seconds=300)


def _corr_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "missing-correlation-id")


# ---------------------------------------------------------------------------
# Seller Listing Guardrails
# ---------------------------------------------------------------------------
@router.post("/seller/listings/validate", response_model=GuardrailResponse)
def validate_seller_listing(
    payload: SellerListingInput,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> GuardrailResponse:
    return service.evaluate_seller_listing(
        db,
        principal=principal,
        payload=payload,
        correlation_id=_corr_id(request),
        create_record=False,
    )


@router.post("/seller/listings", response_model=GuardrailResponse, status_code=status.HTTP_201_CREATED)
def create_seller_listing(
    payload: SellerListingInput,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> GuardrailResponse:
    res = service.evaluate_seller_listing(
        db,
        principal=principal,
        payload=payload,
        correlation_id=_corr_id(request),
        create_record=True,
    )
    if res.outcome == GuardrailOutcome.BLOCK:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=res.model_dump(mode="json"),
        )
    return res


# ---------------------------------------------------------------------------
# Supplier Lot Guardrails & Ownership
# ---------------------------------------------------------------------------
@router.post("/supplier/lots/validate", response_model=GuardrailResponse)
def validate_supplier_lot(
    payload: SupplierLotInput,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> GuardrailResponse:
    return service.evaluate_supplier_lot(
        db,
        principal=principal,
        payload=payload,
        correlation_id=_corr_id(request),
        create_record=False,
    )


@router.post("/supplier/lots", response_model=GuardrailResponse, status_code=status.HTTP_201_CREATED)
def create_supplier_lot(
    payload: SupplierLotInput,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> GuardrailResponse:
    res = service.evaluate_supplier_lot(
        db,
        principal=principal,
        payload=payload,
        correlation_id=_corr_id(request),
        create_record=True,
    )
    if res.outcome == GuardrailOutcome.BLOCK:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=res.model_dump(mode="json"),
        )
    return res


@router.get("/supplier/lots/{lot_id}")
def get_supplier_lot(
    lot_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    lot = db.scalar(select(SupplierLot).where(SupplierLot.id == lot_id))
    if lot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier lot not found.")
    supplier = db.scalar(select(SupplierProfile).where(SupplierProfile.id == lot.supplier_profile_id))
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier profile not found.")
    assert_owner_or_admin(
        owner_user_id=supplier.user_id,
        actor_user_id=principal.user_id,
        is_admin=principal.has_permission("procurement.read"),
        resource_label="supplier lot",
    )
    return {
        "id": lot.id,
        "lot_number": lot.lot_number,
        "lot_title": lot.lot_title,
        "offered_quantity": str(lot.offered_quantity),
        "lot_status": lot.lot_status,
    }


# ---------------------------------------------------------------------------
# Dealer Profile, Wholesale Listing & Assignment Ownership
# ---------------------------------------------------------------------------
@router.post("/dealer/profile/validate", response_model=GuardrailResponse)
def validate_dealer_profile(
    payload: DealerProfileValidateInput,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> GuardrailResponse:
    return service.validate_dealer_profile(
        db,
        principal=principal,
        payload=payload,
        correlation_id=_corr_id(request),
    )


@router.post("/dealer/wholesale-listings/validate", response_model=GuardrailResponse)
def validate_dealer_wholesale_listing(
    payload: DealerWholesaleListingInput,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> GuardrailResponse:
    return service.validate_dealer_wholesale_listing(
        db,
        principal=principal,
        payload=payload,
        correlation_id=_corr_id(request),
    )


@router.post("/dealer/assignments/{assignment_id}/respond")
def respond_to_assignment(
    assignment_id: str,
    payload: DealerAssignmentResponseInput,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(require_platform_role("DEALER")),
    db: Session = Depends(get_db),
) -> dict:
    return service.respond_to_dealer_assignment(
        db,
        principal=principal,
        assignment_id=assignment_id,
        payload=payload,
        correlation_id=_corr_id(request),
    )


# ---------------------------------------------------------------------------
# Secure Private Document Upload & Authorized Retrieval
# ---------------------------------------------------------------------------
@router.post("/guardrails/documents/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    response: Response,
    owner_scope: str = Form(default="seller_document"),
    file: UploadFile = File(...),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> FileUploadResponse:
    allowed, retry_after = _document_upload_limiter.allow(f"upload:{principal.user_id}")
    if not allowed:
        response.headers["Retry-After"] = str(retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Document upload rate limit exceeded. Please wait before uploading again.",
        )

    max_bytes = int(settings.max_upload_size_bytes)
    chunks: list[bytes] = []
    total_read = 0
    chunk_size = 65_536
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {max_bytes} bytes.",
            )
        chunks.append(chunk)
    raw_bytes = b"".join(chunks)

    return service.upload_private_document(
        db,
        principal=principal,
        owner_scope=owner_scope,
        original_filename=file.filename or "",
        claimed_content_type=file.content_type,
        payload=raw_bytes,
        settings=settings,
        correlation_id=_corr_id(request),
    )


@router.get("/guardrails/documents/{scan_id}")
def download_document(
    scan_id: str,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    scan_row, file_path = service.retrieve_private_document(
        db,
        principal=principal,
        scan_id=scan_id,
        settings=settings,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        correlation_id=_corr_id(request),
    )
    return FileResponse(
        path=file_path,
        media_type=scan_row.detected_mime_type,
        filename=f"{scan_row.id}{file_path.suffix}",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


# ---------------------------------------------------------------------------
# GI vs Non-GI Verification Assessment Gate
# ---------------------------------------------------------------------------
@router.post("/guardrails/verification/assess", response_model=GuardrailResponse)
def assess_verification(
    payload: VerificationAssessInput,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> GuardrailResponse:
    res = service.run_verification_assessment(
        db,
        principal=principal,
        payload=payload,
        correlation_id=_corr_id(request),
    )
    if res.outcome == GuardrailOutcome.BLOCK:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=res.model_dump(mode="json"),
        )
    return res


# ---------------------------------------------------------------------------
# Admin Guardrail Center
# ---------------------------------------------------------------------------
@router.get("/admin/guardrail/cases", response_model=list[GuardrailCaseSummary])
def list_cases(
    case_status: str | None = None,
    _admin: AuthenticatedPrincipal = Depends(require_admin_permission("guardrails.read")),
    db: Session = Depends(get_db),
) -> list[GuardrailCaseSummary]:
    rows = repository.list_guardrail_cases(db, status_filter=case_status)
    return [
        GuardrailCaseSummary(
            id=r.id,
            case_number=r.case_number,
            workflow_name=r.workflow_name,
            target_type=r.target_type,
            target_id=r.target_id,
            guardrail_outcome=r.guardrail_outcome,
            case_status=r.case_status,
            reason_codes=r.reason_codes_json,
            evidence_refs=r.evidence_refs_json,
            decision_reason=r.decision_reason,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/admin/guardrail/cases/{case_id}", response_model=GuardrailCaseSummary)
def get_case(
    case_id: str,
    _admin: AuthenticatedPrincipal = Depends(require_admin_permission("guardrails.read")),
    db: Session = Depends(get_db),
) -> GuardrailCaseSummary:
    r = repository.get_guardrail_case(db, case_id)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guardrail case not found.")
    return GuardrailCaseSummary(
        id=r.id,
        case_number=r.case_number,
        workflow_name=r.workflow_name,
        target_type=r.target_type,
        target_id=r.target_id,
        guardrail_outcome=r.guardrail_outcome,
        case_status=r.case_status,
        reason_codes=r.reason_codes_json,
        evidence_refs=r.evidence_refs_json,
        decision_reason=r.decision_reason,
        created_at=r.created_at,
    )


@router.post("/admin/guardrail/cases/{case_id}/decision", response_model=GuardrailCaseSummary)
def decide_case(
    case_id: str,
    payload: AdminCaseDecisionInput,
    request: Request,
    admin: AuthenticatedPrincipal = Depends(require_admin_permission("guardrails.decide")),
    db: Session = Depends(get_db),
) -> GuardrailCaseSummary:
    r = service.decide_guardrail_case(
        db,
        principal=admin,
        case_id=case_id,
        payload=payload,
        correlation_id=_corr_id(request),
        ip_address=request.client.host if request.client else None,
    )
    return GuardrailCaseSummary(
        id=r.id,
        case_number=r.case_number,
        workflow_name=r.workflow_name,
        target_type=r.target_type,
        target_id=r.target_id,
        guardrail_outcome=r.guardrail_outcome,
        case_status=r.case_status,
        reason_codes=r.reason_codes_json,
        evidence_refs=r.evidence_refs_json,
        decision_reason=r.decision_reason,
        created_at=r.created_at,
    )


@router.get("/admin/guardrail/rules")
def list_rules(
    _admin: AuthenticatedPrincipal = Depends(require_admin_permission("guardrails.read")),
    db: Session = Depends(get_db),
) -> list[dict]:
    rules = repository.list_guardrail_rules(db)
    return [
        {
            "id": r.id,
            "rule_code": r.rule_code,
            "layer": r.layer,
            "name": r.name,
            "default_outcome": r.default_outcome,
            "is_active": r.is_active,
            "rule_version": r.rule_version,
        }
        for r in rules
    ]
