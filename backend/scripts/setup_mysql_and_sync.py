#!/usr/bin/env python3
"""Turnkey MySQL 8.4 LTS Setup + SQLite -> MySQL Data Migrator for HunarLink.

Updates your MySQL 8.4 database (visible in MySQL Workbench) with:
  1. All 96 canonical tables + views + triggers + procedures from
     `hunarlink-database/hunarlink_mysql_full_install.sql`
  2. All 6 ASIGS Guardrail tables + `admin_credentials` (Alembic 0002 & 0003)
  3. Idempotent migration of existing rows from local SQLite (`./hunarlink_dev.db`)
     so your synced Clerk users, addresses, admin credentials, orders & artisans
     transfer cleanly into MySQL 8.4 with ZERO duplicates!
  4. Real Kashmiri artisans & GI-verified craft listings (`seed_real_artisans.py`)

Usage (Windows PowerShell / Linux):
  python scripts/setup_mysql_and_sync.py
  python scripts/setup_mysql_and_sync.py --mysql-url "mysql+pymysql://root:PASS@127.0.0.1:3306/hunarlink"
  python scripts/setup_mysql_and_sync.py --from-sqlite ./hunarlink_dev.db
  python scripts/setup_mysql_and_sync.py --verify-only
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from urllib.parse import urlparse, unquote

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pymysql
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.base import Base
import app.models.core_models as core_models  # noqa: F401
import app.models.guardrail_models as guardrail_models  # noqa: F401
import app.models.craftproof_models as craftproof_models  # noqa: F401


def split_mysql_statements(sql_text: str) -> list[str]:
    """Split a MySQL script respecting `DELIMITER $$` blocks for triggers & procedures."""
    statements: list[str] = []
    delimiter = ";"
    buf: list[str] = []

    for raw_line in sql_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("--"):
            continue

        m_delim = re.match(r"^DELIMITER\s+(\S+)\s*$", stripped, re.IGNORECASE)
        if m_delim:
            if buf:
                joined = "\n".join(buf).strip()
                if joined:
                    statements.append(joined)
                buf = []
            delimiter = m_delim.group(1)
            continue

        buf.append(raw_line)
        joined = "\n".join(buf)
        if joined.rstrip().endswith(delimiter):
            stmt = joined.rstrip()[: -len(delimiter)].strip()
            if stmt:
                statements.append(stmt)
            buf = []

    if buf:
        leftover = "\n".join(buf).strip()
        if leftover:
            statements.append(leftover)
    return statements


def install_mysql_schema(mysql_url: str) -> None:
    """Create DB if absent, apply the 96-table MySQL 8.4 installer + ASIGS tables."""
    parsed = make_url(mysql_url)
    if not parsed.drivername.startswith("mysql"):
        raise SystemExit(
            f"ERROR: Target URL must be MySQL (got '{parsed.drivername}'). "
            "Set DATABASE_URL=mysql+pymysql://... in backend/.env or pass --mysql-url."
        )

    db_name = parsed.database or "hunarlink"
    host = parsed.host or "127.0.0.1"
    port = parsed.port or 3306
    user = parsed.username or "root"
    password = parsed.password or ""

    print(f"[1/4] Connecting to MySQL 8.4 at {user}@{host}:{port} (database `{db_name}`)...")
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION()")
            version = cur.fetchone()[0]
            print(f"      Connected! MySQL server version: {version}")
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
            cur.execute(f"USE `{db_name}`")

            full_sql_path = REPO_ROOT / "hunarlink-database" / "hunarlink_mysql_full_install.sql"
            if full_sql_path.exists():
                print(f"[2/4] Applying 96-table installer: {full_sql_path.name} ...")
                sql_text = full_sql_path.read_text(encoding="utf-8")
                stmts = split_mysql_statements(sql_text)
                applied = 0
                skipped_existing = 0
                for stmt in stmts:
                    upper = stmt.lstrip().upper()
                    if upper.startswith("CREATE DATABASE") or upper.startswith("USE "):
                        continue
                    try:
                        cur.execute(stmt)
                        applied += 1
                    except pymysql.MySQLError as exc:
                        # 1359 = Trigger already exists, 1304 = Procedure already exists,
                        # 1050 = Table already exists, 1061 = Duplicate key/index name
                        if exc.args and exc.args[0] in (1050, 1061, 1304, 1359):
                            skipped_existing += 1
                        else:
                            raise
                print(f"      Installer complete: {applied} statements applied, {skipped_existing} already existed.")
            else:
                print("      NOTE: hunarlink_mysql_full_install.sql not found; creating ORM tables directly.")
    finally:
        conn.close()

    # Ensure ASIGS guardrail tables + admin_credentials + account_role + views exist cleanly
    engine = create_engine(mysql_url, pool_pre_ping=True, future=True)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    from app.modules.auth.role_views import ensure_login_tracking_and_views

    ensure_login_tracking_and_views(engine)
    with engine.begin() as c:
        c.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version ("
                "version_num VARCHAR(64) NOT NULL PRIMARY KEY"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
        )
        c.execute(text("DELETE FROM alembic_version"))
        c.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:ver)"),
            {"ver": "0006_add_users_account_role"},
        )
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"      MySQL schema verified: {len(tables)} total tables ready in `{db_name}`.")
    engine.dispose()


def _copy_model_rows(
    src_db: Session,
    dst_db: Session,
    model_cls,
    unique_cols: tuple[str, ...] = ("id",),
) -> int:
    """Copy rows of a SQLAlchemy model from SQLite -> MySQL idempotently."""
    rows = src_db.scalars(select(model_cls)).all()
    inserted = 0
    col_names = [c.name for c in model_cls.__table__.columns]

    for row in rows:
        # Check by primary key `id` first
        existing = dst_db.get(model_cls, getattr(row, "id"))
        if existing is not None:
            continue

        # Also check secondary unique keys (like email / code / slug) to prevent UNIQUE collisions
        duplicate = False
        for ucol in unique_cols:
            if ucol == "id":
                continue
            val = getattr(row, ucol, None)
            if val is not None:
                found = dst_db.scalar(
                    select(model_cls).where(getattr(model_cls, ucol) == val)
                )
                if found is not None:
                    duplicate = True
                    break
        if duplicate:
            continue

        data = {name: getattr(row, name) for name in col_names}
        dst_db.add(model_cls(**data))
        dst_db.flush()
        inserted += 1

    return inserted


def migrate_sqlite_to_mysql(sqlite_path: pathlib.Path, mysql_url: str) -> None:
    """Copy existing local SQLite rows into MySQL 8.4 in strict FK order."""
    if not sqlite_path.exists():
        print(f"[3/4] SQLite file '{sqlite_path}' not found — skipping SQLite data import.")
        return

    print(f"[3/4] Migrating existing rows from SQLite ({sqlite_path}) -> MySQL 8.4 ...")
    sqlite_url = f"sqlite:///{sqlite_path.resolve().as_posix()}"
    src_engine = create_engine(sqlite_url, future=True)
    dst_engine = create_engine(mysql_url, pool_pre_ping=True, future=True)

    src_tables = set(inspect(src_engine).get_table_names())

    migration_order = [
        (core_models.PlatformRole, ("id", "code")),
        (core_models.AdminRole, ("id", "code")),
        (core_models.AdminPermission, ("id", "code")),
        (core_models.AdminRolePermission, ("id",)),
        (core_models.User, ("id", "email", "clerk_user_id")),
        (core_models.UserRoleAssignment, ("id",)),
        (core_models.UserAddress, ("id",)),
        (core_models.AdminProfile, ("id", "user_id")),
        (core_models.AdminUserRole, ("id",)),
        (core_models.AdminCredential, ("id", "user_id", "email")),
        (core_models.SellerProfile, ("id", "store_slug")),
        (core_models.SellerVerificationApplication, ("id", "application_number")),
        (core_models.SellerDocument, ("id", "storage_key")),
        (core_models.Category, ("id", "code", "slug")),
        (core_models.Product, ("id", "sku_root", "slug")),
        (core_models.ProductVariant, ("id", "variant_sku")),
        (core_models.ProductImage, ("id",)),
        (core_models.SellerProductListing, ("id",)),
        (core_models.RetailOrder, ("id", "order_number")),
        (core_models.RetailOrderItem, ("id",)),
        (core_models.Payment, ("id", "payment_reference")),
        (core_models.Refund, ("id", "refund_reference")),
        (guardrail_models.GuardrailRule, ("id", "rule_code")),
        (guardrail_models.GuardrailCheck, ("id",)),
        (guardrail_models.GuardrailCase, ("id", "case_number")),
        (guardrail_models.GuardrailCaseEvent, ("id",)),
        (guardrail_models.FileSecurityScan, ("id", "storage_key")),
        (guardrail_models.InputFingerprint, ("id",)),
    ]

    total_copied = 0
    with Session(src_engine) as src_db, Session(dst_engine) as dst_db:
        for model_cls, unique_cols in migration_order:
            tname = model_cls.__tablename__
            if tname not in src_tables:
                continue
            try:
                count = _copy_model_rows(src_db, dst_db, model_cls, unique_cols=unique_cols)
                if count > 0:
                    print(f"      + {tname}: copied {count} row(s)")
                    total_copied += count
            except Exception as exc:
                dst_db.rollback()
                print(f"      ! {tname}: skipped ({type(exc).__name__}: {exc})")
                continue
        dst_db.commit()

    print(f"      SQLite -> MySQL migration complete ({total_copied} new rows imported).")
    src_engine.dispose()
    dst_engine.dispose()


def seed_real_artisans_and_rules(mysql_url: str) -> None:
    """Seed the 4 real Kashmiri artisans, 5 GI crafts, and default ASIGS rules."""
    print("[4/4] Seeding verified Kashmiri artisans, craft listings & ASIGS guardrail rules ...")
    import os
    os.environ["DATABASE_URL"] = mysql_url
    from scripts.seed_real_artisans import seed as seed_artisans
    from app.modules.guardrails.repository import ensure_default_guardrail_rules

    seed_artisans()

    engine = create_engine(mysql_url, pool_pre_ping=True, future=True)
    with Session(engine) as db:
        ensure_default_guardrail_rules(db)
        db.commit()
    engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize MySQL 8.4 LTS schema, migrate SQLite data & seed HunarLink."
    )
    parser.add_argument("--mysql-url", help="Target MySQL SQLAlchemy URL (default: DATABASE_URL from .env)")
    parser.add_argument(
        "--from-sqlite",
        default=str(BACKEND_DIR / "hunarlink_dev.db"),
        help="Optional SQLite DB path to migrate rows from (default: ./hunarlink_dev.db)",
    )
    parser.add_argument("--skip-sqlite", action="store_true", help="Do not import rows from SQLite")
    parser.add_argument("--skip-seed", action="store_true", help="Do not seed real Kashmiri artisans")
    parser.add_argument("--verify-only", action="store_true", help="Only verify MySQL connection & table count")
    args = parser.parse_args()

    settings = get_settings()
    mysql_url = args.mysql_url or settings.database_url

    if args.verify_only:
        engine = create_engine(mysql_url, pool_pre_ping=True, future=True)
        tables = inspect(engine).get_table_names()
        print(f"MySQL OK: {len(tables)} tables present in target database.")
        engine.dispose()
        return

    install_mysql_schema(mysql_url)
    if not args.skip_sqlite:
        migrate_sqlite_to_mysql(pathlib.Path(args.from_sqlite), mysql_url)
    if not args.skip_seed:
        seed_real_artisans_and_rules(mysql_url)

    print("\nALL DONE! Run `python scripts/inspect_db.py` to inspect your live MySQL 8.4 database.")


if __name__ == "__main__":
    main()
