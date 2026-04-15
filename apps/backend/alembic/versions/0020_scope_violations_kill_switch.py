"""Add scope violations table and kill switch columns to scans.

Revision ID: 0020_scope_violations_kill_switch
Revises: 0019_generated_reports
Create Date: 2026-04-13

Creates:
    scope_violations — Immutable audit trail of out-of-scope detections

Modifies:
    scans — Add kill switch columns for emergency abort mechanism
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0020_scope_violations_kill_switch"
down_revision = "0019_generated_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create scope_violations table and add kill switch columns to scans."""

    # Create scope_violations table
    op.create_table(
        "scope_violations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "program_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("violation_type", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("target", sa.String(1000), nullable=True),
        sa.Column("immutable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "detected_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="safety_system"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for efficient querying
    op.create_index("ix_scope_violations_program_id", "scope_violations", ["program_id"])
    op.create_index("ix_scope_violations_scan_id", "scope_violations", ["scan_id"])
    op.create_index("ix_scope_violations_violation_type", "scope_violations", ["violation_type"])
    op.create_index("ix_scope_violations_detected_at", "scope_violations", ["detected_at"])

    # Add kill switch columns to scans table
    op.add_column("scans", sa.Column("abort_requested", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("scans", sa.Column("abort_requested_by", sa.String(255), nullable=True))
    op.add_column(
        "scans",
        sa.Column("abort_requested_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column("scans", sa.Column("abort_reason", sa.Text(), nullable=True))

    # Create index for fast abort status checks
    op.create_index("ix_scans_abort_requested", "scans", ["abort_requested"])


def downgrade() -> None:
    """Remove scope_violations table and kill switch columns from scans."""

    # Drop index first
    op.drop_index("ix_scans_abort_requested", table_name="scans")

    # Drop columns from scans
    op.drop_column("scans", "abort_reason")
    op.drop_column("scans", "abort_requested_at")
    op.drop_column("scans", "abort_requested_by")
    op.drop_column("scans", "abort_requested")

    # Drop indexes
    op.drop_index("ix_scope_violations_detected_at", table_name="scope_violations")
    op.drop_index("ix_scope_violations_violation_type", table_name="scope_violations")
    op.drop_index("ix_scope_violations_scan_id", table_name="scope_violations")
    op.drop_index("ix_scope_violations_program_id", table_name="scope_violations")

    # Drop table
    op.drop_table("scope_violations")
