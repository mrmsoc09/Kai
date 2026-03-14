"""workflow persistence extensions

Revision ID: 0005_workflow_persistence_extensions
Revises: 0004_workflow_persistence
Create Date: 2026-03-11 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0005_workflow_persistence_extensions"
down_revision = "0004_workflow_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_runs",
        sa.Column("scope_target_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "workflow_runs",
        sa.Column("trigger_source", sa.Text(), nullable=False, server_default="API"),
    )
    op.add_column(
        "workflow_runs",
        sa.Column("artifact_manifest_path", sa.Text(), nullable=True),
    )
    op.add_column("workflow_runs", sa.Column("duration_ms", sa.Float(), nullable=True))
    op.create_foreign_key(
        "fk_workflow_runs_scope_target_id_scope_targets",
        "workflow_runs",
        "scope_targets",
        ["scope_target_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("stage_runs", sa.Column("failure_reason", sa.Text(), nullable=True))
    op.add_column("stage_runs", sa.Column("duration_ms", sa.Float(), nullable=True))

    op.add_column(
        "tool_executions",
        sa.Column("stage_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("tool_executions", sa.Column("execution_mode", sa.Text(), nullable=True))
    op.add_column("tool_executions", sa.Column("artifact_path", sa.Text(), nullable=True))
    op.add_column("tool_executions", sa.Column("duration_ms", sa.Float(), nullable=True))
    op.create_foreign_key(
        "fk_tool_executions_stage_run_id_stage_runs",
        "tool_executions",
        "stage_runs",
        ["stage_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_tool_executions_stage_run_id",
        "tool_executions",
        ["stage_run_id"],
        unique=False,
    )

    op.add_column(
        "correlation_records",
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "correlation_records",
        sa.Column("asset_identifier", sa.Text(), nullable=True),
    )
    op.add_column(
        "correlation_records",
        sa.Column(
            "signal_sources_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "correlation_records",
        sa.Column("priority_rank", sa.Integer(), nullable=True),
    )
    op.add_column("correlation_records", sa.Column("explanation", sa.Text(), nullable=True))
    op.alter_column("correlation_records", "finding_id", nullable=True)
    op.alter_column("correlation_records", "observation_id", nullable=True)
    op.alter_column("correlation_records", "campaign_id", nullable=True)
    op.create_foreign_key(
        "fk_correlation_records_workflow_run_id_workflow_runs",
        "correlation_records",
        "workflow_runs",
        ["workflow_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_correlation_records_workflow_run_id",
        "correlation_records",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_correlation_records_asset_identifier",
        "correlation_records",
        ["asset_identifier"],
        unique=False,
    )

    op.create_table(
        "workflow_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "stage_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stage_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tool_execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tool_executions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("asset_identifier", sa.Text(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=True),
        sa.Column("parameter", sa.Text(), nullable=True),
        sa.Column("vulnerability_type", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("severity_hint", sa.Text(), nullable=True),
        sa.Column("evidence_artifact_path", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_workflow_findings_workflow_run_id",
        "workflow_findings",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_findings_campaign_id",
        "workflow_findings",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_findings_asset_identifier",
        "workflow_findings",
        ["asset_identifier"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_findings_vulnerability_type",
        "workflow_findings",
        ["vulnerability_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_findings_vulnerability_type", table_name="workflow_findings")
    op.drop_index("ix_workflow_findings_asset_identifier", table_name="workflow_findings")
    op.drop_index("ix_workflow_findings_campaign_id", table_name="workflow_findings")
    op.drop_index("ix_workflow_findings_workflow_run_id", table_name="workflow_findings")
    op.drop_table("workflow_findings")

    op.drop_index(
        "ix_correlation_records_asset_identifier",
        table_name="correlation_records",
    )
    op.drop_index(
        "ix_correlation_records_workflow_run_id",
        table_name="correlation_records",
    )
    op.drop_constraint(
        "fk_correlation_records_workflow_run_id_workflow_runs",
        "correlation_records",
        type_="foreignkey",
    )
    op.alter_column("correlation_records", "campaign_id", nullable=False)
    op.alter_column("correlation_records", "observation_id", nullable=False)
    op.alter_column("correlation_records", "finding_id", nullable=False)
    op.drop_column("correlation_records", "explanation")
    op.drop_column("correlation_records", "priority_rank")
    op.drop_column("correlation_records", "signal_sources_json")
    op.drop_column("correlation_records", "asset_identifier")
    op.drop_column("correlation_records", "workflow_run_id")

    op.drop_index("ix_tool_executions_stage_run_id", table_name="tool_executions")
    op.drop_constraint(
        "fk_tool_executions_stage_run_id_stage_runs",
        "tool_executions",
        type_="foreignkey",
    )
    op.drop_column("tool_executions", "duration_ms")
    op.drop_column("tool_executions", "artifact_path")
    op.drop_column("tool_executions", "execution_mode")
    op.drop_column("tool_executions", "stage_run_id")

    op.drop_column("stage_runs", "duration_ms")
    op.drop_column("stage_runs", "failure_reason")

    op.drop_constraint(
        "fk_workflow_runs_scope_target_id_scope_targets",
        "workflow_runs",
        type_="foreignkey",
    )
    op.drop_column("workflow_runs", "duration_ms")
    op.drop_column("workflow_runs", "artifact_manifest_path")
    op.drop_column("workflow_runs", "trigger_source")
    op.drop_column("workflow_runs", "scope_target_id")

