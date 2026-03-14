"""bug bounty continuous hunting persistence

Revision ID: 0006_bug_bounty_continuous_hunting
Revises: 0005_workflow_persistence_extensions
Create Date: 2026-03-13 16:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0006_bug_bounty_continuous_hunting"
down_revision = "0005_workflow_persistence_extensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scope_targets",
        sa.Column("monitoring_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "scope_targets",
        sa.Column("monitoring_priority_tier", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "scope_targets",
        sa.Column("monitoring_status", sa.Text(), nullable=False, server_default="ACTIVE"),
    )
    op.add_column("scope_targets", sa.Column("monitoring_source", sa.Text(), nullable=True))
    op.add_column("scope_targets", sa.Column("monitoring_notes", sa.Text(), nullable=True))
    op.add_column(
        "scope_targets",
        sa.Column("safe_mode_required", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "scope_targets",
        sa.Column("last_checked_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "scope_targets",
        sa.Column("last_success_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "scope_targets",
        sa.Column("last_failure_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "scope_targets",
        sa.Column("next_scheduled_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_scope_targets_monitoring_enabled",
        "scope_targets",
        ["monitoring_enabled"],
        unique=False,
    )
    op.create_index(
        "ix_scope_targets_next_scheduled_run_at",
        "scope_targets",
        ["next_scheduled_run_at"],
        unique=False,
    )

    op.create_table(
        "hunt_schedule_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "program_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scope_target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scope_targets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workflow_template", sa.Text(), nullable=False),
        sa.Column("schedule_type", sa.Text(), nullable=False, server_default="interval"),
        sa.Column("interval_minutes", sa.Integer(), nullable=True),
        sa.Column("cron_expr", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="ACTIVE"),
        sa.Column("safe_mode", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("priority_tier", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("max_concurrency", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("failure_backoff_minutes", sa.Integer(), nullable=False, server_default="240"),
        sa.Column("failure_pause_threshold", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_run_started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_run_finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_run_status", sa.Text(), nullable=True),
        sa.Column("last_failure_reason", sa.Text(), nullable=True),
        sa.Column("next_scheduled_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("paused_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("paused_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
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
        sa.UniqueConstraint(
            "program_id",
            "scope_target_id",
            "workflow_template",
            name="uq_hunt_schedule_jobs_program_target_template",
        ),
        sa.CheckConstraint(
            "btrim(workflow_template) <> ''",
            name="hunt_schedule_jobs_template_not_empty",
        ),
        sa.CheckConstraint(
            "schedule_type IN ('interval', 'cron')",
            name="hunt_schedule_jobs_schedule_type_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'PAUSED', 'DISABLED', 'ERROR')",
            name="hunt_schedule_jobs_status_allowed",
        ),
        sa.CheckConstraint(
            "interval_minutes IS NULL OR interval_minutes > 0",
            name="hunt_schedule_jobs_interval_positive",
        ),
        sa.CheckConstraint(
            "max_concurrency > 0",
            name="hunt_schedule_jobs_max_concurrency_positive",
        ),
        sa.CheckConstraint(
            "cooldown_minutes >= 0",
            name="hunt_schedule_jobs_cooldown_non_negative",
        ),
        sa.CheckConstraint(
            "failure_backoff_minutes >= 0",
            name="hunt_schedule_jobs_failure_backoff_non_negative",
        ),
        sa.CheckConstraint(
            "failure_pause_threshold >= 1",
            name="hunt_schedule_jobs_failure_pause_threshold_positive",
        ),
    )
    op.create_index("ix_hunt_schedule_jobs_program_id", "hunt_schedule_jobs", ["program_id"], unique=False)
    op.create_index(
        "ix_hunt_schedule_jobs_scope_target_id",
        "hunt_schedule_jobs",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index("ix_hunt_schedule_jobs_status", "hunt_schedule_jobs", ["status"], unique=False)
    op.create_index(
        "ix_hunt_schedule_jobs_next_scheduled_run_at",
        "hunt_schedule_jobs",
        ["next_scheduled_run_at"],
        unique=False,
    )

    op.create_table(
        "hunt_readiness_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "schedule_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hunt_schedule_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "program_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scope_target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scope_targets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("workflow_template", sa.Text(), nullable=False),
        sa.Column("target_identifier", sa.Text(), nullable=False),
        sa.Column("trigger_source", sa.Text(), nullable=False, server_default="scheduler"),
        sa.Column("decision_status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "decided_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
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
        sa.CheckConstraint(
            "decision_status IN ('READY', 'BLOCKED_BY_SCOPE', 'BLOCKED_BY_PROGRAM_POLICY', "
            "'BLOCKED_BY_HEALTH', 'BLOCKED_BY_CONFIG', 'BLOCKED_BY_COOLDOWN', "
            "'BLOCKED_BY_DISABLED_TARGET', 'BLOCKED_BY_SAFETY_POLICY')",
            name="hunt_readiness_records_status_allowed",
        ),
        sa.CheckConstraint(
            "btrim(workflow_template) <> ''",
            name="hunt_readiness_records_template_not_empty",
        ),
        sa.CheckConstraint(
            "btrim(target_identifier) <> ''",
            name="hunt_readiness_records_target_not_empty",
        ),
    )
    op.create_index(
        "ix_hunt_readiness_records_schedule_id",
        "hunt_readiness_records",
        ["schedule_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_hunt_readiness_records_program_id",
        "hunt_readiness_records",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_hunt_readiness_records_scope_target_id",
        "hunt_readiness_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_hunt_readiness_records_decision_status",
        "hunt_readiness_records",
        ["decision_status"],
        unique=False,
    )
    op.create_index(
        "ix_hunt_readiness_records_decided_at",
        "hunt_readiness_records",
        ["decided_at"],
        unique=False,
    )

    op.create_table(
        "workflow_delta_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "schedule_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hunt_schedule_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "program_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scope_target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scope_targets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "previous_workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("delta_type", sa.Text(), nullable=False),
        sa.Column("delta_key", sa.Text(), nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("severity_hint", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "btrim(delta_type) <> ''",
            name="workflow_delta_records_delta_type_not_empty",
        ),
        sa.CheckConstraint(
            "change_type IN ('NEW', 'REMOVED', 'CHANGED', 'UNCHANGED', 'COVERAGE_GAP')",
            name="workflow_delta_records_change_type_allowed",
        ),
        sa.CheckConstraint(
            "btrim(delta_key) <> ''",
            name="workflow_delta_records_delta_key_not_empty",
        ),
    )
    op.create_index(
        "ix_workflow_delta_records_program_id",
        "workflow_delta_records",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_delta_records_scope_target_id",
        "workflow_delta_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_delta_records_workflow_run_id",
        "workflow_delta_records",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_delta_records_previous_workflow_run_id",
        "workflow_delta_records",
        ["previous_workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_delta_records_delta_type",
        "workflow_delta_records",
        ["delta_type"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_delta_records_change_type",
        "workflow_delta_records",
        ["change_type"],
        unique=False,
    )

    op.create_table(
        "analyst_queue_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "program_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scope_target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scope_targets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_findings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("workflow_template", sa.Text(), nullable=False),
        sa.Column("finding_type", sa.Text(), nullable=True),
        sa.Column("vulnerability_type", sa.Text(), nullable=False),
        sa.Column("affected_asset", sa.Text(), nullable=False),
        sa.Column("affected_endpoint", sa.Text(), nullable=True),
        sa.Column("parameter", sa.Text(), nullable=True),
        sa.Column("evidence_summary", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("severity_hint", sa.Text(), nullable=True),
        sa.Column("novelty_score", sa.Float(), nullable=True),
        sa.Column("reportability_score", sa.Float(), nullable=True),
        sa.Column("duplicate_risk_hint", sa.Text(), nullable=True),
        sa.Column("policy_fit_status", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="new"),
        sa.Column("artifact_ref", sa.Text(), nullable=True),
        sa.Column("assigned_to", sa.Text(), nullable=True),
        sa.Column("last_transition_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "workflow_finding_id",
            name="uq_analyst_queue_items_workflow_finding_id",
        ),
        sa.CheckConstraint(
            "status IN ('new', 'acknowledged', 'triaged', 'needs_manual_validation', "
            "'ready_for_report', 'dismissed', 'duplicate_suspected', 'submitted_externally')",
            name="analyst_queue_items_status_allowed",
        ),
        sa.CheckConstraint(
            "btrim(vulnerability_type) <> ''",
            name="analyst_queue_items_vulnerability_type_not_empty",
        ),
        sa.CheckConstraint(
            "btrim(affected_asset) <> ''",
            name="analyst_queue_items_affected_asset_not_empty",
        ),
    )
    op.create_index(
        "ix_analyst_queue_items_program_id",
        "analyst_queue_items",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_analyst_queue_items_scope_target_id",
        "analyst_queue_items",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_analyst_queue_items_workflow_run_id",
        "analyst_queue_items",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_analyst_queue_items_status",
        "analyst_queue_items",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_analyst_queue_items_reportability_score",
        "analyst_queue_items",
        ["reportability_score"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analyst_queue_items_reportability_score", table_name="analyst_queue_items")
    op.drop_index("ix_analyst_queue_items_status", table_name="analyst_queue_items")
    op.drop_index("ix_analyst_queue_items_workflow_run_id", table_name="analyst_queue_items")
    op.drop_index("ix_analyst_queue_items_scope_target_id", table_name="analyst_queue_items")
    op.drop_index("ix_analyst_queue_items_program_id", table_name="analyst_queue_items")
    op.drop_table("analyst_queue_items")

    op.drop_index("ix_workflow_delta_records_change_type", table_name="workflow_delta_records")
    op.drop_index("ix_workflow_delta_records_delta_type", table_name="workflow_delta_records")
    op.drop_index(
        "ix_workflow_delta_records_previous_workflow_run_id",
        table_name="workflow_delta_records",
    )
    op.drop_index("ix_workflow_delta_records_workflow_run_id", table_name="workflow_delta_records")
    op.drop_index("ix_workflow_delta_records_scope_target_id", table_name="workflow_delta_records")
    op.drop_index("ix_workflow_delta_records_program_id", table_name="workflow_delta_records")
    op.drop_table("workflow_delta_records")

    op.drop_index("ix_hunt_readiness_records_decided_at", table_name="hunt_readiness_records")
    op.drop_index(
        "ix_hunt_readiness_records_decision_status",
        table_name="hunt_readiness_records",
    )
    op.drop_index(
        "ix_hunt_readiness_records_scope_target_id",
        table_name="hunt_readiness_records",
    )
    op.drop_index("ix_hunt_readiness_records_program_id", table_name="hunt_readiness_records")
    op.drop_index("ix_hunt_readiness_records_schedule_id", table_name="hunt_readiness_records")
    op.drop_table("hunt_readiness_records")

    op.drop_index("ix_hunt_schedule_jobs_next_scheduled_run_at", table_name="hunt_schedule_jobs")
    op.drop_index("ix_hunt_schedule_jobs_status", table_name="hunt_schedule_jobs")
    op.drop_index("ix_hunt_schedule_jobs_scope_target_id", table_name="hunt_schedule_jobs")
    op.drop_index("ix_hunt_schedule_jobs_program_id", table_name="hunt_schedule_jobs")
    op.drop_table("hunt_schedule_jobs")

    op.drop_index("ix_scope_targets_next_scheduled_run_at", table_name="scope_targets")
    op.drop_index("ix_scope_targets_monitoring_enabled", table_name="scope_targets")
    op.drop_column("scope_targets", "next_scheduled_run_at")
    op.drop_column("scope_targets", "last_failure_at")
    op.drop_column("scope_targets", "last_success_at")
    op.drop_column("scope_targets", "last_checked_at")
    op.drop_column("scope_targets", "safe_mode_required")
    op.drop_column("scope_targets", "monitoring_notes")
    op.drop_column("scope_targets", "monitoring_source")
    op.drop_column("scope_targets", "monitoring_status")
    op.drop_column("scope_targets", "monitoring_priority_tier")
    op.drop_column("scope_targets", "monitoring_enabled")
