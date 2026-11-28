"""Provision, list, or revoke dedicated Email+Password Admin accounts in HunarLink DB.

Security model:
  - Only the 1-2 accounts provisioned with this script can log into `/admin`.
  - No public admin registration endpoint exists.
  - Passwords are stored strictly as salted PBKDF2-HMAC-SHA256 hashes (390,000 rounds)
    inside `admin_credentials` (never plaintext) and work on BOTH MySQL 8.4 and SQLite.

Usage (from backend/ directory):
  Create / update an admin:
    python scripts/create_admin_account.py --email admin@example.com --name "Samyak Admin"
    (prompts securely for password if --password is omitted)

  List authorized admins in DB:
    python scripts/create_admin_account.py --list

  Revoke an admin:
    python scripts/create_admin_account.py --revoke admin@example.com
"""
from __future__ import annotations

import argparse
import getpass
import sys
import uuid
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.admin_security import hash_admin_password
from app.core.config import get_settings
from app.core.database import create_db_engine
from app.models.base import Base, new_uuid, utcnow
from app.models.core_models import (
    AdminCredential,
    AdminPermission,
    AdminProfile,
    AdminRole,
    AdminRolePermission,
    AdminUserRole,
    PlatformRole,
    User,
    UserRoleAssignment,
)

ADMIN_PERMISSIONS = [
    ("payments.read", "payments", False),
    ("payments.refund", "payments", True),
    ("guardrails.read", "guardrails", False),
    ("guardrails.decide", "guardrails", True),
    ("procurement.read", "procurement", False),
]


def _ensure_tables(engine) -> None:
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
    else:
        # On MySQL 8.4, core tables come from hunarlink_mysql_full_install.sql;
        # create `admin_credentials` automatically if Alembic 0003 hasn't run yet.
        AdminCredential.__table__.create(bind=engine, checkfirst=True)


def list_admins(db: Session, dialect: str) -> None:
    rows = db.scalars(select(AdminCredential).order_by(AdminCredential.created_at.asc())).all()
    print(f"=== AUTHORIZED ADMIN ACCOUNTS ({dialect.upper()}) — {len(rows)} total ===")
    if not rows:
        print("  (none configured yet)")
        return
    for r in rows:
        status_str = "ACTIVE" if r.is_active else "REVOKED"
        print(
            f"  • {r.email} [{status_str}]\n"
            f"      user_id={r.user_id}\n"
            f"      password_hash={r.password_hash}\n"
            f"      last_login={r.last_login_at or 'never'}"
        )


def revoke_admin(db: Session, email: str) -> None:
    cleaned = email.strip().lower()
    cred = db.scalar(select(AdminCredential).where(AdminCredential.email == cleaned))
    if cred is None:
        print(f"ERROR: No admin credential found for '{cleaned}'.")
        sys.exit(1)
    cred.is_active = False
    ap = db.scalar(select(AdminProfile).where(AdminProfile.user_id == cred.user_id))
    if ap is not None:
        ap.admin_status = "REVOKED"
    db.commit()
    print(f"REVOKED admin access for {cleaned}.")


def upsert_admin(db: Session, email: str, password: str, display_name: str, dialect: str) -> None:
    cleaned = email.strip().lower()
    if "@" not in cleaned:
        print("ERROR: Please supply a valid email address.")
        sys.exit(1)
    if len(password) < 8:
        print("ERROR: Admin password must be at least 8 characters.")
        sys.exit(1)

    pw_hash = hash_admin_password(password)
    parts = display_name.strip().split()
    first_name = parts[0] if parts else "HunarLink"
    last_name = " ".join(parts[1:]) if len(parts) > 1 else "Admin"

    user = db.scalar(select(User).where(User.email == cleaned))
    if user is None:
        user = User(
            id=new_uuid(),
            clerk_user_id=f"hl_admin_{uuid.uuid4().hex[:16]}",
            email=cleaned,
            email_verified=True,
            first_name=first_name,
            last_name=last_name,
            display_name=display_name.strip() or cleaned,
            preferred_currency="INR",
            account_role="ADMIN",
            account_status="ACTIVE",
        )
        db.add(user)
        db.flush()
    else:
        user.account_role = "ADMIN"
        user.account_status = "ACTIVE"
        if display_name.strip():
            user.display_name = display_name.strip()

    # 1. Platform ADMIN role
    plat_role = db.scalar(select(PlatformRole).where(PlatformRole.code == "ADMIN"))
    if plat_role is None:
        plat_role = PlatformRole(id=new_uuid(), code="ADMIN", name="Platform Admin", is_active=True)
        db.add(plat_role)
        db.flush()

    assign = db.scalar(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user.id,
            UserRoleAssignment.platform_role_id == plat_role.id,
        )
    )
    if assign is None:
        db.add(
            UserRoleAssignment(
                id=new_uuid(),
                user_id=user.id,
                platform_role_id=plat_role.id,
                assignment_status="ACTIVE",
                granted_at=utcnow(),
            )
        )
    else:
        assign.assignment_status = "ACTIVE"

    # 2. Active AdminProfile
    ap = db.scalar(select(AdminProfile).where(AdminProfile.user_id == user.id))
    if ap is None:
        ap = AdminProfile(
            id=new_uuid(),
            user_id=user.id,
            department="Platform Administration",
            admin_status="ACTIVE",
        )
        db.add(ap)
        db.flush()
    else:
        ap.admin_status = "ACTIVE"

    # 3. SUPER_ADMIN AdminRole + permissions
    ar = db.scalar(select(AdminRole).where(AdminRole.code == "SUPER_ADMIN"))
    if ar is None:
        ar = AdminRole(id=new_uuid(), code="SUPER_ADMIN", name="Super Administrator", is_active=True)
        db.add(ar)
        db.flush()

    for code, mod, high_risk in ADMIN_PERMISSIONS:
        perm = db.scalar(select(AdminPermission).where(AdminPermission.code == code))
        if perm is None:
            perm = AdminPermission(
                id=new_uuid(),
                code=code,
                module_name=mod,
                is_high_risk=high_risk,
            )
            db.add(perm)
            db.flush()
        rp = db.scalar(
            select(AdminRolePermission).where(
                AdminRolePermission.admin_role_id == ar.id,
                AdminRolePermission.admin_permission_id == perm.id,
            )
        )
        if rp is None:
            db.add(
                AdminRolePermission(
                    id=new_uuid(),
                    admin_role_id=ar.id,
                    admin_permission_id=perm.id,
                )
            )

    aur = db.scalar(
        select(AdminUserRole).where(
            AdminUserRole.admin_profile_id == ap.id,
            AdminUserRole.admin_role_id == ar.id,
        )
    )
    if aur is None:
        db.add(
            AdminUserRole(
                id=new_uuid(),
                admin_profile_id=ap.id,
                admin_role_id=ar.id,
                is_active=True,
            )
        )
    else:
        aur.is_active = True

    # 4. Dedicated admin_credentials row (salted PBKDF2-HMAC-SHA256 hash)
    cred = db.scalar(select(AdminCredential).where(AdminCredential.user_id == user.id))
    if cred is None:
        cred = AdminCredential(
            id=new_uuid(),
            user_id=user.id,
            email=cleaned,
            password_hash=pw_hash,
            is_active=True,
        )
        db.add(cred)
    else:
        cred.email = cleaned
        cred.password_hash = pw_hash
        cred.is_active = True

    db.commit()
    print(f"SUCCESS ({dialect.upper()}): Authorized admin '{cleaned}' saved to admin_credentials.")
    print(f"  user_id       = {user.id}")
    print(f"  password_hash = {pw_hash}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage HunarLink allowlisted Admin accounts.")
    parser.add_argument("--email", help="Authorized administrator email address")
    parser.add_argument("--password", help="Administrator password (min 8 chars; prompted if omitted)")
    parser.add_argument("--name", default="HunarLink Admin", help="Admin display name")
    parser.add_argument("--list", action="store_true", help="List authorized admin accounts in DB")
    parser.add_argument("--revoke", help="Revoke an admin account by email")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_db_engine(settings)
    _ensure_tables(engine)

    with Session(engine) as db:
        if args.list:
            list_admins(db, engine.dialect.name)
            return
        if args.revoke:
            revoke_admin(db, args.revoke)
            return
        if not args.email:
            parser.print_help()
            sys.exit(1)
        pw = args.password or getpass.getpass(f"Enter strong password for {args.email} (min 8 chars): ")
        upsert_admin(db, args.email, pw, args.name, engine.dialect.name)


if __name__ == "__main__":
    main()
