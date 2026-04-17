"""Dedup fingerprints and execution jobs tables.

Revision ID: 0028_dedup_and_execution_jobs
Revises: 0027_phase2_evidence_lifecycle
Create Date: 2026-04-15

Changes:
- Create dedup_fingerprints table with unique (campaign_id, fingerprint) index
- Create execution_jobs table with campaign_id and state indexes
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028_dedup_and_execution_jobs"
down_revision = "0027_phase2_evidence_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # dedup_fingerprints
    # ------------------------------------------------------------------
    op.create_table(
        "dedup_fingerprints",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", sa.Text, nullable=False),
        sa.Column("finding_id", sa.Text, nullable=True),
        sa.Column("fingerprint", sa.Text, nullable=False),
        sa.Column("endpoint", sa.Text, nullable=False),
        sa.Column("vuln_type", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_unique_constraint(
        "uq_dedup_fingerprints_campaign_fp",
        "dedup_fingerprints",
        ["campaign_id", "fingerprint"],
    )
    op.create_index(
        "ix_dedup_fingerprints_campaign_id",
        "dedup_fingerprints",
        ["campaign_id"],
    )
    op.create_index(
        "ix_dedup_fingerprints_campaign_endpoint",
        "dedup_fingerprints",
        ["campaign_id", "endpoint"],
    )

    # ------------------------------------------------------------------
    # execution_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "execution_jobs",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("campaign_id", sa.Text, nullable=False),
        sa.Column("tool_name", sa.Text, nullable=False),
        sa.Column("target", sa.Text, nullable=False),
        sa.Column("state", sa.Text, nullable=False, server_default="PENDING"),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "state IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'RETRYING', 'CANCELED')",
            name="execution_jobs_state_allowed",
        ),
        sa.CheckConstraint("attempt >= 0", name="execution_jobs_attempt_non_negative"),
        sa.CheckConstraint("max_attempts >= 1", name="execution_jobs_max_attempts_positive"),
    )
    op.create_index("ix_execution_jobs_campaign_id", "execution_jobs", ["campaign_id"])
    op.create_index("ix_execution_jobs_state", "execution_jobs", ["state"])


def downgrade() -> None:
    op.drop_table("execution_jobs")
    op.drop_table("dedup_fingerprints")
