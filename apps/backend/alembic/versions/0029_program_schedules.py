"""Program schedules table.

Revision ID: 0029_program_schedules
Revises: 0028_dedup_and_execution_jobs
Create Date: 2026-04-15

Changes:
- Create program_schedules table for periodic hunt scheduling
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0029_program_schedules"
down_revision = "0028_dedup_and_execution_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "program_schedules",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("program_handle", sa.Text, nullable=False),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("targets", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("interval_hours", sa.Integer, nullable=False, server_default="24"),
        sa.Column("next_run_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.UniqueConstraint("program_handle", name="uq_program_schedules_handle"),
    )


def downgrade() -> None:
    op.drop_table("program_schedules")
