"""Add account_role column directly onto root users table + backfill existing accounts.

Revision ID: 0006_add_users_account_role
Revises: 0005_add_user_login_logs_and_role_views
Create Date: 2026-11-28
"""
from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from app.modules.auth.role_views import (
    SQL_VIEWS_PATH,
    _split_statements,
    backfill_users_account_role,
)

revision = "0006_add_users_account_role"
down_revision = "0005_add_user_login_logs_and_role_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    offline = context.is_offline_mode()
    insp = None if offline else sa.inspect(bind)

    if insp is None or insp.has_table("users"):
        cols = set() if insp is None else {c["name"] for c in insp.get_columns("users")}
        if "account_role" not in cols:
            col_type = sa.String(length=32).with_variant(
                mysql.ENUM(
                    "BUYER",
                    "ARTISAN",
                    "ADMIN",
                    "WHOLESALE_BUYER",
                    "DEALER",
                    "SUPPLIER",
                    "DEACTIVATED",
                ),
                "mysql",
            )
            op.add_column(
                "users",
                sa.Column("account_role", col_type, nullable=False, server_default="BUYER"),
            )
            existing_idx = (
                {idx["name"] for idx in insp.get_indexes("users")} if insp is not None else set()
            )
            if "idx_users_account_role" not in existing_idx:
                op.create_index("idx_users_account_role", "users", ["account_role"])

    if not offline and bind is not None:
        backfill_users_account_role(bind)

    if bind.dialect.name == "mysql" and SQL_VIEWS_PATH.exists():
        sql_text = SQL_VIEWS_PATH.read_text(encoding="utf-8")
        for stmt in _split_statements(sql_text):
            if stmt.strip().upper().startswith("CREATE OR REPLACE VIEW"):
                op.execute(sa.text(stmt))


def downgrade() -> None:
    bind = op.get_bind()
    offline = context.is_offline_mode()
    insp = None if offline else sa.inspect(bind)
    if insp is None or insp.has_table("users"):
        cols = set() if insp is None else {c["name"] for c in insp.get_columns("users")}
        if "account_role" in cols:
            existing_idx = (
                {idx["name"] for idx in insp.get_indexes("users")} if insp is not None else set()
            )
            if "idx_users_account_role" in existing_idx:
                op.drop_index("idx_users_account_role", table_name="users")
            op.drop_column("users", "account_role")
