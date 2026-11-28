"""Idempotent CLI to add `users.last_login_at`, `user_login_logs`, and MySQL role views.

Safe to run against an already-populated local/remote MySQL 8.4 database even when
Alembic was never stamped on the baseline schema.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.database import create_db_engine  # noqa: E402
from app.modules.auth.role_views import ensure_login_tracking_and_views  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync users.last_login_at, user_login_logs, and per-role MySQL views."
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="Optional SQLAlchemy DB URL override (defaults to DATABASE_URL from backend/.env).",
    )
    args = parser.parse_args()

    if args.database_url:
        target_engine = create_engine(args.database_url)
    else:
        env_path = ROOT / ".env"
        cfg = Settings(_env_file=str(env_path)) if env_path.exists() else Settings()
        target_engine = create_db_engine(cfg)

    summary = ensure_login_tracking_and_views(target_engine)
    print(f"Dialect: {summary['dialect']}")
    print(f"users.account_role added: {summary['account_role_column_added']}")
    print(f"users.account_role backfilled rows: {summary['account_roles_backfilled']}")
    print(f"users.last_login_at added: {summary['last_login_column_added']}")
    print(f"user_login_logs created: {summary['login_logs_table_created']}")
    print(f"MySQL views applied ({len(summary['views_applied'])}):")
    for v in summary["views_applied"]:
        print(f"  - {v}")


if __name__ == "__main__":
    main()
