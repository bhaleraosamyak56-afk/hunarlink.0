"""SQLAlchemy 2.x models aligned with the HunarLink MySQL 8.4 LTS baseline tables.

Every table name and column matches `hunarlink-database/sql/01`–`08` verbatim.
All monetary columns use `Numeric(14, 2)` -> Python `decimal.Decimal` (never float).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, UUIDChar, new_uuid, utcnow


# ---------------------------------------------------------------------------
# Module A: Identity & Admin Access
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    clerk_user_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    preferred_currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    account_role: Mapped[str] = mapped_column(String(32), default="BUYER", nullable=False)
    account_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False)


class PlatformRole(Base):
    __tablename__ = "platform_roles"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserRoleAssignment(Base):
    __tablename__ = "user_role_assignments"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    platform_role_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("platform_roles.id"), nullable=False)
    assignment_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    granted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class UserLoginLog(Base):
    """Per-role registration & sign-in audit trail (`REGISTER` vs `LOGIN`)."""

    __tablename__ = "user_login_logs"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    role_code: Mapped[str] = mapped_column(String(50), nullable=False)
    auth_event_type: Mapped[str] = mapped_column(String(24), nullable=False)  # REGISTER | LOGIN
    auth_method: Mapped[str] = mapped_column(String(32), nullable=False)  # clerk_signup | clerk_signin | clerk_sync | admin_password
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class UserAddress(Base):
    __tablename__ = "user_addresses"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    address_label: Mapped[str] = mapped_column(String(50), default="HOME", nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(160), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    landmark: Mapped[str | None] = mapped_column(String(160), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_province: Mapped[str] = mapped_column(String(100), default="Jammu and Kashmir", nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), default="IN", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False)


class AdminProfile(Base):
    __tablename__ = "admin_profiles"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), unique=True, nullable=False)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    admin_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class AdminRole(Base):
    __tablename__ = "admin_roles"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AdminPermission(Base):
    __tablename__ = "admin_permissions"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    module_name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_high_risk: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AdminUserRole(Base):
    __tablename__ = "admin_user_roles"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    admin_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("admin_profiles.id"), nullable=False)
    admin_role_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("admin_roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AdminRolePermission(Base):
    __tablename__ = "admin_role_permissions"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    admin_role_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("admin_roles.id"), nullable=False)
    admin_permission_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("admin_permissions.id"), nullable=False)


class AdminCredential(Base):
    """Dedicated password credentials strictly for 1-2 DB-provisioned Admins."""

    __tablename__ = "admin_credentials"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False)


# ---------------------------------------------------------------------------
# Module B & C: Sellers, GI Verification & Product Catalogue
# ---------------------------------------------------------------------------
class SellerProfile(Base):
    __tablename__ = "seller_profiles"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), unique=True, nullable=False)
    store_name: Mapped[str] = mapped_column(String(160), nullable=False)
    store_slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    craft_specialty: Mapped[str | None] = mapped_column(String(160), nullable=True)
    workshop_district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verification_path: Mapped[str] = mapped_column(String(16), default="NON_GI", nullable=False)
    profile_status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="UNVERIFIED", nullable=False)
    claimed_gi_authorized_user_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    average_rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.00"), nullable=False)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class SellerDocument(Base):
    __tablename__ = "seller_documents"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    seller_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("seller_profiles.id"), nullable=False)
    application_id: Mapped[str | None] = mapped_column(
        UUIDChar(), ForeignKey("seller_verification_applications.id"), nullable=True
    )
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    detected_mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scan_status: Mapped[str] = mapped_column(String(32), default="CLEAN", nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="ACCEPTED", nullable=False)
    uploaded_by_user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class SellerVerificationApplication(Base):
    __tablename__ = "seller_verification_applications"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    seller_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("seller_profiles.id"), nullable=False)
    application_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    verification_path: Mapped[str] = mapped_column(String(16), nullable=False)
    application_status: Mapped[str] = mapped_column(String(32), default="SUBMITTED", nullable=False)
    claimed_gi_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    claimed_craft_cluster: Mapped[str | None] = mapped_column(String(160), nullable=True)
    submitted_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=True)
    review_decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class GIReferenceRecord(Base):
    __tablename__ = "gi_reference_records"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    gi_registration_number: Mapped[str] = mapped_column(String(100), nullable=False)
    gi_name: Mapped[str] = mapped_column(String(255), nullable=False)
    authorized_geographic_area: Mapped[str] = mapped_column(String(255), nullable=False)
    state_region: Mapped[str] = mapped_column(String(120), nullable=False)
    source_authority: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False)
    is_gi_eligible_category: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    category_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("categories.id"), nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=True)
    sku_root: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    slug: Mapped[str] = mapped_column(String(240), unique=True, nullable=False)
    short_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    craft_technique: Mapped[str | None] = mapped_column(String(120), nullable=True)
    origin_district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    material_composition: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gi_status: Mapped[str] = mapped_column(String(32), default="UNVERIFIED", nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)
    attributes_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    product_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("products.id"), nullable=False)
    product_variant_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("product_variants.id"), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    product_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("products.id"), nullable=False)
    variant_sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    variant_name: Mapped[str] = mapped_column(String(160), nullable=False)
    base_mrp: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProductGIClaim(Base):
    __tablename__ = "product_gi_claims"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    product_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("products.id"), nullable=False)
    seller_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("seller_profiles.id"), nullable=False)
    gi_reference_record_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("gi_reference_records.id"), nullable=True)
    claimed_gi_code: Mapped[str] = mapped_column(String(120), nullable=False)
    claimed_origin_location: Mapped[str] = mapped_column(String(200), nullable=False)
    claim_statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_status: Mapped[str] = mapped_column(String(32), default="SUBMITTED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class GIVerificationRun(Base):
    __tablename__ = "gi_verification_runs"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    seller_application_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("seller_verification_applications.id"), nullable=True)
    product_gi_claim_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("product_gi_claims.id"), nullable=True)
    gi_reference_record_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("gi_reference_records.id"), nullable=True)
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_reference_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    assessment_outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    structured_findings_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_legal_proof: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_mock_provider: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    human_review_decision: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class SellerProductListing(Base):
    __tablename__ = "seller_product_listings"
    __table_args__ = (UniqueConstraint("seller_profile_id", "seller_sku", name="uq_spl_seller_sku"),)

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    seller_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("seller_profiles.id"), nullable=False)
    product_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("products.id"), nullable=False)
    product_variant_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("product_variants.id"), nullable=False)
    seller_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    listing_title: Mapped[str] = mapped_column(String(220), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    compare_at_mrp: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    min_order_qty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_order_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listing_status: Mapped[str] = mapped_column(String(32), default="PENDING_APPROVAL", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


# ---------------------------------------------------------------------------
# Module D & E: Suppliers, Dealers, Procurement, Inventory & Retail Orders
# ---------------------------------------------------------------------------
class SupplierProfile(Base):
    __tablename__ = "supplier_profiles"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), unique=True, nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(180), nullable=False)
    profile_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="APPROVED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class SupplierLot(Base):
    __tablename__ = "supplier_lots"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    lot_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    supplier_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("supplier_profiles.id"), nullable=False)
    category_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("categories.id"), nullable=False)
    product_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("products.id"), nullable=True)
    product_variant_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("product_variants.id"), nullable=True)
    lot_title: Mapped[str] = mapped_column(String(220), nullable=False)
    lot_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    offered_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(32), default="PCS", nullable=False)
    expected_unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    is_gi_claimed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    available_from_date: Mapped[date] = mapped_column(Date, nullable=False)
    available_until_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lot_status: Mapped[str] = mapped_column(String(32), default="SUBMITTED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class DealerProfile(Base):
    __tablename__ = "dealer_profiles"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), unique=True, nullable=False)
    dealership_name: Mapped[str] = mapped_column(String(180), nullable=False)
    dealership_slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state_province: Mapped[str] = mapped_column(String(100), nullable=False)
    profile_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="APPROVED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    warehouse_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    owner_type: Mapped[str] = mapped_column(String(16), nullable=False)
    seller_profile_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("seller_profiles.id"), nullable=True)
    dealer_profile_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("dealer_profiles.id"), nullable=True)
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state_province: Mapped[str] = mapped_column(String(100), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DealerAssignment(Base):
    __tablename__ = "dealer_assignments"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    supplier_lot_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("supplier_lots.id"), nullable=False)
    dealer_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("dealer_profiles.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    assigned_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    proposed_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    assignment_status: Mapped[str] = mapped_column(String(32), default="INVITED", nullable=False)
    assigned_by_user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class SupplierPurchaseOrder(Base):
    __tablename__ = "supplier_purchase_orders"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    po_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    supplier_lot_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("supplier_lots.id"), nullable=False)
    dealer_assignment_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("dealer_assignments.id"), unique=True, nullable=False)
    supplier_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("supplier_profiles.id"), nullable=False)
    dealer_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("dealer_profiles.id"), nullable=False)
    destination_warehouse_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("warehouses.id"), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    settlement_status: Mapped[str] = mapped_column(String(32), default="UNPAID", nullable=False)
    po_status: Mapped[str] = mapped_column(String(32), default="ISSUED", nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class SupplierPurchaseOrderItem(Base):
    __tablename__ = "supplier_purchase_order_items"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    supplier_purchase_order_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("supplier_purchase_orders.id"), nullable=False)
    product_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("products.id"), nullable=False)
    product_variant_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("product_variants.id"), nullable=False)
    item_title_snapshot: Mapped[str] = mapped_column(String(220), nullable=False)
    sku_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    ordered_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    receipt_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    supplier_purchase_order_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("supplier_purchase_orders.id"), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("warehouses.id"), nullable=False)
    dealer_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("dealer_profiles.id"), nullable=False)
    received_by_user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    receipt_status: Mapped[str] = mapped_column(String(32), default="RECEIVED_PENDING_INSPECTION", nullable=False)


class GoodsReceiptItem(Base):
    __tablename__ = "goods_receipt_items"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    goods_receipt_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("goods_receipts.id"), nullable=False)
    supplier_po_item_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("supplier_purchase_order_items.id"), nullable=False)
    product_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("products.id"), nullable=False)
    product_variant_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("product_variants.id"), nullable=False)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    accepted_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0.000"), nullable=False)
    rejected_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0.000"), nullable=False)
    damaged_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0.000"), nullable=False)
    inventory_posted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class QualityInspection(Base):
    __tablename__ = "quality_inspections"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    goods_receipt_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("goods_receipts.id"), nullable=False)
    goods_receipt_item_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("goods_receipt_items.id"), nullable=True)
    inspector_user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    inspection_outcome: Mapped[str] = mapped_column(String(32), nullable=False)


class WarehouseStock(Base):
    __tablename__ = "warehouse_stock"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    warehouse_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("warehouses.id"), nullable=False)
    product_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("products.id"), nullable=False)
    product_variant_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("product_variants.id"), nullable=False)
    owner_type: Mapped[str] = mapped_column(String(16), nullable=False)
    seller_profile_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("seller_profiles.id"), nullable=True)
    dealer_profile_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("dealer_profiles.id"), nullable=True)
    seller_listing_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("seller_product_listings.id"), nullable=True)
    available_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0.000"), nullable=False)
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0.000"), nullable=False)
    damaged_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0.000"), nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    warehouse_stock_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("warehouse_stock.id"), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("warehouses.id"), nullable=False)
    product_variant_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("product_variants.id"), nullable=False)
    goods_receipt_item_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("goods_receipt_items.id"), nullable=True)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    available_after: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reserved_after: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    damaged_after: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(UUIDChar(), nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class RetailOrder(Base):
    __tablename__ = "retail_orders"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    order_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    customer_user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    shipping_address_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    shipping_fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(32), default="RAZORPAY_STANDARD", nullable=False)
    payment_status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    fulfilment_status: Mapped[str] = mapped_column(String(32), default="PENDING_PAYMENT", nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class SellerFulfilmentGroup(Base):
    __tablename__ = "seller_fulfilment_groups"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    fulfilment_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    retail_order_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("retail_orders.id"), nullable=False)
    seller_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("seller_profiles.id"), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    group_total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fulfilment_status: Mapped[str] = mapped_column(String(32), default="PENDING_PAYMENT", nullable=False)


class RetailOrderItem(Base):
    __tablename__ = "retail_order_items"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    retail_order_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("retail_orders.id"), nullable=False)
    seller_fulfilment_group_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("seller_fulfilment_groups.id"), nullable=False)
    seller_listing_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("seller_product_listings.id"), nullable=False)
    product_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("products.id"), nullable=False)
    product_variant_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("product_variants.id"), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(220), nullable=False)
    sku_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    gi_status_snapshot: Mapped[str] = mapped_column(String(40), default="UNVERIFIED", nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount_snapshot: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    tax_amount_snapshot: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    line_total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)


# ---------------------------------------------------------------------------
# Module F: Wholesale Marketplace
# ---------------------------------------------------------------------------
class DealerWholesaleListing(Base):
    __tablename__ = "dealer_wholesale_listings"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    dealer_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("dealer_profiles.id"), nullable=False)
    product_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("products.id"), nullable=False)
    product_variant_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("product_variants.id"), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("warehouses.id"), nullable=False)
    warehouse_stock_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("warehouse_stock.id"), nullable=True)
    dealer_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    listing_title: Mapped[str] = mapped_column(String(220), nullable=False)
    base_unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    minimum_order_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    lead_time_days: Mapped[int] = mapped_column(SmallInteger, default=14, nullable=False)
    listing_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)


class WholesaleBuyerProfile(Base):
    __tablename__ = "wholesale_buyer_profiles"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    business_city: Mapped[str] = mapped_column(String(100), nullable=False)
    business_state: Mapped[str] = mapped_column(String(100), nullable=False)
    profile_status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="APPROVED", nullable=False)


class WholesalePriceTier(Base):
    __tablename__ = "wholesale_price_tiers"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    dealer_wholesale_listing_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("dealer_wholesale_listings.id"), nullable=False)
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    max_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class WholesaleRFQ(Base):
    __tablename__ = "wholesale_rfqs"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    rfq_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    wholesale_buyer_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("wholesale_buyer_profiles.id"), nullable=False)
    buyer_user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    rfq_status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False)


class DealerQuote(Base):
    __tablename__ = "dealer_quotes"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    quote_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    wholesale_rfq_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("wholesale_rfqs.id"), nullable=False)
    dealer_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("dealer_profiles.id"), nullable=False)
    submitted_by_user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    quote_status: Mapped[str] = mapped_column(String(32), default="SUBMITTED", nullable=False)


class DealerQuoteItem(Base):
    __tablename__ = "dealer_quote_items"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    dealer_quote_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("dealer_quotes.id"), nullable=False)
    dealer_wholesale_listing_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("dealer_wholesale_listings.id"), nullable=True)
    product_variant_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("product_variants.id"), nullable=False)
    item_title_snapshot: Mapped[str] = mapped_column(String(220), nullable=False)
    quoted_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)


class WholesaleOrder(Base):
    __tablename__ = "wholesale_orders"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    order_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    wholesale_buyer_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("wholesale_buyer_profiles.id"), nullable=False)
    buyer_user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    dealer_profile_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("dealer_profiles.id"), nullable=False)
    order_source: Mapped[str] = mapped_column(String(32), nullable=False)
    wholesale_rfq_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("wholesale_rfqs.id"), nullable=True)
    dealer_quote_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("dealer_quotes.id"), unique=True, nullable=True)
    shipping_address_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    shipping_fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(32), default="RAZORPAY_STANDARD", nullable=False)
    payment_status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    fulfilment_status: Mapped[str] = mapped_column(String(32), default="PENDING_PAYMENT", nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class WholesaleOrderItem(Base):
    __tablename__ = "wholesale_order_items"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    wholesale_order_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("wholesale_orders.id"), nullable=False)
    dealer_wholesale_listing_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("dealer_wholesale_listings.id"), nullable=True)
    product_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("products.id"), nullable=False)
    product_variant_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("product_variants.id"), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(220), nullable=False)
    sku_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount_snapshot: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    tax_amount_snapshot: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    line_total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)


class StockReservation(Base):
    __tablename__ = "stock_reservations"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    warehouse_stock_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("warehouse_stock.id"), nullable=False)
    reservation_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    retail_order_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("retail_orders.id"), nullable=True)
    wholesale_order_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("wholesale_orders.id"), nullable=True)
    reserved_by_user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reservation_status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


# ---------------------------------------------------------------------------
# Module G & H: Payments, Webhooks, Refunds & Immutable Audit Logs
# ---------------------------------------------------------------------------
class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    payment_reference: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    payment_purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    retail_order_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("retail_orders.id"), nullable=True)
    wholesale_order_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("wholesale_orders.id"), nullable=True)
    supplier_purchase_order_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("supplier_purchase_orders.id"), nullable=True)
    payer_user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(32), default="RAZORPAY_STANDARD", nullable=False)
    provider_name: Mapped[str] = mapped_column(String(40), default="RAZORPAY", nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    captured_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    payment_status: Mapped[str] = mapped_column(String(32), default="CREATED", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    provider_receipt: Mapped[str | None] = mapped_column(String(80), nullable=True)
    authorized_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False)


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    payment_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("payments.id"), nullable=False)
    payer_user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    attempt_status: Mapped[str] = mapped_column(String(32), default="INITIATED", nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    safe_metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False)


class PaymentStatusHistory(Base):
    __tablename__ = "payment_status_history"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    payment_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("payments.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str] = mapped_column(String(40), nullable=False)
    event_source: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=True)
    provider_event_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class PaymentWebhookEvent(Base):
    __tablename__ = "payment_webhook_events"
    __table_args__ = (
        UniqueConstraint("provider_name", "provider_event_id", name="uq_pwe_provider_event_id"),
    )

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    provider_name: Mapped[str] = mapped_column(String(40), default="RAZORPAY", nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("payments.id"), nullable=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    signature_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), default="RECEIVED", nullable=False)
    safe_payload_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    refund_reference: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    payment_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("payments.id"), nullable=False)
    provider_refund_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    refund_type: Mapped[str] = mapped_column(String(16), nullable=False)
    refund_status: Mapped[str] = mapped_column(String(32), default="REQUESTED", nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    initiated_by_user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    actor_user_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    previous_values_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_values_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class ProductReview(Base):
    """Customer/collector product reviews matching `sql/07_payments_shipping_returns_reviews.sql`."""

    __tablename__ = "product_reviews"

    id: Mapped[str] = mapped_column(UUIDChar(), primary_key=True, default=new_uuid)
    product_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("products.id"), nullable=False)
    product_variant_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("product_variants.id"), nullable=True)
    seller_profile_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("seller_profiles.id"), nullable=True)
    reviewer_user_id: Mapped[str] = mapped_column(UUIDChar(), ForeignKey("users.id"), nullable=False)
    retail_order_item_id: Mapped[str | None] = mapped_column(UUIDChar(), ForeignKey("retail_order_items.id"), nullable=True)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    review_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_verified_purchase: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    moderation_status: Mapped[str] = mapped_column(String(32), default="PUBLISHED", nullable=False)
    seller_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    seller_replied_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False)
