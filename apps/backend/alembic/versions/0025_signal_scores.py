"""Create signal_scores table.

Revision ID: 0025_signal_scores
Revises: 0024_attack_path_graph
Create Date: 2026-04-15
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0025_signal_scores"
down_revision = "0024_attack_path_graph"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("exploitability_score", sa.Float(), nullable=False),
        sa.Column("impact_score", sa.Float(), nullable=False),
        sa.Column("evidence_completeness", sa.Float(), nullable=False),
        sa.Column("novelty_score", sa.Float(), nullable=False),
        sa.Column("overall_priority", sa.Float(), nullable=False),
        sa.Column("score_rationale", sa.Text(), nullable=True),
        sa.Column("scored_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("scored_by", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "exploitability_score >= 0.0 AND exploitability_score <= 10.0",
            name="signal_scores_exploitability_range",
        ),
        sa.CheckConstraint(
            "impact_score >= 0.0 AND impact_score <= 10.0",
            name="signal_scores_impact_range",
        ),
        sa.CheckConstraint(
            "evidence_completeness >= 0.0 AND evidence_completeness <= 1.0",
            name="signal_scores_evidence_completeness_range",
        ),
        sa.CheckConstraint(
            "novelty_score >= 0.0 AND novelty_score <= 1.0",
            name="signal_scores_novelty_range",
        ),
        sa.CheckConstraint(
            "overall_priority >= 0.0 AND overall_priority <= 10.0",
            name="signal_scores_overall_priority_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_scores_campaign_id", "signal_scores", ["campaign_id"])
    op.create_index("ix_signal_scores_finding_id", "signal_scores", ["finding_id"])
    op.create_index("ix_signal_scores_scored_at", "signal_scores", ["scored_at"])


def downgrade() -> None:
    op.drop_index("ix_signal_scores_scored_at", table_name="signal_scores")
    op.drop_index("ix_signal_scores_finding_id", table_name="signal_scores")
    op.drop_index("ix_signal_scores_campaign_id", table_name="signal_scores")
    op.drop_table("signal_scores")
