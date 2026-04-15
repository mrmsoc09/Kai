"""Add opportunity_credentials and opportunity_access_metadata tables

Revision ID: 0017_opportunity_credentials
Revises: 0016_praison_mission_persistence
Create Date: 2026-04-13

Creates:
    opportunity_credentials     — tracks credentials stored in Vault per opportunity
    opportunity_access_metadata — describes available access types per program
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0017_opportunity_credentials"
down_revision = "0016_praison_mission_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create opportunity_credentials table
    op.create_table(
        "opportunity_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("vault_secret_path", sa.Text(), nullable=False),
        sa.Column("credential_username", sa.Text(), nullable=True),
        sa.Column("last_validated", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("validation_method", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("last_accessed_by", sa.Text(), nullable=True),
        sa.Column("last_accessed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "access_type IN ('unauthenticated', 'user_account', 'api_key', 'hunter_account', 'admin_account')",
            name="opportunity_credentials_access_type_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'invalid', 'needs_renewal')",
            name="opportunity_credentials_status_allowed",
        ),
        sa.CheckConstraint(
            "validation_method IN ('login_test', 'api_ping', 'manual')",
            name="opportunity_credentials_validation_method_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["programs.id"],
            name="fk_opportunity_credentials_program_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_opportunity_credentials"),
        sa.UniqueConstraint(
            "program_id",
            "access_type",
            name="uq_opportunity_credentials_program_access_type",
        ),
    )
    op.create_index("ix_opportunity_credentials_program_id", "opportunity_credentials", ["program_id"])
    op.create_index("ix_opportunity_credentials_status", "opportunity_credentials", ["status"])

    # Create opportunity_access_metadata table
    op.create_table(
        "opportunity_access_metadata",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_type", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("signup_url", sa.Text(), nullable=True),
        sa.Column("signup_instructions", sa.Text(), nullable=True),
        sa.Column("requires_email", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("requires_payment", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("rate_limits", sa.Text(), nullable=True),
        sa.Column("available_endpoints", sa.Text(), nullable=True),
        sa.Column("testing_account_available", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("testing_account_url", sa.Text(), nullable=True),
        sa.Column("testing_instructions", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "access_type IN ('unauthenticated', 'user_account', 'api_key', 'hunter_account', 'admin_account')",
            name="opportunity_access_metadata_access_type_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["programs.id"],
            name="fk_opportunity_access_metadata_program_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_opportunity_access_metadata"),
        sa.UniqueConstraint(
            "program_id",
            "access_type",
            name="uq_opportunity_access_metadata_program_access_type",
        ),
    )
    op.create_index("ix_opportunity_access_metadata_program_id", "opportunity_access_metadata", ["program_id"])


def downgrade() -> None:
    op.drop_index("ix_opportunity_access_metadata_program_id", table_name="opportunity_access_metadata")
    op.drop_table("opportunity_access_metadata")

    op.drop_index("ix_opportunity_credentials_status", table_name="opportunity_credentials")
    op.drop_index("ix_opportunity_credentials_program_id", table_name="opportunity_credentials")
    op.drop_table("opportunity_credentials")
