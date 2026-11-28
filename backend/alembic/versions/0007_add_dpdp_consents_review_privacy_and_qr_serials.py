"""Add DPDP user_consents ledger, anonymous reviews flag, and signed CraftPassport serial telemetry.

Revision ID: 0007_add_dpdp_consents_review_privacy_and_qr_serials
Revises: 0006_add_users_account_role
Create Date: 2026-11-28
"""
from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa

revision = "0007_add_dpdp_consents_review_privacy_and_qr_serials"
down_revision = "0006_add_users_account_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    offline = context.is_offline_mode()
    insp = None if offline else sa.inspect(bind)

    if insp is None or not insp.has_table("user_consents"):
        op.create_table(
            "user_consents",
            sa.Column("id", sa.CHAR(length=36), nullable=False),
            sa.Column("user_id", sa.CHAR(length=36), nullable=False),
            sa.Column("consent_scope", sa.String(length=64), nullable=False),
            sa.Column("policy_version", sa.String(length=32), nullable=False, server_default="2026-11-v1"),
            sa.Column("granted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("source_surface", sa.String(length=64), nullable=True),
            sa.Column("ip_hash", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column("granted_at", sa.DateTime(), nullable=True),
            sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("user_id", "consent_scope", name="uq_uc_user_scope"),
        )

    if insp is None or insp.has_table("product_reviews"):
        cols = set() if insp is None else {c["name"] for c in insp.get_columns("product_reviews")}
        if "is_anonymous" not in cols:
            op.add_column(
                "product_reviews",
                sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default=sa.false()),
            )

    if insp is None or insp.has_table("craft_passports"):
        cp_cols = set() if insp is None else {c["name"] for c in insp.get_columns("craft_passports")}
        if "serial_number" not in cp_cols:
            op.add_column("craft_passports", sa.Column("serial_number", sa.String(length=48), nullable=True))
        if "first_scanned_at" not in cp_cols:
            op.add_column("craft_passports", sa.Column("first_scanned_at", sa.DateTime(), nullable=True))
        if "scan_count" not in cp_cols:
            op.add_column(
                "craft_passports",
                sa.Column("scan_count", sa.Integer(), nullable=False, server_default="0"),
            )


def downgrade() -> None:
    bind = op.get_bind()
    offline = context.is_offline_mode()
    insp = None if offline else sa.inspect(bind)
    if insp is None or insp.has_table("craft_passports"):
        cp_cols = set() if insp is None else {c["name"] for c in insp.get_columns("craft_passports")}
        for col in ("scan_count", "first_scanned_at", "serial_number"):
            if col in cp_cols:
                op.drop_column("craft_passports", col)
    if insp is None or insp.has_table("product_reviews"):
        cols = set() if insp is None else {c["name"] for c in insp.get_columns("product_reviews")}
        if "is_anonymous" in cols:
            op.drop_column("product_reviews", "is_anonymous")
    if insp is None or insp.has_table("user_consents"):
        op.drop_table("user_consents")
