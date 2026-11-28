"""Shared user-deletion & anonymization service (MySQL/SQLite + Clerk Backend API).

Used by:
  - Self-service account deletion (`POST /api/v1/auth/me/delete`, `DELETE /api/v1/auth/me`)
  - Admin Console user deletion (`DELETE /api/v1/admin/users/{user_id}`)
  - CLI utility (`backend/scripts/delete_user.py`)

Guarantees:
  1. Never breaks foreign-key constraints or MySQL append-only `audit_logs` triggers:
     - Clean accounts with zero blocking references are purged cleanly (`purged=True`).
     - Accounts referenced by orders, seller profiles, guardrails, or immutable `audit_logs`
       are safely anonymized (`DEACTIVATED`, `deleted+<id>@deleted.hunarlink.local`,
       `deleted_<id>`), roles revoked, ephemeral PII/logs wiped, freeing the real email
       for re-registration.
  2. Automatically deletes the linked Clerk user (`DELETE /v1/users/{id}` plus email lookup
     cleanup) whenever `CLERK_SECRET_KEY` is configured — zero manual Clerk Dashboard steps.
"""
from __future__ import annotations

from dataclasses import dataclass
import uuid

from fastapi import HTTPException, Request, status
import httpx
from sqlalchemy import delete, func, inspect as sa_inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.audit import record_audit_log
from app.models.base import utcnow
from app.models.core_models import (
    AdminCredential,
    AdminProfile,
    AuditLog,
    PlatformRole,
    RetailOrder,
    SellerFulfilmentGroup,
    SellerProductListing,
    SellerProfile,
    User,
    UserAddress,
    UserLoginLog,
    UserRoleAssignment,
    WholesaleOrder,
)


@dataclass
class AccountDeletionResult:
    user_id: str
    original_email: str
    original_clerk_id: str
    purged: bool
    anonymized: bool
    clerk_deleted: bool
    clerk_deleted_count: int
    message: str


def get_active_role_codes(db: Session, user_id: str) -> list[str]:
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


def is_admin_user(db: Session, user_id: str, role_codes: list[str] | None = None) -> bool:
    roles = role_codes if role_codes is not None else get_active_role_codes(db, user_id)
    if "ADMIN" in roles:
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
        if sa_inspect(db.connection()).has_table("admin_credentials"):
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


def verify_clerk_password_server_side(
    clerk_user_id: str,
    password: str,
    secret_key: str,
) -> None:
    """Verify current password via Clerk Backend API when CLERK_SECRET_KEY is configured."""
    try:
        resp = httpx.post(
            f"https://api.clerk.com/v1/users/{clerk_user_id}/verify_password",
            headers={"Authorization": f"Bearer {secret_key}"},
            json={"password": password},
            timeout=8.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify password with Clerk authentication service.",
        ) from exc

    if resp.status_code == 200 and resp.json().get("verified") is True:
        return
    if resp.status_code in (400, 401, 422):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect. Account deletion aborted.",
        )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not verify current password with Clerk.",
    )


def delete_clerk_user_server_side(clerk_user_id: str, secret_key: str) -> bool:
    """Delete a single Clerk user by Clerk user_id."""
    if (
        not secret_key
        or not clerk_user_id
        or clerk_user_id.startswith("deleted_")
        or clerk_user_id.startswith("hl_admin_")
    ):
        return False
    try:
        resp = httpx.delete(
            f"https://api.clerk.com/v1/users/{clerk_user_id}",
            headers={"Authorization": f"Bearer {secret_key}"},
            timeout=8.0,
        )
        return resp.status_code in (200, 204, 404)
    except httpx.HTTPError:
        return False


def find_clerk_user_ids_by_email(email: str, secret_key: str) -> list[str]:
    """Query Clerk Backend API for any user records matching `email`."""
    clean_email = (email or "").strip().lower()
    if (
        not secret_key
        or not clean_email
        or "@" not in clean_email
        or clean_email.endswith("@deleted.hunarlink.local")
    ):
        return []
    try:
        resp = httpx.get(
            "https://api.clerk.com/v1/users",
            headers={"Authorization": f"Bearer {secret_key}"},
            params={"email_address": clean_email},
            timeout=8.0,
        )
        if resp.status_code != 200:
            return []
        body = resp.json()
        rows = body.get("data", []) if isinstance(body, dict) else body
        if not isinstance(rows, list):
            return []
        ids: list[str] = []
        for item in rows:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
        return ids
    except httpx.HTTPError:
        return []


def delete_clerk_account(
    clerk_user_id: str | None,
    email: str | None,
    secret_key: str,
    *,
    also_search_email: bool = False,
) -> tuple[bool, int]:
    """Automatically delete the user from Clerk by ID (and email lookup if needed)."""
    if not secret_key:
        return False, 0

    candidate_ids: list[str] = []
    if clerk_user_id and not clerk_user_id.startswith(("deleted_", "hl_admin_")):
        candidate_ids.append(clerk_user_id)
    if not candidate_ids or also_search_email:
        for eid in find_clerk_user_ids_by_email(email or "", secret_key):
            if eid not in candidate_ids:
                candidate_ids.append(eid)

    if not candidate_ids:
        return False, 0

    deleted_count = 0
    all_ok = True
    for cid in candidate_ids:
        ok = delete_clerk_user_server_side(cid, secret_key)
        if ok:
            deleted_count += 1
        else:
            all_ok = False
    return all_ok, deleted_count


def _has_blocking_references_for_purge(
    db: Session,
    user_id: str,
    seller: SellerProfile | None,
    insp,
) -> bool:
    if seller is not None:
        return True
    if (db.scalar(select(func.count(RetailOrder.id)).where(RetailOrder.customer_user_id == user_id)) or 0) > 0:
        return True
    if (db.scalar(select(func.count(WholesaleOrder.id)).where(WholesaleOrder.buyer_user_id == user_id)) or 0) > 0:
        return True
    if (db.scalar(select(func.count(AuditLog.id)).where(AuditLog.actor_user_id == user_id)) or 0) > 0:
        return True

    optional_user_fk_checks = [
        ("payments", "payer_user_id"),
        ("payment_attempts", "payer_user_id"),
        ("refunds", "initiated_by_user_id"),
        ("payouts", "recipient_user_id"),
        ("return_requests", "requested_by_user_id"),
        ("product_reviews", "reviewer_user_id"),
        ("coupon_usage", "user_id"),
        ("support_tickets", "requester_user_id"),
        ("support_ticket_messages", "sender_user_id"),
        ("guardrail_checks", "actor_user_id"),
        ("guardrail_cases", "submitted_by_user_id"),
        ("file_security_scans", "uploader_user_id"),
        ("dealer_profiles", "user_id"),
        ("supplier_profiles", "user_id"),
    ]
    for table_name, col_name in optional_user_fk_checks:
        if insp.has_table(table_name):
            cnt = db.execute(
                text(f"SELECT COUNT(*) FROM `{table_name}` WHERE `{col_name}` = :uid"),
                {"uid": user_id},
            ).scalar()
            if cnt and int(cnt) > 0:
                return True
    return False


def execute_user_deletion(
    db: Session,
    *,
    user: User,
    actor_user_id: str | None,
    actor_role: str,
    reason: str | None = None,
    request: Request | None = None,
    clerk_secret: str = "",
    current_password: str | None = None,
    allow_purge_if_clean: bool = False,
    audit_action: str = "USER_SELF_DELETED",
    self_delete_mode: bool = True,
) -> AccountDeletionResult:
    """Safely delete/anonymize a user in HunarLink DB and automatically delete from Clerk."""
    existing_roles = get_active_role_codes(db, user.id)
    if is_admin_user(db, user.id, existing_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Administrator accounts cannot be self-deleted. Revoke admin access via an authorized administrator."
                if self_delete_mode
                else "Administrator accounts cannot be deleted here. Revoke admin privileges via create_admin_account.py --revoke."
            ),
        )

    # 1. Block deletion if the user still has active / uncompleted orders or fulfilments
    active_orders = list(
        db.scalars(
            select(RetailOrder.order_number).where(
                RetailOrder.customer_user_id == user.id,
                (
                    RetailOrder.fulfilment_status.in_(
                        ["CONFIRMED", "PROCESSING", "PARTIALLY_SHIPPED", "SHIPPED"]
                    )
                    | (
                        (RetailOrder.fulfilment_status == "PENDING_PAYMENT")
                        & RetailOrder.payment_status.in_(["AUTHORIZED", "PAID", "COD_PENDING"])
                    )
                ),
            )
        ).all()
    )
    if active_orders:
        order_list = ", ".join(active_orders[:5])
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account has active order(s) in progress ({order_list}). Complete or cancel them before deletion.",
        )

    active_wholesale = list(
        db.scalars(
            select(WholesaleOrder.order_number).where(
                WholesaleOrder.buyer_user_id == user.id,
                WholesaleOrder.fulfilment_status.in_(
                    ["CONFIRMED", "PROCESSING", "PARTIALLY_SHIPPED", "SHIPPED"]
                ),
            )
        ).all()
    )
    if active_wholesale:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account has active wholesale order(s) in progress. Complete or cancel them before deletion.",
        )

    seller = db.scalar(select(SellerProfile).where(SellerProfile.user_id == user.id))
    if seller is not None:
        active_fulfilments = list(
            db.scalars(
                select(SellerFulfilmentGroup.id).where(
                    SellerFulfilmentGroup.seller_profile_id == seller.id,
                    SellerFulfilmentGroup.fulfilment_status.notin_(["DELIVERED", "CANCELLED"]),
                )
            ).all()
        )
        if active_fulfilments:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Account has active artisan order fulfilments in progress. Complete or cancel them before deletion.",
            )

    insp = sa_inspect(db.connection())
    if insp.has_table("return_requests"):
        open_returns = db.execute(
            text(
                "SELECT return_number FROM return_requests "
                "WHERE requested_by_user_id = :uid "
                "AND return_status NOT IN ('REJECTED', 'CLOSED', 'CANCELLED')"
            ),
            {"uid": user.id},
        ).fetchall()
        if open_returns:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Account has an open return or refund request. Wait until it closes before deletion.",
            )

    original_clerk_id = user.clerk_user_id
    original_email = user.email

    # 2. Optional server-side password verification (self-delete flow)
    if clerk_secret and current_password:
        verify_clerk_password_server_side(original_clerk_id, current_password, clerk_secret)

    # 3. Delete personal/ephemeral data (addresses, login logs, carts, wishlists, notifications)
    db.execute(delete(UserAddress).where(UserAddress.user_id == user.id))
    if insp.has_table("user_login_logs"):
        db.execute(delete(UserLoginLog).where(UserLoginLog.user_id == user.id))
    if insp.has_table("notifications"):
        db.execute(text("DELETE FROM notifications WHERE user_id = :uid"), {"uid": user.id})

    if insp.has_table("carts"):
        if insp.has_table("cart_items"):
            db.execute(
                text(
                    "DELETE FROM cart_items WHERE cart_id IN "
                    "(SELECT id FROM carts WHERE user_id = :uid)"
                ),
                {"uid": user.id},
            )
        db.execute(text("DELETE FROM carts WHERE user_id = :uid"), {"uid": user.id})
    if insp.has_table("wishlists"):
        if insp.has_table("wishlist_items"):
            db.execute(
                text(
                    "DELETE FROM wishlist_items WHERE wishlist_id IN "
                    "(SELECT id FROM wishlists WHERE user_id = :uid)"
                ),
                {"uid": user.id},
            )
        db.execute(text("DELETE FROM wishlists WHERE user_id = :uid"), {"uid": user.id})

    # 4. Try clean physical purge when explicitly allowed AND no FKs/triggers block it
    purged = False
    if allow_purge_if_clean and not _has_blocking_references_for_purge(db, user.id, seller, insp):
        try:
            with db.begin_nested():
                db.execute(delete(UserRoleAssignment).where(UserRoleAssignment.user_id == user.id))
                db.delete(user)
                db.flush()
            purged = True
        except SQLAlchemyError:
            purged = False

    now = utcnow()
    anonymized = False
    target_id = user.id

    if not purged:
        assignments = list(
            db.scalars(
                select(UserRoleAssignment).where(
                    UserRoleAssignment.user_id == user.id,
                    UserRoleAssignment.assignment_status == "ACTIVE",
                )
            ).all()
        )
        for ura in assignments:
            ura.assignment_status = "REVOKED"
            ura.revoked_at = now
            ura.status_reason = (reason or "Account deleted").strip()[:255]

        if seller is not None:
            seller.profile_status = "TERMINATED"
            seller.verification_status = "REVOKED"
            seller.updated_at = now
            for listing in db.scalars(
                select(SellerProductListing).where(SellerProductListing.seller_profile_id == seller.id)
            ).all():
                listing.listing_status = "ARCHIVED"
                listing.updated_at = now

        anonymized_email = f"deleted+{user.id}@deleted.hunarlink.local"
        user.account_role = "DEACTIVATED"
        user.account_status = "DEACTIVATED"
        user.suspended_reason = (reason or ("Self-deleted by user" if self_delete_mode else "Deleted by administrator")).strip()[:500]
        user.email = anonymized_email
        user.clerk_user_id = f"deleted_{user.id}"
        user.email_verified = False
        user.phone = None
        user.phone_verified = False
        user.first_name = "Deleted"
        user.last_name = None
        user.display_name = "Deleted User"
        user.avatar_storage_key = None
        user.last_login_at = None
        user.updated_at = now
        anonymized = True

    record_audit_log(
        db,
        actor_user_id=None if (purged and actor_user_id == target_id) else (actor_user_id or (None if purged else target_id)),
        actor_role=actor_role,
        action=audit_action,
        target_type="users",
        target_id=target_id,
        correlation_id=(
            getattr(request.state, "correlation_id", "") if request is not None else ""
        )
        or str(uuid.uuid4()),
        new_values={
            "account_role": "PURGED" if purged else "DEACTIVATED",
            "account_status": "PURGED" if purged else "DEACTIVATED",
            "purged": purged,
            "anonymized": anonymized,
            "revoked_roles": existing_roles,
        },
        ip_address=request.client.host if (request is not None and request.client) else None,
        user_agent=request.headers.get("user-agent") if request is not None else "cli/delete_user",
    )

    db.commit()

    clerk_deleted, clerk_deleted_count = delete_clerk_account(
        original_clerk_id,
        original_email,
        clerk_secret,
        also_search_email=not self_delete_mode,
    )

    return AccountDeletionResult(
        user_id=target_id,
        original_email=original_email,
        original_clerk_id=original_clerk_id,
        purged=purged,
        anonymized=anonymized,
        clerk_deleted=clerk_deleted,
        clerk_deleted_count=clerk_deleted_count,
        message=(
            "Your HunarLink account has been permanently deleted."
            if self_delete_mode
            else f"User {original_email} removed from HunarLink DB"
            + (" and deleted from Clerk." if clerk_deleted else ".")
        ),
    )
