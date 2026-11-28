"""Pydantic schemas for Clerk -> HunarLink DB user synchronization."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AuthSyncRequest(BaseModel):
    """Profile metadata supplied alongside a verified Clerk RS256 JWT.

    Security notes:
      - `clerk_user_id` is NEVER accepted from the body; it is read exclusively
        from the verified JWT `sub` claim.
      - `requested_role` only allows non-privileged self-onboarding roles
        (`buyer` -> CUSTOMER, `artisan` -> DIRECT_SELLER). ADMIN is forbidden.
    """

    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=3, max_length=255)
    email_verified: bool = False
    first_name: str = Field(default="Collector", min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    display_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    requested_role: Literal["buyer", "artisan"] = "buyer"
    auth_mode: Literal["signup", "signin", "sync"] = "sync"
    dpdp_consent_accepted: bool | None = None
    age_confirmed: bool | None = None
    marketing_opt_in: bool | None = None
    policy_version: str = Field(default="2026-11-v1", max_length=32)


class AccountCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=3, max_length=255)
    requested_role: Literal["buyer", "artisan"] | None = None


class AccountCheckResponse(BaseModel):
    exists: bool
    account_role: str | None = None
    roles: list[str] = Field(default_factory=list)
    is_buyer: bool = False
    is_artisan: bool = False
    is_admin: bool = False
    artisan_verified: bool = False
    artisan_verification_status: str | None = None
    has_requested_role: bool | None = None
    role_conflict: bool = False
    conflict_message: str | None = None
    last_login_at: datetime | None = None


class SellerProfileBrief(BaseModel):
    seller_profile_id: str
    store_name: str
    store_slug: str
    craft_specialty: str | None = None
    workshop_district: str | None = None
    verification_path: str
    verification_status: str
    profile_status: str
    claimed_gi_authorized_user_no: str | None = None
    latest_application_id: str | None = None
    latest_application_number: str | None = None
    latest_application_status: str | None = None
    artisan_card_scan_id: str | None = None
    digilocker_verification_id: str | None = None
    digilocker_mode: str | None = None
    digilocker_issuer_name: str | None = None
    digilocker_card_number: str | None = None
    digilocker_holder_name: str | None = None
    digilocker_doc_uri: str | None = None
    digilocker_fetched_at: str | None = None
    review_decision_notes: str | None = None


class AuthUserProfileResponse(BaseModel):
    synced: bool = True
    is_new_user: bool = False
    user_id: str
    clerk_user_id: str
    email: str
    email_verified: bool
    first_name: str
    last_name: str | None = None
    display_name: str | None = None
    phone: str | None = None
    account_role: str = "BUYER"
    account_status: str
    roles: list[str]
    is_artisan: bool = False
    artisan_verified: bool = False
    is_admin: bool = False
    admin_permissions: list[str] = Field(default_factory=list)
    seller_profile: SellerProfileBrief | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DeleteAccountRequest(BaseModel):
    """Self-service account deletion request after current-password / factor reverification."""

    model_config = ConfigDict(extra="forbid")

    current_password: str | None = Field(default=None, max_length=256)
    reason: str | None = Field(default=None, max_length=500)


class DeleteAccountResponse(BaseModel):
    deleted: bool = True
    anonymized: bool = True
    purged: bool = False
    clerk_deleted: bool = False
    clerk_deleted_count: int = 0
    message: str


class AdminDeleteUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


class ArtisanVerificationSubmitRequest(BaseModel):
    """Artisan GI or Standard verification submission stored in seller_verification_applications."""

    model_config = ConfigDict(extra="forbid")

    store_name: str = Field(..., min_length=2, max_length=160)
    craft_specialty: str = Field(..., min_length=2, max_length=160)
    workshop_district: str = Field(..., min_length=2, max_length=100)
    verification_path: Literal["GI", "NON_GI", "STANDARD"] = "NON_GI"
    claimed_gi_code: str | None = Field(default=None, max_length=120)
    digilocker_verification_id: str | None = Field(default=None, max_length=64)
    artisan_card_scan_id: str | None = Field(default=None, max_length=64)
    skill_description: str | None = Field(default=None, max_length=2000)
    phone: str | None = Field(default=None, max_length=32)


class DigiLockerIssuerItem(BaseModel):
    issuer_id: str
    issuer_name: str
    doc_type: str
    label: str


class DigiLockerStatusResponse(BaseModel):
    mode: Literal["live", "sandbox"]
    live_configured: bool
    issuers: list[DigiLockerIssuerItem] = Field(default_factory=list)


class DigiLockerStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    return_to: str | None = Field(default="/auth?tab=verify", max_length=255)


class DigiLockerStartResponse(BaseModel):
    verification_id: str
    state: str
    mode: Literal["live", "sandbox"]
    authorize_url: str | None = None
    issuers: list[DigiLockerIssuerItem] = Field(default_factory=list)
    expires_at: datetime


class DigiLockerSandboxCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_id: str = Field(..., min_length=8, max_length=64)
    issuer_id: str = Field(default="in.gov.handicrafts", min_length=3, max_length=128)
    artisan_card_number: str = Field(..., min_length=4, max_length=100)
    card_holder_name: str = Field(..., min_length=2, max_length=160)
    craft_category: str = Field(default="Kashmiri Handloom & Craft", min_length=2, max_length=160)
    district: str = Field(default="Srinagar", min_length=2, max_length=120)


class DigiLockerVerificationResponse(BaseModel):
    verification_id: str
    mode: str
    status: str
    issuer_id: str | None = None
    issuer_name: str | None = None
    doc_type: str | None = None
    doc_uri: str | None = None
    artisan_card_number: str | None = None
    card_holder_name: str | None = None
    craft_category: str | None = None
    district: str | None = None
    issued_date: str | None = None
    file_scan_id: str | None = None
    fetched_at: datetime | None = None


class ArtisanVerificationSubmitResponse(BaseModel):
    application_id: str
    application_number: str
    application_status: str
    seller_profile: SellerProfileBrief


class UserAddressCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address_label: str = Field(default="HOME", min_length=1, max_length=50)
    recipient_name: str = Field(..., min_length=2, max_length=160)
    recipient_phone: str = Field(..., min_length=7, max_length=32)
    line1: str = Field(..., min_length=2, max_length=255)
    line2: str | None = Field(default=None, max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    state_province: str = Field(default="Jammu and Kashmir", min_length=2, max_length=100)
    postal_code: str = Field(..., min_length=4, max_length=20)
    is_default: bool = False


class UserAddressResponse(BaseModel):
    id: str
    address_label: str
    recipient_name: str
    recipient_phone: str
    line1: str
    line2: str | None = None
    city: str
    state_province: str
    postal_code: str
    is_default: bool
    created_at: datetime


class AdminPasswordLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class AdminPasswordLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    email: str
    display_name: str
    admin_permissions: list[str] = Field(default_factory=list)


ConsentScopeLiteral = Literal[
    "essential_account",
    "order_fulfilment",
    "marketing_updates",
    "analytics_telemetry",
    "age_18_plus_confirmation",
]


class ConsentPreferenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent_scope: ConsentScopeLiteral
    granted: bool
    policy_version: str = Field(default="2026-11-v1", min_length=1, max_length=32)
    source_surface: str | None = Field(default=None, max_length=64)


class ConsentBatchUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consents: list[ConsentPreferenceIn] = Field(..., min_length=1, max_length=10)


class ConsentItemResponse(BaseModel):
    consent_scope: str
    policy_version: str
    granted: bool
    source_surface: str | None = None
    granted_at: datetime | None = None
    withdrawn_at: datetime | None = None
    updated_at: datetime | None = None

