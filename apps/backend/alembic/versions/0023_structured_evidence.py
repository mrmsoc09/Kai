"""Create structured_evidence table.

Revision ID: 0023_structured_evidence
Revises: 0022_approval_gate_reviewer_intention
Create Date: 2026-04-15
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0023_structured_evidence"
down_revision = "0022_approval_gate_reviewer_intention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "structured_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("evidence_type", sa.Text(), nullable=False),
        sa.Column("source_phase", sa.Text(), nullable=True),
        sa.Column("collected_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("collected_by", sa.Text(), nullable=False),
        sa.Column("artifact_uri", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "validation_status",
            sa.Text(),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "validation_status IN ('PENDING', 'CONFIRMED', 'REJECTED')",
            name="structured_evidence_validation_status_allowed",
        ),
    )
    op.create_index("ix_structured_evidence_campaign_id", "structured_evidence", ["campaign_id"])
    op.create_index("ix_structured_evidence_finding_id", "structured_evidence", ["finding_id"])
    op.create_index(
        "ix_structured_evidence_validation_status", "structured_evidence", ["validation_status"]
    )
    op.create_index("ix_structured_evidence_collected_at", "structured_evidence", ["collected_at"])


def downgrade() -> None:
    op.drop_index("ix_structured_evidence_collected_at", table_name="structured_evidence")
    op.drop_index("ix_structured_evidence_validation_status", table_name="structured_evidence")
    op.drop_index("ix_structured_evidence_finding_id", table_name="structured_evidence")
    op.drop_index("ix_structured_evidence_campaign_id", table_name="structured_evidence")
    op.drop_table("structured_evidence")
