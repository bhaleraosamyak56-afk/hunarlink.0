"""Add digilocker_verifications table for mandatory DigiLocker Artisan Card verification.

Revision ID: 0008_add_digilocker_verifications
Revises: 0007_add_dpdp_consents_review_privacy_and_qr_serials
Create Date: 2026-11-28
"""
from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa

revision = "0008_add_digilocker_verifications"
down_revision = "0007_add_dpdp_consents_review_privacy_and_qr_serials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    offline = context.is_offline_mode()
    insp = None if offline else sa.inspect(bind)

    if insp is None or not insp.has_table("digilocker_verifications"):
        op.create_table(
            "digilocker_verifications",
            sa.Column("id", sa.CHAR(length=36), nullable=False),
            sa.Column("user_id", sa.CHAR(length=36), nullable=False),
            sa.Column("state_token", sa.String(length=128), nullable=False),
            sa.Column("pkce_verifier", sa.String(length=255), nullable=True),
            sa.Column("mode", sa.String(length=16), nullable=False, server_default="SANDBOX"),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="INITIATED"),
            sa.Column("issuer_id", sa.String(length=128), nullable=True),
            sa.Column("issuer_name", sa.String(length=255), nullable=True),
            sa.Column("doc_type", sa.String(length=64), nullable=True),
            sa.Column("doc_uri", sa.String(length=255), nullable=True),
            sa.Column("artisan_card_number", sa.String(length=100), nullable=True),
            sa.Column("card_holder_name", sa.String(length=160), nullable=True),
            sa.Column("craft_category", sa.String(length=160), nullable=True),
            sa.Column("district", sa.String(length=120), nullable=True),
            sa.Column("issued_date", sa.String(length=32), nullable=True),
            sa.Column("file_scan_id", sa.CHAR(length=36), nullable=True),
            sa.Column("raw_claims_json", sa.JSON(), nullable=True),
            sa.Column("return_to", sa.String(length=255), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("fetched_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("state_token", name="uq_dlv_state_token"),
        )
        op.create_index("idx_dlv_user_id", "digilocker_verifications", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    offline = context.is_offline_mode()
    insp = None if offline else sa.inspect(bind)
    if insp is None or insp.has_table("digilocker_verifications"):
        op.drop_index("idx_dlv_user_id", table_name="digilocker_verifications")
        op.drop_table("digilocker_verifications")
