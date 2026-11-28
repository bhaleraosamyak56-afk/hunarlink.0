"""Helpers for `users.account_role`, `users.last_login_at`, `user_login_logs`, and MySQL role views."""
from __future__ import annotations

from collections.abc import Iterable
import pathlib
import re

from sqlalchemy import Engine, inspect, text

from app.models.core_models import ProductReview, UserLoginLog

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
SQL_VIEWS_PATH = REPO_ROOT / "hunarlink-database" / "sql" / "15_role_registration_and_login_views.sql"


def derive_account_role(
    role_codes: Iterable[str] = (),
    *,
    account_status: str = "ACTIVE",
    has_seller_profile: bool = False,
    is_admin: bool = False,
) -> str:
    """Resolve the canonical root `users.account_role` value.

    Values: BUYER | ARTISAN | ADMIN | WHOLESALE_BUYER | DEALER | SUPPLIER | DEACTIVATED
    """
    if str(account_status or "").upper() == "DEACTIVATED":
        return "DEACTIVATED"
    codes = {str(c).strip().upper() for c in role_codes if c}
    if is_admin or "ADMIN" in codes or codes & {
        "SUPER_ADMIN",
        "OPS_ADMIN",
        "VERIFICATION_OFFICER",
        "FINANCE_ADMIN",
    }:
        return "ADMIN"
    if has_seller_profile or "DIRECT_SELLER" in codes or "ARTISAN" in codes:
        return "ARTISAN"
    if "WHOLESALE_BUYER" in codes:
        return "WHOLESALE_BUYER"
    if "DEALER" in codes:
        return "DEALER"
    if "SUPPLIER" in codes:
        return "SUPPLIER"
    return "BUYER"


def _split_statements(sql_text: str) -> list[str]:
    stmts: list[str] = []
    buf: list[str] = []
    for raw_line in sql_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        if stripped.upper().startswith("USE "):
            continue
        buf.append(raw_line)
        if stripped.endswith(";"):
            stmts.append("\n".join(buf).rstrip().rstrip(";"))
            buf.clear()
    leftover = "\n".join(buf).strip()
    if leftover:
        stmts.append(leftover.rstrip(";"))
    return stmts


def backfill_users_account_role(bind_or_engine) -> int:
    """Backfill `users.account_role` from role assignments, seller_profiles, and admin tables."""
    from sqlalchemy.engine import Connection

    def _run(conn: Connection) -> int:
        insp = inspect(conn)
        if not insp.has_table("users"):
            return 0
        user_cols = {c["name"] for c in insp.get_columns("users")}
        if "account_role" not in user_cols:
            return 0

        has_ura = insp.has_table("user_role_assignments") and insp.has_table("platform_roles")
        has_sp = insp.has_table("seller_profiles")
        has_ap = insp.has_table("admin_profiles")
        has_ac = insp.has_table("admin_credentials")

        updated = 0
        rows = conn.execute(
            text("SELECT id, clerk_user_id, account_role, account_status FROM users")
        ).fetchall()
        for uid, clerk_id, current_role, acc_status in rows:
            role_codes: set[str] = set()
            if has_ura:
                assigned = conn.execute(
                    text(
                        "SELECT pr.code FROM user_role_assignments ura "
                        "JOIN platform_roles pr ON pr.id = ura.platform_role_id "
                        "WHERE ura.user_id = :uid AND ura.assignment_status = 'ACTIVE'"
                    ),
                    {"uid": uid},
                ).fetchall()
                role_codes.update(str(r[0]) for r in assigned if r[0])

            has_seller = False
            if has_sp:
                sp_cnt = conn.execute(
                    text("SELECT COUNT(*) FROM seller_profiles WHERE user_id = :uid"),
                    {"uid": uid},
                ).scalar()
                has_seller = bool(sp_cnt and int(sp_cnt) > 0)

            is_admin = str(clerk_id or "").startswith("hl_admin_")
            if not is_admin and has_ap:
                ap_cnt = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM admin_profiles "
                        "WHERE user_id = :uid AND admin_status = 'ACTIVE'"
                    ),
                    {"uid": uid},
                ).scalar()
                if ap_cnt and int(ap_cnt) > 0:
                    is_admin = True
            if not is_admin and has_ac:
                ac_cnt = conn.execute(
                    text("SELECT COUNT(*) FROM admin_credentials WHERE user_id = :uid"),
                    {"uid": uid},
                ).scalar()
                if ac_cnt and int(ac_cnt) > 0:
                    is_admin = True

            target_role = derive_account_role(
                role_codes,
                account_status=str(acc_status or "ACTIVE"),
                has_seller_profile=has_seller,
                is_admin=is_admin,
            )
            if current_role != target_role:
                conn.execute(
                    text("UPDATE users SET account_role = :role WHERE id = :uid"),
                    {"role": target_role, "uid": uid},
                )
                updated += 1
        return updated

    if isinstance(bind_or_engine, Connection):
        return _run(bind_or_engine)
    with bind_or_engine.begin() as conn:
        return _run(conn)


def ensure_login_tracking_and_views(engine: Engine) -> dict:
    """Idempotently ensure `users.account_role`, `users.last_login_at`, `user_login_logs`, and MySQL views."""
    insp = inspect(engine)
    account_role_added = False
    last_login_added = False
    backfilled_roles = 0

    if insp.has_table("users"):
        user_cols = {c["name"] for c in insp.get_columns("users")}
        if "account_role" not in user_cols:
            if engine.dialect.name == "mysql":
                col_ddl = (
                    "ENUM('BUYER','ARTISAN','ADMIN','WHOLESALE_BUYER','DEALER','SUPPLIER','DEACTIVATED') "
                    "NOT NULL DEFAULT 'BUYER' AFTER `preferred_currency`"
                )
            else:
                col_ddl = "VARCHAR(32) NOT NULL DEFAULT 'BUYER'"
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN account_role {col_ddl}"))
                if engine.dialect.name == "mysql":
                    try:
                        conn.execute(text("CREATE INDEX idx_users_account_role ON users (account_role)"))
                    except Exception:
                        pass
            account_role_added = True

        if "last_login_at" not in user_cols:
            col_ddl = "DATETIME(6) NULL" if engine.dialect.name == "mysql" else "DATETIME NULL"
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN last_login_at {col_ddl}"))
            last_login_added = True

        backfilled_roles = backfill_users_account_role(engine)

    table_existed = insp.has_table("user_login_logs")
    UserLoginLog.__table__.create(bind=engine, checkfirst=True)
    ProductReview.__table__.create(bind=engine, checkfirst=True)
    table_created = not table_existed and inspect(engine).has_table("user_login_logs")

    views_applied: list[str] = []
    if engine.dialect.name == "mysql" and SQL_VIEWS_PATH.exists():
        sql_text = SQL_VIEWS_PATH.read_text(encoding="utf-8")
        with engine.begin() as conn:
            for stmt in _split_statements(sql_text):
                if stmt.strip().upper().startswith("CREATE OR REPLACE VIEW"):
                    conn.execute(text(stmt))
                    m = re.search(r"CREATE OR REPLACE VIEW\s+`?([a-zA-Z0-9_]+)`?", stmt, re.I)
                    if m:
                        views_applied.append(m.group(1))

    return {
        "dialect": engine.dialect.name,
        "account_role_column_added": account_role_added,
        "account_roles_backfilled": backfilled_roles,
        "last_login_column_added": last_login_added,
        "login_logs_table_created": table_created,
        "views_applied": views_applied,
    }
