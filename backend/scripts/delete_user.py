"""Safely delete/anonymize a HunarLink user in DB AND automatically delete them in Clerk.

Usage (from backend/ directory):
    python scripts/delete_user.py --email buyer@example.com
    python scripts/delete_user.py --user-id <uuid>
    python scripts/delete_user.py --clerk-id user_3...

Notes:
  - Reads MySQL/SQLite connection settings and `CLERK_SECRET_KEY` from `backend/.env`.
  - If the user has zero blocking order/audit/seller references, removes the `users` row
    completely; if MySQL append-only `audit_logs` triggers or orders reference them,
    safely anonymizes `users` (`DEACTIVATED`, `deleted+<id>@deleted.hunarlink.local`),
    revokes roles, wipes addresses/login logs/carts, and frees the original email.
  - Automatically deletes the matching account in Clerk via `CLERK_SECRET_KEY` (even if
    the MySQL row was already deleted manually earlier).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_db_engine
from app.models.core_models import User
from app.modules.auth.deletion import delete_clerk_account, execute_user_deletion


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete/anonymize a HunarLink user in DB and delete them from Clerk automatically."
    )
    parser.add_argument("--email", help="Email address of the user to delete.")
    parser.add_argument("--user-id", help="HunarLink DB UUID (users.id).")
    parser.add_argument("--clerk-id", help="Clerk user ID (users.clerk_user_id / user_...).")
    parser.add_argument("--reason", default="Deleted via backend/scripts/delete_user.py")
    parser.add_argument(
        "--database-url",
        default="",
        help="Optional SQLAlchemy database URL override (uses backend/.env by default).",
    )
    args = parser.parse_args()

    if not any([args.email, args.user_id, args.clerk_id]):
        parser.error("Provide at least one of --email, --user-id, or --clerk-id.")

    env_path = BACKEND_ROOT / ".env"
    settings = Settings(_env_file=str(env_path) if env_path.exists() else None)
    if args.database_url:
        settings.database_url = args.database_url.strip()

    engine = create_db_engine(settings)
    clerk_secret = settings.clerk_secret_key.get_secret_value().strip()
    clean_email = args.email.strip().lower() if args.email else None

    with Session(engine) as db:
        user: User | None = None
        if args.user_id:
            user = db.scalar(select(User).where(User.id == args.user_id.strip()))
        elif clean_email:
            user = db.scalar(select(User).where(User.email == clean_email))
        elif args.clerk_id:
            user = db.scalar(select(User).where(User.clerk_user_id == args.clerk_id.strip()))

        if user is None:
            print("DB: No matching active/existing row found in `users` table.")
            if not clerk_secret:
                print(
                    "CLERK: CLERK_SECRET_KEY is not set in backend/.env; cannot check/delete in Clerk."
                )
                sys.exit(0)
            ok, count = delete_clerk_account(
                args.clerk_id.strip() if args.clerk_id else None,
                clean_email,
                clerk_secret,
                also_search_email=True,
            )
            if count > 0:
                print(f"CLERK: Deleted {count} orphaned Clerk user record(s) automatically.")
            elif ok:
                print("CLERK: No matching Clerk user found (already clean).")
            else:
                print("CLERK: No matching Clerk user deleted.")
            return

        print(
            f"Found user in DB: id={user.id} | email={user.email} | clerk_id={user.clerk_user_id}"
        )
        try:
            res = execute_user_deletion(
                db,
                user=user,
                actor_user_id=None,
                actor_role="ADMIN",
                reason=args.reason,
                request=None,
                clerk_secret=clerk_secret,
                current_password=None,
                allow_purge_if_clean=True,
                audit_action="CLI_USER_DELETED",
                self_delete_mode=False,
            )
        except HTTPException as exc:
            print(f"BLOCKED ({exc.status_code}): {exc.detail}", file=sys.stderr)
            sys.exit(1)

        db_mode = (
            "PURGED (row deleted from `users`)"
            if res.purged
            else "ANONYMIZED (`DEACTIVATED`, email & Clerk ID freed without breaking audit/order FKs)"
        )
        print(f"DB:    {db_mode}")
        if not clerk_secret:
            print("CLERK: Skipped — CLERK_SECRET_KEY is not set in backend/.env.")
        elif res.clerk_deleted:
            print(f"CLERK: Automatically deleted ({res.clerk_deleted_count} record(s) removed).")
        else:
            print("CLERK: Warning — Clerk deletion returned false (check CLERK_SECRET_KEY or network).")


if __name__ == "__main__":
    main()
