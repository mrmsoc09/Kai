"""Persist opportunity scan queue settings per user + tenant

Revision ID: 0014_user_scan_queue_settings
Revises: 0013_auth_initial_password_setup
Create Date: 2026-03-23
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0014_user_scan_queue_settings"
down_revision = "0013_auth_initial_password_setup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_scan_queue_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("min_concurrent", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_concurrent", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_user_scan_queue_settings_user_tenant"),
        sa.CheckConstraint("min_concurrent >= 1", name="ck_user_scan_queue_settings_min_ge_1"),
        sa.CheckConstraint("max_concurrent >= 1", name="ck_user_scan_queue_settings_max_ge_1"),
        sa.CheckConstraint("max_concurrent <= 20", name="ck_user_scan_queue_settings_max_le_20"),
        sa.CheckConstraint("min_concurrent <= max_concurrent", name="ck_user_scan_queue_settings_min_le_max"),
    )
    op.create_index("ix_user_scan_queue_settings_user_id", "user_scan_queue_settings", ["user_id"])
    op.create_index("ix_user_scan_queue_settings_tenant_id", "user_scan_queue_settings", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_user_scan_queue_settings_tenant_id", table_name="user_scan_queue_settings")
    op.drop_index("ix_user_scan_queue_settings_user_id", table_name="user_scan_queue_settings")
    op.drop_table("user_scan_queue_settings")

