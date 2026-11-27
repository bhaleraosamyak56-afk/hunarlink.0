"""Helpers to ensure `user_login_logs`, `users.last_login_at`, and MySQL role views exist."""
from __future__ import annotations

import pathlib

import re

from sqlalchemy import Engine, inspect, text

from app.models.core_models import UserLoginLog

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
SQL_VIEWS_PATH = REPO_ROOT / "hunarlink-database" / "sql" / "15_role_registration_and_login_views.sql"


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


def ensure_login_tracking_and_views(engine: Engine) -> dict:
    """Idempotently create `user_login_logs`, `users.last_login_at`, and MySQL role views."""
    insp = inspect(engine)
    last_login_added = False
    if insp.has_table("users"):
        user_cols = {c["name"] for c in insp.get_columns("users")}
        if "last_login_at" not in user_cols:
            col_ddl = "DATETIME(6) NULL" if engine.dialect.name == "mysql" else "DATETIME NULL"
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN last_login_at {col_ddl}"))
            last_login_added = True

    table_existed = insp.has_table("user_login_logs")
    UserLoginLog.__table__.create(bind=engine, checkfirst=True)
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
        "last_login_column_added": last_login_added,
        "login_logs_table_created": table_created,
        "views_applied": views_applied,
    }
