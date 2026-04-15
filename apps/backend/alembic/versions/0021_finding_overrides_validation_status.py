"""Add finding overrides audit table and analyst validation status column.

Revision ID: 0021_finding_overrides_validation_status
Revises: 0020_scope_violations_kill_switch
Create Date: 2026-04-13
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0021_finding_overrides_validation_status"
down_revision = "0020_scope_violations_kill_switch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scan_findings",
        sa.Column(
            "validation_status",
            sa.String(length=50),
            nullable=False,
            server_default="pending_analyst_review",
        ),
    )
    op.create_check_constraint(
        "scan_findings_validation_status_allowed",
        "scan_findings",
        "validation_status IN ('pending_analyst_review', 'approved_for_submission', 'excluded')",
    )
    op.create_index("ix_scan_findings_validation_status", "scan_findings", ["validation_status"])

    op.create_table(
        "finding_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scan_findings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("override_decision", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("analyst_notes", sa.Text(), nullable=True),
        sa.Column("overridden_by", sa.String(length=255), nullable=False),
        sa.Column(
            "overridden_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("immutable", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_finding_overrides_finding_id", "finding_overrides", ["finding_id"])
    op.create_index("ix_finding_overrides_decision", "finding_overrides", ["override_decision"])
    op.create_index("ix_finding_overrides_overridden_by", "finding_overrides", ["overridden_by"])


def downgrade() -> None:
    op.drop_index("ix_finding_overrides_overridden_by", table_name="finding_overrides")
    op.drop_index("ix_finding_overrides_decision", table_name="finding_overrides")
    op.drop_index("ix_finding_overrides_finding_id", table_name="finding_overrides")
    op.drop_table("finding_overrides")

    op.drop_index("ix_scan_findings_validation_status", table_name="scan_findings")
    op.drop_constraint("scan_findings_validation_status_allowed", "scan_findings", type_="check")
    op.drop_column("scan_findings", "validation_status")

