"""Promote an existing Clerk-synced user in HunarLink DB to active SUPER_ADMIN.

Works on BOTH MySQL 8.4 LTS and SQLite.

Usage (from backend/ directory):
    python scripts/promote_admin.py your.email@example.com
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import create_db_engine
from app.models.base import Base, new_uuid, utcnow
from app.models.core_models import (
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


def promote_admin(email: str) -> None:
    cleaned = email.strip().lower()
    settings = get_settings()
    engine = create_db_engine(settings)
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == cleaned))
        if user is None:
            print(f"ERROR: No user found with email '{cleaned}'. Sign in once via Clerk first.")
            sys.exit(1)

        user.account_role = "ADMIN"

        # 1. Ensure ADMIN platform role assignment
        plat_role = db.scalar(select(PlatformRole).where(PlatformRole.code == "ADMIN"))
        if plat_role is None:
            plat_role = PlatformRole(id=new_uuid(), code="ADMIN", name="Platform Admin", is_active=True)
            db.add(plat_role)
            db.flush()

        existing_assign = db.scalar(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == user.id,
                UserRoleAssignment.platform_role_id == plat_role.id,
            )
        )
        if existing_assign is None:
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
            existing_assign.assignment_status = "ACTIVE"

        # 2. Ensure ACTIVE admin_profiles row
        admin_profile = db.scalar(select(AdminProfile).where(AdminProfile.user_id == user.id))
        if admin_profile is None:
            admin_profile = AdminProfile(
                id=new_uuid(),
                user_id=user.id,
                department="Platform Governance",
                admin_status="ACTIVE",
            )
            db.add(admin_profile)
            db.flush()
        else:
            admin_profile.admin_status = "ACTIVE"

        # 3. Ensure SUPER_ADMIN admin_role + permissions
        admin_role = db.scalar(select(AdminRole).where(AdminRole.code == "SUPER_ADMIN"))
        if admin_role is None:
            admin_role = AdminRole(
                id=new_uuid(),
                code="SUPER_ADMIN",
                name="Super Administrator",
                is_active=True,
            )
            db.add(admin_role)
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
                    AdminRolePermission.admin_role_id == admin_role.id,
                    AdminRolePermission.admin_permission_id == perm.id,
                )
            )
            if rp is None:
                db.add(
                    AdminRolePermission(
                        id=new_uuid(),
                        admin_role_id=admin_role.id,
                        admin_permission_id=perm.id,
                    )
                )

        # 4. Bind admin_profile -> SUPER_ADMIN
        aur = db.scalar(
            select(AdminUserRole).where(
                AdminUserRole.admin_profile_id == admin_profile.id,
                AdminUserRole.admin_role_id == admin_role.id,
            )
        )
        if aur is None:
            db.add(
                AdminUserRole(
                    id=new_uuid(),
                    admin_profile_id=admin_profile.id,
                    admin_role_id=admin_role.id,
                    is_active=True,
                )
            )
        else:
            aur.is_active = True

        db.commit()
        print(
            f"SUCCESS ({engine.dialect.name.upper()}): Promoted {user.email} "
            f"(user_id={user.id}) to ACTIVE SUPER_ADMIN with full RBAC permissions."
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/promote_admin.py <user-email>")
        sys.exit(1)
    promote_admin(sys.argv[1])
