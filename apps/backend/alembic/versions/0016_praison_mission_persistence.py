"""Add praison_missions and praison_tool_runs tables

Revision ID: 0016_praison_mission_persistence
Revises: 0015_scan_pool_tables
Create Date: 2026-03-27

Creates:
    praison_missions   — one row per autonomous mission lifecycle
    praison_tool_runs  — one row per tool invocation within a mission
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0016_praison_mission_persistence"
down_revision = "0015_scan_pool_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "praison_missions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=True),
        sa.Column("workflow_id", sa.Text(), nullable=False),
        sa.Column("program_id", sa.Text(), nullable=False),
        sa.Column("mission_name", sa.Text(), nullable=True),
        sa.Column("execution_mode", sa.Text(), nullable=False, server_default="live"),
        sa.Column("status", sa.Text(), nullable=False, server_default="created"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("tools_executed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("artifacts_written", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("final_state_summary", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_praison_missions"),
        sa.UniqueConstraint("mission_id", name="uq_praison_missions_mission_id"),
    )
    op.create_index("ix_praison_missions_program_id", "praison_missions", ["program_id"])
    op.create_index("ix_praison_missions_workflow_id", "praison_missions", ["workflow_id"])
    op.create_index("ix_praison_missions_status", "praison_missions", ["status"])
    op.create_index("ix_praison_missions_tenant_id", "praison_missions", ["tenant_id"])

    op.create_table(
        "praison_tool_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=True),
        sa.Column("tool_id", sa.Text(), nullable=False),
        sa.Column("target", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="completed"),
        sa.Column("execution_time_ms", sa.Float(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_praison_tool_runs"),
    )
    op.create_index("ix_praison_tool_runs_mission_id", "praison_tool_runs", ["mission_id"])
    op.create_index("ix_praison_tool_runs_tool_id", "praison_tool_runs", ["tool_id"])
    op.create_index("ix_praison_tool_runs_agent_id", "praison_tool_runs", ["agent_id"])
    op.create_index("ix_praison_tool_runs_status", "praison_tool_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_praison_tool_runs_status", table_name="praison_tool_runs")
    op.drop_index("ix_praison_tool_runs_agent_id", table_name="praison_tool_runs")
    op.drop_index("ix_praison_tool_runs_tool_id", table_name="praison_tool_runs")
    op.drop_index("ix_praison_tool_runs_mission_id", table_name="praison_tool_runs")
    op.drop_table("praison_tool_runs")

    op.drop_index("ix_praison_missions_tenant_id", table_name="praison_missions")
    op.drop_index("ix_praison_missions_status", table_name="praison_missions")
    op.drop_index("ix_praison_missions_workflow_id", table_name="praison_missions")
    op.drop_index("ix_praison_missions_program_id", table_name="praison_missions")
    op.drop_table("praison_missions")
