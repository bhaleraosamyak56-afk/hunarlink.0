"""Clerk JWT -> HunarLink DB user synchronization & Artisan onboarding endpoints.

Security invariants:
  1. Identity (`clerk_user_id`) comes ONLY from the cryptographically verified
     Clerk RS256 JWT `sub` claim — never from the request body.
  2. Self-sync can ONLY assign `CUSTOMER` or `DIRECT_SELLER` roles; `ADMIN`
     can never be granted via API.
  3. Artisan verification submissions persist `verification_status='SUBMITTED'`
     (never self-assigned `APPROVED`), preserving ASIGS anti-fraud guardrails.
"""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.admin_security import create_admin_session_token, verify_admin_password
from app.core.audit import record_audit_log
from app.core.auth import (
    AuthenticatedPrincipal,
    get_current_principal,
    get_verified_clerk_claims,
    require_admin_permission,
)
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import SlidingWindowRateLimiter
from app.models.base import new_uuid, utcnow
from app.models.core_models import (
    AdminCredential,
    AdminPermission,
    AdminProfile,
    AdminRole,
    AdminRolePermission,
    AdminUserRole,
    PlatformRole,
    RetailOrder,
    SellerDocument,
    SellerProductListing,
    SellerProfile,
    SellerVerificationApplication,
    User,
    UserAddress,
    UserLoginLog,
    UserRoleAssignment,
)
from app.models.guardrail_models import FileSecurityScan
from app.modules.auth.schemas import (
    AccountCheckRequest,
    AccountCheckResponse,
    AdminPasswordLoginRequest,
    AdminPasswordLoginResponse,
    ArtisanVerificationSubmitRequest,
    ArtisanVerificationSubmitResponse,
    AuthSyncRequest,
    AuthUserProfileResponse,
    SellerProfileBrief,
    UserAddressCreateRequest,
    UserAddressResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication & User Sync"])
_admin_login_limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)

ROLE_CODE_MAP = {
    "buyer": ("CUSTOMER", "Retail Customer"),
    "artisan": ("DIRECT_SELLER", "Direct Artisan Seller"),
}


def _ensure_platform_role(db: Session, code: str, default_name: str) -> PlatformRole:
    role = db.scalar(select(PlatformRole).where(PlatformRole.code == code))
    if role is None:
        role = PlatformRole(id=new_uuid(), code=code, name=default_name, is_active=True)
        db.add(role)
        db.flush()
    return role


def _ensure_user_role(db: Session, user_id: str, role_code: str, role_name: str) -> None:
    role = _ensure_platform_role(db, role_code, role_name)
    existing = db.scalar(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.platform_role_id == role.id,
        )
    )
    if existing is None:
        db.add(
            UserRoleAssignment(
                id=new_uuid(),
                user_id=user_id,
                platform_role_id=role.id,
                assignment_status="ACTIVE",
                granted_at=utcnow(),
            )
        )
        db.flush()
    elif existing.assignment_status != "ACTIVE":
        existing.assignment_status = "ACTIVE"
        existing.granted_at = utcnow()


def _slugify_store(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "artisan-atelier"
    return f"{base[:150]}-{uuid.uuid4().hex[:6]}"


def _load_admin_access(db: Session, user_id: str, role_codes: list[str]) -> tuple[bool, list[str]]:
    if "ADMIN" not in role_codes:
        return False, []
    admin_profile = db.scalar(
        select(AdminProfile).where(
            AdminProfile.user_id == user_id,
            AdminProfile.admin_status == "ACTIVE",
        )
    )
    if admin_profile is None:
        return False, []
    perms = sorted(
        set(
            db.scalars(
                select(AdminPermission.code)
                .join(
                    AdminRolePermission,
                    AdminRolePermission.admin_permission_id == AdminPermission.id,
                )
                .join(AdminRole, AdminRole.id == AdminRolePermission.admin_role_id)
                .join(AdminUserRole, AdminUserRole.admin_role_id == AdminRole.id)
                .where(
                    AdminUserRole.admin_profile_id == admin_profile.id,
                    AdminUserRole.is_active == True,  # noqa: E712
                    AdminRole.is_active == True,  # noqa: E712
                )
            ).all()
        )
    )
    return True, perms


def _build_seller_brief(db: Session, seller: SellerProfile | None) -> SellerProfileBrief | None:
    if seller is None:
        return None
    latest_app = db.scalar(
        select(SellerVerificationApplication)
        .where(SellerVerificationApplication.seller_profile_id == seller.id)
        .order_by(SellerVerificationApplication.created_at.desc())
        .limit(1)
    )
    meta = (
        latest_app.submitted_metadata
        if latest_app and isinstance(latest_app.submitted_metadata, dict)
        else {}
    )
    return SellerProfileBrief(
        seller_profile_id=seller.id,
        store_name=seller.store_name,
        store_slug=seller.store_slug,
        craft_specialty=seller.craft_specialty,
        workshop_district=seller.workshop_district,
        verification_path=seller.verification_path,
        verification_status=seller.verification_status,
        profile_status=seller.profile_status,
        claimed_gi_authorized_user_no=seller.claimed_gi_authorized_user_no,
        latest_application_id=latest_app.id if latest_app else None,
        latest_application_number=latest_app.application_number if latest_app else None,
        latest_application_status=latest_app.application_status if latest_app else None,
        artisan_card_scan_id=meta.get("artisan_card_scan_id"),
        review_decision_notes=latest_app.review_decision_notes if latest_app else None,
    )


def _build_user_response(
    db: Session, user: User, *, is_new_user: bool = False
) -> AuthUserProfileResponse:
    role_codes = sorted(
        set(
            db.scalars(
                select(PlatformRole.code)
                .join(
                    UserRoleAssignment,
                    UserRoleAssignment.platform_role_id == PlatformRole.id,
                )
                .where(
                    UserRoleAssignment.user_id == user.id,
                    UserRoleAssignment.assignment_status == "ACTIVE",
                    PlatformRole.is_active == True,  # noqa: E712
                )
            ).all()
        )
    )
    is_admin, admin_permissions = _load_admin_access(db, user.id, role_codes)
    seller = db.scalar(select(SellerProfile).where(SellerProfile.user_id == user.id))
    seller_brief = _build_seller_brief(db, seller)
    is_artisan = ("DIRECT_SELLER" in role_codes) or (seller is not None)
    artisan_verified = bool(
        seller is not None
        and seller.verification_status == "APPROVED"
        and seller.profile_status == "ACTIVE"
    )
    return AuthUserProfileResponse(
        synced=True,
        is_new_user=is_new_user,
        user_id=user.id,
        clerk_user_id=user.clerk_user_id,
        email=user.email,
        email_verified=user.email_verified,
        first_name=user.first_name,
        last_name=user.last_name,
        display_name=user.display_name,
        phone=user.phone,
        account_status=user.account_status,
        roles=role_codes,
        is_artisan=is_artisan,
        artisan_verified=artisan_verified,
        is_admin=is_admin,
        admin_permissions=admin_permissions,
        seller_profile=seller_brief,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _get_user_active_roles(db: Session, user_id: str) -> list[str]:
    return sorted(
        set(
            db.scalars(
                select(PlatformRole.code)
                .join(
                    UserRoleAssignment,
                    UserRoleAssignment.platform_role_id == PlatformRole.id,
                )
                .where(
                    UserRoleAssignment.user_id == user_id,
                    UserRoleAssignment.assignment_status == "ACTIVE",
                    PlatformRole.is_active == True,  # noqa: E712
                )
            ).all()
        )
    )


def _is_admin_account(db: Session, user_id: str, role_codes: list[str]) -> bool:
    if "ADMIN" in role_codes:
        return True
    if (
        db.scalar(
            select(AdminProfile.id).where(
                AdminProfile.user_id == user_id,
                AdminProfile.admin_status == "ACTIVE",
            )
        )
        is not None
    ):
        return True
    try:
        AdminCredential.__table__.create(bind=db.get_bind(), checkfirst=True)
        if (
            db.scalar(
                select(AdminCredential.id).where(
                    AdminCredential.user_id == user_id,
                    AdminCredential.is_active == True,  # noqa: E712
                )
            )
            is not None
        ):
            return True
    except Exception:
        pass
    return False


def _record_auth_event(
    db: Session,
    *,
    user: User,
    role_code: str,
    event_type: str,
    auth_method: str,
    request: Request,
) -> None:
    UserLoginLog.__table__.create(bind=db.get_bind(), checkfirst=True)
    ip_addr = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    db.add(
        UserLoginLog(
            id=new_uuid(),
            user_id=user.id,
            role_code=role_code,
            auth_event_type=event_type,
            auth_method=auth_method,
            email=user.email,
            ip_address=ip_addr[:64] if ip_addr else None,
            user_agent=ua[:500] if ua else None,
        )
    )


_account_check_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=60)


@router.post("/check-account", response_model=AccountCheckResponse)
def check_existing_account(
    payload: AccountCheckRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AccountCheckResponse:
    """Check whether an email already exists in the HunarLink DB and enforce role isolation."""
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = _account_check_limiter.allow(f"check-account:{client_ip}")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many account check requests. Retry in {retry_after}s.",
        )

    clean_email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == clean_email))
    if user is None:
        return AccountCheckResponse(exists=False)

    role_codes = _get_user_active_roles(db, user.id)
    seller = db.scalar(select(SellerProfile).where(SellerProfile.user_id == user.id))
    is_admin = _is_admin_account(db, user.id, role_codes)
    is_buyer = "CUSTOMER" in role_codes
    is_artisan = ("DIRECT_SELLER" in role_codes) or (seller is not None)

    has_requested_role: bool | None = None
    role_conflict = False
    conflict_message: str | None = None

    if payload.requested_role == "buyer":
        if is_admin:
            has_requested_role = False
            role_conflict = True
            conflict_message = (
                "This email belongs to an Administrator account. Please sign in at /admin."
            )
        elif not is_buyer:
            has_requested_role = False
            role_conflict = True
            conflict_message = (
                "This email is registered as an Artisan (DIRECT_SELLER), not a Buyer. "
                "Please switch to the Artisan role or register with a separate Buyer email."
            )
        else:
            has_requested_role = True
    elif payload.requested_role == "artisan":
        if is_admin:
            has_requested_role = False
            role_conflict = True
            conflict_message = (
                "This email belongs to an Administrator account. Please sign in at /admin."
            )
        elif not is_artisan:
            has_requested_role = False
            role_conflict = True
            conflict_message = (
                "This email is registered as a Buyer (CUSTOMER), not an Artisan. "
                "Please switch to Buyer or register with a separate Artisan email."
            )
        else:
            has_requested_role = True

    return AccountCheckResponse(
        exists=True,
        roles=role_codes,
        is_buyer=is_buyer,
        is_artisan=is_artisan,
        is_admin=is_admin,
        artisan_verified=bool(seller is not None and seller.verification_status == "APPROVED"),
        artisan_verification_status=seller.verification_status if seller is not None else "UNVERIFIED",
        has_requested_role=has_requested_role,
        role_conflict=role_conflict,
        conflict_message=conflict_message,
        last_login_at=user.last_login_at,
    )


@router.post("/sync", response_model=AuthUserProfileResponse)
def sync_authenticated_user(
    payload: AuthSyncRequest,
    request: Request,
    claims: dict = Depends(get_verified_clerk_claims),
    db: Session = Depends(get_db),
) -> AuthUserProfileResponse:
    """Upsert a Clerk-authenticated user into HunarLink's database (`users` + roles).

    Enforces strict role isolation:
      - New registration grants ONLY the requested role (`CUSTOMER` or `DIRECT_SELLER`).
      - Existing accounts cannot sign in under a different role (returns 403).
      - Admin accounts (`admin_credentials` / `ADMIN`) cannot sign in via Buyer/Artisan portals.
      - Records `REGISTER` vs `LOGIN` events in `user_login_logs` and `users.last_login_at`.
    """
    clerk_user_id = str(claims["sub"]).strip()
    clean_email = payload.email.strip().lower()
    if "@" not in clean_email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A valid email address is required.",
        )

    user = db.scalar(select(User).where(User.clerk_user_id == clerk_user_id))
    is_new_user = False
    role_code, role_name = ROLE_CODE_MAP[payload.requested_role]

    if user is None:
        existing_by_email = db.scalar(select(User).where(User.email == clean_email))
        if existing_by_email is not None:
            if payload.auth_mode == "signup":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This account already exists in HunarLink. You cannot register again — please log in instead.",
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email is already registered under a different identity.",
            )
        if payload.auth_mode == "signin":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No registered HunarLink account found for this email. Please register first.",
            )
        is_new_user = True
        first_name = payload.first_name.strip() or clean_email.split("@")[0][:100]
        last_name = (payload.last_name or "").strip() or None
        display_name = (payload.display_name or "").strip() or (
            f"{first_name} {last_name}".strip() if last_name else first_name
        )
        user = User(
            id=new_uuid(),
            clerk_user_id=clerk_user_id,
            email=clean_email,
            email_verified=bool(payload.email_verified),
            phone=(payload.phone or "").strip() or None,
            first_name=first_name[:100],
            last_name=last_name[:100] if last_name else None,
            display_name=display_name[:160],
            preferred_currency="INR",
            account_status="ACTIVE",
            last_login_at=None,
        )
        db.add(user)
        db.flush()
        _ensure_user_role(db, user.id, role_code, role_name)
        _record_auth_event(
            db,
            user=user,
            role_code=role_code,
            event_type="REGISTER",
            auth_method="clerk_signup" if payload.auth_mode == "signup" else "clerk_sync",
            request=request,
        )
    else:
        if payload.auth_mode == "signup":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This account already exists in HunarLink. You cannot register again — please log in instead.",
            )
        if user.account_status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account is not active (status={user.account_status}).",
            )

        existing_roles = _get_user_active_roles(db, user.id)
        if _is_admin_account(db, user.id, existing_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator accounts must sign in through the dedicated /admin login portal.",
            )
        if payload.requested_role == "buyer" and "CUSTOMER" not in existing_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role mismatch: this email is registered as an Artisan (DIRECT_SELLER), not a Buyer. Please sign in with the Artisan role.",
            )
        if payload.requested_role == "artisan" and "DIRECT_SELLER" not in existing_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role mismatch: this email is registered as a Buyer (CUSTOMER), not an Artisan. Please register a separate Artisan account.",
            )

        if payload.first_name.strip():
            user.first_name = payload.first_name.strip()[:100]
        if payload.last_name is not None:
            user.last_name = payload.last_name.strip()[:100] or None
        if payload.display_name is not None and payload.display_name.strip():
            user.display_name = payload.display_name.strip()[:160]
        if payload.phone is not None and payload.phone.strip():
            user.phone = payload.phone.strip()[:32]
        if payload.email_verified:
            user.email_verified = True
        user.last_login_at = utcnow()
        user.updated_at = utcnow()

        _record_auth_event(
            db,
            user=user,
            role_code=role_code,
            event_type="LOGIN",
            auth_method="clerk_signin" if payload.auth_mode == "signin" else "clerk_sync",
            request=request,
        )

    record_audit_log(
        db,
        actor_user_id=user.id,
        actor_role=role_code,
        action="USER_SYNC_CREATED" if is_new_user else "USER_SYNC_UPDATED",
        target_type="users",
        target_id=user.id,
        correlation_id=getattr(request.state, "correlation_id", "") or str(uuid.uuid4()),
        new_values={
            "requested_role": payload.requested_role,
            "is_new_user": is_new_user,
            "auth_event_type": "REGISTER" if is_new_user else "LOGIN",
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    db.commit()
    db.refresh(user)
    return _build_user_response(db, user, is_new_user=is_new_user)


@router.get("/me", response_model=AuthUserProfileResponse)
def get_my_profile(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> AuthUserProfileResponse:
    """Return the authenticated caller's DB profile, roles, and seller status."""
    user = db.scalar(select(User).where(User.id == principal.user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _build_user_response(db, user, is_new_user=False)


@router.post(
    "/artisan-verification",
    response_model=ArtisanVerificationSubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_artisan_verification(
    payload: ArtisanVerificationSubmitRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> ArtisanVerificationSubmitResponse:
    """Persist an authenticated artisan's GI or Standard verification application.

    - Standard (`NON_GI` / `STANDARD`) applications require an uploaded Artisan Card
      image/PDF (`artisan_card_scan_id` from `/api/v1/guardrails/documents/upload`) so
      administrators can inspect the physical card in `/admin`.
    - Applications stay staged in `seller_verification_applications` (`SUBMITTED`) with
      `SellerProfile.profile_status='DRAFT'` and `verification_status='SUBMITTED'`
      (excluded from public `/api/v1/artisans`) until an Admin approves them in `/admin`,
      which promotes the record straight into the live verified artisans table.
    """
    user = db.scalar(select(User).where(User.id == principal.user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if "DIRECT_SELLER" not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only registered Artisan accounts (DIRECT_SELLER) can submit artisan verification. Please register a separate Artisan account.",
        )

    normalized_path = "GI" if payload.verification_path == "GI" else "NON_GI"
    claimed_gi = (payload.claimed_gi_code or "").strip() or None
    card_scan_id = (payload.artisan_card_scan_id or "").strip() or None

    if normalized_path == "GI" and not claimed_gi:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="GI Certified track requires a GI Registration / Authorized User number.",
        )

    scan_row: FileSecurityScan | None = None
    if card_scan_id:
        scan_row = db.scalar(
            select(FileSecurityScan).where(FileSecurityScan.id == card_scan_id)
        )
        if scan_row is None or scan_row.uploader_user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Uploaded Artisan Card document was not found for your account. Please upload it again.",
            )
        if scan_row.scan_status == "INFECTED":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Uploaded Artisan Card failed security scanning.",
            )
    elif normalized_path == "NON_GI":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Standard Artisan registration requires uploading your Artisan Card image for Admin verification.",
        )

    if payload.phone and payload.phone.strip():
        user.phone = payload.phone.strip()[:32]
        user.updated_at = utcnow()

    seller = db.scalar(select(SellerProfile).where(SellerProfile.user_id == user.id))
    if seller is None:
        seller = SellerProfile(
            id=new_uuid(),
            user_id=user.id,
            store_name=payload.store_name.strip(),
            store_slug=_slugify_store(payload.store_name.strip()),
            craft_specialty=payload.craft_specialty.strip(),
            workshop_district=payload.workshop_district.strip(),
            verification_path=normalized_path,
            profile_status="DRAFT",
            verification_status="SUBMITTED",
            claimed_gi_authorized_user_no=claimed_gi,
            bio=(payload.skill_description or "").strip()[:1000] or None,
        )
        db.add(seller)
        db.flush()
    else:
        seller.store_name = payload.store_name.strip()
        seller.craft_specialty = payload.craft_specialty.strip()
        seller.workshop_district = payload.workshop_district.strip()
        seller.verification_path = normalized_path
        seller.claimed_gi_authorized_user_no = claimed_gi
        if payload.skill_description and payload.skill_description.strip():
            seller.bio = payload.skill_description.strip()[:1000]
        if seller.verification_status != "APPROVED":
            seller.verification_status = "SUBMITTED"
            seller.profile_status = "DRAFT"

    app_number = f"HL-VER-{utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    application = SellerVerificationApplication(
        id=new_uuid(),
        seller_profile_id=seller.id,
        application_number=app_number,
        verification_path=normalized_path,
        application_status="SUBMITTED",
        claimed_gi_code=claimed_gi,
        claimed_craft_cluster=payload.workshop_district.strip(),
        submitted_metadata={
            "craft_specialty": payload.craft_specialty.strip(),
            "skill_description": (payload.skill_description or "").strip()[:1000],
            "artisan_card_scan_id": scan_row.id if scan_row else None,
            "artisan_card_filename": scan_row.original_filename if scan_row else None,
            "artisan_card_mime": scan_row.detected_mime_type if scan_row else None,
            "phone": (payload.phone or user.phone or "").strip(),
        },
    )
    db.add(application)
    db.flush()

    if scan_row is not None:
        existing_doc = db.scalar(
            select(SellerDocument).where(SellerDocument.storage_key == scan_row.storage_key)
        )
        if existing_doc is None:
            doc_type = "GI_AUTHORIZED_USER_CERT" if normalized_path == "GI" else "IDENTITY_PROOF"
            db.add(
                SellerDocument(
                    id=new_uuid(),
                    seller_profile_id=seller.id,
                    application_id=application.id,
                    document_type=doc_type,
                    storage_key=scan_row.storage_key,
                    original_filename=scan_row.original_filename,
                    detected_mime_type=scan_row.detected_mime_type,
                    file_size_bytes=scan_row.file_size_bytes,
                    sha256_hash=scan_row.sha256_hash,
                    scan_status=scan_row.scan_status if scan_row.scan_status in {"PENDING_SCAN", "CLEAN", "INFECTED", "SCAN_ERROR"} else "CLEAN",
                    verification_status="PENDING",
                    uploaded_by_user_id=user.id,
                )
            )
        else:
            existing_doc.application_id = application.id
            existing_doc.verification_status = "PENDING"

    record_audit_log(
        db,
        actor_user_id=user.id,
        actor_role="DIRECT_SELLER",
        action="ARTISAN_VERIFICATION_SUBMITTED",
        target_type="seller_verification_applications",
        target_id=application.id,
        correlation_id=getattr(request.state, "correlation_id", "") or str(uuid.uuid4()),
        new_values={
            "application_number": app_number,
            "verification_path": normalized_path,
            "workshop_district": payload.workshop_district.strip(),
            "artisan_card_scan_id": scan_row.id if scan_row else None,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    db.commit()
    db.refresh(seller)
    db.refresh(application)

    brief = _build_seller_brief(db, seller)
    assert brief is not None
    return ArtisanVerificationSubmitResponse(
        application_id=application.id,
        application_number=application.application_number,
        application_status=application.application_status,
        seller_profile=brief,
    )


@router.get("/addresses", response_model=list[UserAddressResponse])
def list_my_addresses(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[UserAddressResponse]:
    rows = db.scalars(
        select(UserAddress)
        .where(UserAddress.user_id == principal.user_id, UserAddress.is_active == True)  # noqa: E712
        .order_by(UserAddress.is_default.desc(), UserAddress.created_at.desc())
    ).all()
    return [
        UserAddressResponse(
            id=a.id,
            address_label=a.address_label,
            recipient_name=a.recipient_name,
            recipient_phone=a.recipient_phone,
            line1=a.line1,
            line2=a.line2,
            city=a.city,
            state_province=a.state_province,
            postal_code=a.postal_code,
            is_default=a.is_default,
            created_at=a.created_at,
        )
        for a in rows
    ]


@router.post("/addresses", response_model=UserAddressResponse, status_code=status.HTTP_201_CREATED)
def create_my_address(
    payload: UserAddressCreateRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> UserAddressResponse:
    existing = db.scalars(
        select(UserAddress).where(
            UserAddress.user_id == principal.user_id,
            UserAddress.is_active == True,  # noqa: E712
        )
    ).all()
    make_default = payload.is_default or len(existing) == 0
    if make_default:
        for row in existing:
            if row.is_default:
                row.is_default = False
        db.flush()

    addr = UserAddress(
        id=new_uuid(),
        user_id=principal.user_id,
        address_label=payload.address_label.strip().upper()[:50],
        recipient_name=payload.recipient_name.strip(),
        recipient_phone=payload.recipient_phone.strip(),
        line1=payload.line1.strip(),
        line2=(payload.line2 or "").strip() or None,
        city=payload.city.strip(),
        state_province=payload.state_province.strip(),
        postal_code=payload.postal_code.strip(),
        country_code="IN",
        is_default=make_default,
        is_active=True,
    )
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return UserAddressResponse(
        id=addr.id,
        address_label=addr.address_label,
        recipient_name=addr.recipient_name,
        recipient_phone=addr.recipient_phone,
        line1=addr.line1,
        line2=addr.line2,
        city=addr.city,
        state_province=addr.state_province,
        postal_code=addr.postal_code,
        is_default=addr.is_default,
        created_at=addr.created_at,
    )


@router.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_address(
    address_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> None:
    addr = db.scalar(
        select(UserAddress).where(
            UserAddress.id == address_id,
            UserAddress.user_id == principal.user_id,
            UserAddress.is_active == True,  # noqa: E712
        )
    )
    if addr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found.")
    addr.is_active = False
    addr.is_default = False
    db.commit()


@router.post("/admin-login", response_model=AdminPasswordLoginResponse)
def admin_password_login(
    payload: AdminPasswordLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AdminPasswordLoginResponse:
    """Dedicated login strictly for DB-provisioned Admin accounts (zero self-registration)."""
    normalized_email = payload.email.strip().lower()
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = _admin_login_limiter.allow(f"admin-login:{client_ip}:{normalized_email}")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed admin sign-in attempts. Retry in {retry_after}s.",
        )

    # Ensure table exists seamlessly if backend starts before Alembic 0003 ran.
    AdminCredential.__table__.create(bind=db.get_bind(), checkfirst=True)

    cred = db.scalar(
        select(AdminCredential).where(
            AdminCredential.email == normalized_email,
            AdminCredential.is_active == True,  # noqa: E712
        )
    )
    if cred is None or not verify_admin_password(payload.password, cred.password_hash):
        record_audit_log(
            db,
            actor_user_id=None,
            actor_role="ANONYMOUS",
            action="ADMIN_LOGIN_FAILED",
            target_type="admin_credentials",
            target_id=normalized_email,
            correlation_id=getattr(request.state, "correlation_id", "") or str(uuid.uuid4()),
            new_values={"ip": client_ip},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrator email or password.",
        )

    user = db.scalar(select(User).where(User.id == cred.user_id))
    if user is None or user.account_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator account is not active.",
        )

    role_codes = sorted(
        set(
            db.scalars(
                select(PlatformRole.code)
                .join(
                    UserRoleAssignment,
                    UserRoleAssignment.platform_role_id == PlatformRole.id,
                )
                .where(
                    UserRoleAssignment.user_id == user.id,
                    UserRoleAssignment.assignment_status == "ACTIVE",
                    PlatformRole.is_active == True,  # noqa: E712
                )
            ).all()
        )
    )
    is_admin, admin_permissions = _load_admin_access(db, user.id, role_codes)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges have been revoked for this account.",
        )

    cred.last_login_at = utcnow()
    user.last_login_at = utcnow()
    _record_auth_event(
        db,
        user=user,
        role_code="ADMIN",
        event_type="LOGIN",
        auth_method="admin_password",
        request=request,
    )
    record_audit_log(
        db,
        actor_user_id=user.id,
        actor_role="ADMIN",
        action="ADMIN_LOGIN_SUCCESS",
        target_type="admin_credentials",
        target_id=cred.id,
        correlation_id=getattr(request.state, "correlation_id", "") or str(uuid.uuid4()),
        new_values={"email": cred.email, "ip": client_ip},
    )
    db.commit()

    token, ttl = create_admin_session_token(
        user_id=user.id,
        email=cred.email,
        settings=settings,
    )
    return AdminPasswordLoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=ttl,
        user_id=user.id,
        email=cred.email,
        display_name=user.display_name or f"{user.first_name} {user.last_name or ''}".strip(),
        admin_permissions=admin_permissions,
    )
