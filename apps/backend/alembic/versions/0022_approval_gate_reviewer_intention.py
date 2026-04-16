"""Add reviewer_intention column to approval_gates.

Revision ID: 0022_approval_gate_reviewer_intention
Revises: 0021_finding_overrides_validation_status
Create Date: 2026-04-15
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0022_approval_gate_reviewer_intention"
down_revision = "0021_finding_overrides_validation_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "approval_gates",
        sa.Column("reviewer_intention", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_approval_gates_reviewer_intention_notnull",
        "approval_gates",
        ["reviewer_intention"],
        postgresql_where=sa.text("reviewer_intention IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_approval_gates_reviewer_intention_notnull",
        table_name="approval_gates",
    )
    op.drop_column("approval_gates", "reviewer_intention")
