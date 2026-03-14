"""workflow persistence

Revision ID: 0004_workflow_persistence
Revises: 0003_campaign_execution_schema
Create Date: 2026-03-11 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0004_workflow_persistence"
down_revision = "0003_campaign_execution_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    workflow_run_status_enum = postgresql.ENUM(
        "PENDING",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "CANCELED",
        name="workflow_run_status_enum",
    )
    stage_run_status_enum = postgresql.ENUM(
        "PENDING",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "BLOCKED",
        name="stage_run_status_enum",
    )
    correlation_action_enum = postgresql.ENUM(
        "CREATED",
        "ATTACHED",
        "ALREADY_LINKED",
        "DEDUPLICATED",
        "CONTEXT_ONLY",
        "UNSUPPORTED",
        name="correlation_action_enum",
    )

    workflow_run_status_enum.create(bind, checkfirst=True)
    stage_run_status_enum.create(bind, checkfirst=True)
    correlation_action_enum.create(bind, checkfirst=True)

    op.create_table(
        "workflow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("template_name", sa.Text, nullable=False),
        sa.Column("target", sa.Text, nullable=False),
        sa.Column("safe_mode", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("dry_run", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("total_phases", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed_phases", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                "CANCELED",
                name="workflow_run_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("plan_artifact_path", sa.Text, nullable=True),
        sa.Column("summary_artifact_path", sa.Text, nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
    op.create_index("ix_workflow_runs_campaign_run_id", "workflow_runs", ["campaign_run_id"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])

    op.create_table(
        "stage_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage_name", sa.Text, nullable=False),
        sa.Column("stage_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("phase_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                "BLOCKED",
                name="stage_run_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.UniqueConstraint("workflow_run_id", "stage_name", name="uq_stage_runs_workflow_stage"),
    )
    op.create_index("ix_stage_runs_workflow_run_id", "stage_runs", ["workflow_run_id"])
    op.create_index("ix_stage_runs_campaign_run_id", "stage_runs", ["campaign_run_id"])

    op.create_table(
        "correlation_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "observation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("observations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "correlation_rule",
            sa.Text,
            nullable=False,
            server_default="deterministic_title_match",
        ),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column(
            "action",
            postgresql.ENUM(
                "CREATED",
                "ATTACHED",
                "ALREADY_LINKED",
                "DEDUPLICATED",
                "CONTEXT_ONLY",
                "UNSUPPORTED",
                name="correlation_action_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "duplicate_of_finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "correlated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
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
    op.create_index("ix_correlation_records_finding_id", "correlation_records", ["finding_id"])
    op.create_index(
        "ix_correlation_records_observation_id", "correlation_records", ["observation_id"]
    )
    op.create_index("ix_correlation_records_campaign_id", "correlation_records", ["campaign_id"])

    op.add_column(
        "phase_jobs",
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "phase_jobs",
        sa.Column("stage_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_phase_jobs_workflow_run_id",
        "phase_jobs",
        "workflow_runs",
        ["workflow_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_phase_jobs_stage_run_id",
        "phase_jobs",
        "stage_runs",
        ["stage_run_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_constraint("fk_phase_jobs_workflow_run_id", "phase_jobs", type_="foreignkey")
    op.drop_constraint("fk_phase_jobs_stage_run_id", "phase_jobs", type_="foreignkey")
    op.drop_column("phase_jobs", "workflow_run_id")
    op.drop_column("phase_jobs", "stage_run_id")

    op.drop_index("ix_correlation_records_campaign_id", table_name="correlation_records")
    op.drop_index("ix_correlation_records_observation_id", table_name="correlation_records")
    op.drop_index("ix_correlation_records_finding_id", table_name="correlation_records")
    op.drop_table("correlation_records")

    op.drop_index("ix_stage_runs_campaign_run_id", table_name="stage_runs")
    op.drop_index("ix_stage_runs_workflow_run_id", table_name="stage_runs")
    op.drop_table("stage_runs")

    op.drop_index("ix_workflow_runs_status", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_campaign_run_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")

    postgresql.ENUM(name="correlation_action_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="stage_run_status_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="workflow_run_status_enum").drop(bind, checkfirst=True)
