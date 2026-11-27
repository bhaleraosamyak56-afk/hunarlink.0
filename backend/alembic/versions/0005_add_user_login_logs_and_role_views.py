"""Add user_login_logs table, users.last_login_at check, and per-role MySQL views.

Revision ID: 0005_add_user_login_logs_and_role_views
Revises: 0004_add_craftproof_and_demand_bridge
Create Date: 2026-11-27
"""
from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from app.modules.auth.role_views import SQL_VIEWS_PATH, _split_statements

revision = "0005_add_user_login_logs_and_role_views"
down_revision = "0004_add_craftproof_and_demand_bridge"
branch_labels = None
depends_on = None


def _uuid_col() -> sa.types.TypeEngine:
    return sa.String(length=36).with_variant(
        mysql.CHAR(36, charset="ascii", collation="ascii_bin"), "mysql"
    )


def upgrade() -> None:
    bind = op.get_bind()
    offline = context.is_offline_mode()
    insp = None if offline else sa.inspect(bind)

    if insp is not None and insp.has_table("users"):
        cols = {c["name"] for c in insp.get_columns("users")}
        if "last_login_at" not in cols:
            op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))

    if insp is None or not insp.has_table("user_login_logs"):
        op.create_table(
            "user_login_logs",
            sa.Column("id", _uuid_col(), nullable=False),
            sa.Column("user_id", _uuid_col(), nullable=False),
            sa.Column("role_code", sa.String(length=50), nullable=False),
            sa.Column("auth_event_type", sa.String(length=24), nullable=False),
            sa.Column("auth_method", sa.String(length=32), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_ull_user"),
            sa.PrimaryKeyConstraint("id"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_0900_ai_ci",
        )
        op.create_index(
            "idx_ull_user_role_event",
            "user_login_logs",
            ["user_id", "role_code", "auth_event_type"],
        )
        op.create_index(
            "idx_ull_role_event_time",
            "user_login_logs",
            ["role_code", "auth_event_type", "created_at"],
        )

    if bind.dialect.name == "mysql" and SQL_VIEWS_PATH.exists():
        sql_text = SQL_VIEWS_PATH.read_text(encoding="utf-8")
        for stmt in _split_statements(sql_text):
            if stmt.strip().upper().startswith("CREATE OR REPLACE VIEW"):
                op.execute(sa.text(stmt))


def downgrade() -> None:
    bind = op.get_bind()
    offline = context.is_offline_mode()
    insp = None if offline else sa.inspect(bind)
    if bind.dialect.name == "mysql":
        for view_name in (
            "vw_user_role_activity_summary",
            "vw_logged_in_wholesale_accounts",
            "vw_registered_wholesale_accounts",
            "vw_logged_in_admins",
            "vw_registered_admins",
            "vw_logged_in_artisans",
            "vw_registered_artisans",
            "vw_logged_in_buyers",
            "vw_registered_buyers",
        ):
            op.execute(sa.text(f"DROP VIEW IF EXISTS `{view_name}`"))
    if insp is None or insp.has_table("user_login_logs"):
        op.drop_table("user_login_logs")
