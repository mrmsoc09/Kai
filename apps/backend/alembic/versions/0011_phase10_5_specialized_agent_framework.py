"""phase 10.5 specialized agent framework persistence

Revision ID: 0011_phase10_5_specialized_agent_framework
Revises: 0010_phase10_retrospective_feedback_engine
Create Date: 2026-03-14 17:35:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0011_phase10_5_specialized_agent_framework"
down_revision = "0010_phase10_retrospective_feedback_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_registry_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("agent_role", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("allowed_tools_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("forbidden_tools_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("input_schema_reference", sa.Text(), nullable=False),
        sa.Column("output_schema_reference", sa.Text(), nullable=False),
        sa.Column("model_preference", sa.Text(), nullable=False),
        sa.Column("model_runtime", sa.Text(), nullable=False, server_default=sa.text("'self_hosted'")),
        sa.Column("confidence_threshold", sa.Float(), nullable=False, server_default=sa.text("0.65")),
        sa.Column("max_runtime_seconds", sa.Integer(), nullable=False, server_default=sa.text("120")),
        sa.Column("retry_policy_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("escalation_agent_id", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("safety_notes", sa.Text(), nullable=True),
        sa.Column("observability_tags_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("agent_id", name="uq_agent_registry_records_agent_id"),
        sa.CheckConstraint("btrim(agent_id) <> ''", name="agent_registry_records_agent_id_not_empty"),
        sa.CheckConstraint("btrim(agent_name) <> ''", name="agent_registry_records_agent_name_not_empty"),
        sa.CheckConstraint("btrim(agent_role) <> ''", name="agent_registry_records_agent_role_not_empty"),
        sa.CheckConstraint("btrim(category) <> ''", name="agent_registry_records_category_not_empty"),
        sa.CheckConstraint("btrim(model_runtime) <> ''", name="agent_registry_records_model_runtime_not_empty"),
        sa.CheckConstraint(
            "confidence_threshold >= 0.0 AND confidence_threshold <= 1.0",
            name="agent_registry_records_confidence_bounds",
        ),
        sa.CheckConstraint("max_runtime_seconds >= 1", name="agent_registry_records_runtime_positive"),
    )
    op.create_index("ix_agent_registry_records_enabled", "agent_registry_records", ["enabled"], unique=False)
    op.create_index(
        "ix_agent_registry_records_agent_role",
        "agent_registry_records",
        ["agent_role"],
        unique=False,
    )
    op.create_index("ix_agent_registry_records_category", "agent_registry_records", ["category"], unique=False)

    op.create_table(
        "agent_execution_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_registry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_registry_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column(
            "program_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scope_target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scope_targets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "analyst_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyst_case_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "analyst_queue_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("input_ref", sa.Text(), nullable=True),
        sa.Column("input_hash", sa.Text(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("model_used", sa.Text(), nullable=False),
        sa.Column("routing_policy", sa.Text(), nullable=False, server_default=sa.text("'self_hosted_first'")),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("execution_status", sa.Text(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("escalation_taken", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("escalation_agent_id", sa.Text(), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("log_path", sa.Text(), nullable=True),
        sa.Column("artifact_refs_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("btrim(agent_id) <> ''", name="agent_execution_records_agent_id_not_empty"),
        sa.CheckConstraint("btrim(model_used) <> ''", name="agent_execution_records_model_used_not_empty"),
        sa.CheckConstraint(
            "execution_status IN ('SUCCEEDED', 'FAILED', 'ESCALATED', 'DEFERRED', 'RETRIED')",
            name="agent_execution_records_status_allowed",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="agent_execution_records_confidence_bounds",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="agent_execution_records_duration_non_negative",
        ),
    )
    op.create_index("ix_agent_execution_records_program_id", "agent_execution_records", ["program_id"], unique=False)
    op.create_index(
        "ix_agent_execution_records_scope_target_id",
        "agent_execution_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_execution_records_workflow_run_id",
        "agent_execution_records",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index("ix_agent_execution_records_case_id", "agent_execution_records", ["analyst_case_id"], unique=False)
    op.create_index(
        "ix_agent_execution_records_queue_item_id",
        "agent_execution_records",
        ["analyst_queue_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_execution_records_registry_id",
        "agent_execution_records",
        ["agent_registry_id"],
        unique=False,
    )
    op.create_index("ix_agent_execution_records_agent_id", "agent_execution_records", ["agent_id"], unique=False)
    op.create_index("ix_agent_execution_records_status", "agent_execution_records", ["execution_status"], unique=False)
    op.create_index(
        "ix_agent_execution_records_started_at",
        "agent_execution_records",
        ["started_at"],
        unique=False,
    )

    op.create_table(
        "agent_evaluation_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_registry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_registry_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("benchmark_name", sa.Text(), nullable=False),
        sa.Column("model_used", sa.Text(), nullable=False),
        sa.Column("fixture_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("passed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_confidence", sa.Float(), nullable=True),
        sa.Column("avg_latency_ms", sa.Integer(), nullable=True),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("results_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("run_by", sa.Text(), nullable=True),
        sa.Column("run_reason", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("btrim(agent_id) <> ''", name="agent_evaluation_records_agent_id_not_empty"),
        sa.CheckConstraint("btrim(benchmark_name) <> ''", name="agent_evaluation_records_benchmark_not_empty"),
        sa.CheckConstraint("btrim(model_used) <> ''", name="agent_evaluation_records_model_used_not_empty"),
        sa.CheckConstraint(
            "status IN ('PASSED', 'FAILED', 'PARTIAL')",
            name="agent_evaluation_records_status_allowed",
        ),
        sa.CheckConstraint("fixture_count >= 0", name="agent_evaluation_records_fixture_non_negative"),
        sa.CheckConstraint("passed_count >= 0", name="agent_evaluation_records_passed_non_negative"),
        sa.CheckConstraint("failed_count >= 0", name="agent_evaluation_records_failed_non_negative"),
        sa.CheckConstraint(
            "avg_confidence IS NULL OR (avg_confidence >= 0.0 AND avg_confidence <= 1.0)",
            name="agent_evaluation_records_confidence_bounds",
        ),
        sa.CheckConstraint(
            "avg_latency_ms IS NULL OR avg_latency_ms >= 0",
            name="agent_evaluation_records_latency_non_negative",
        ),
        sa.CheckConstraint(
            "success_rate >= 0.0 AND success_rate <= 1.0",
            name="agent_evaluation_records_success_rate_bounds",
        ),
    )
    op.create_index("ix_agent_evaluation_records_agent_id", "agent_evaluation_records", ["agent_id"], unique=False)
    op.create_index("ix_agent_evaluation_records_status", "agent_evaluation_records", ["status"], unique=False)
    op.create_index(
        "ix_agent_evaluation_records_executed_at",
        "agent_evaluation_records",
        ["executed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_evaluation_records_executed_at", table_name="agent_evaluation_records")
    op.drop_index("ix_agent_evaluation_records_status", table_name="agent_evaluation_records")
    op.drop_index("ix_agent_evaluation_records_agent_id", table_name="agent_evaluation_records")
    op.drop_table("agent_evaluation_records")

    op.drop_index("ix_agent_execution_records_started_at", table_name="agent_execution_records")
    op.drop_index("ix_agent_execution_records_status", table_name="agent_execution_records")
    op.drop_index("ix_agent_execution_records_agent_id", table_name="agent_execution_records")
    op.drop_index("ix_agent_execution_records_registry_id", table_name="agent_execution_records")
    op.drop_index("ix_agent_execution_records_queue_item_id", table_name="agent_execution_records")
    op.drop_index("ix_agent_execution_records_case_id", table_name="agent_execution_records")
    op.drop_index("ix_agent_execution_records_workflow_run_id", table_name="agent_execution_records")
    op.drop_index("ix_agent_execution_records_scope_target_id", table_name="agent_execution_records")
    op.drop_index("ix_agent_execution_records_program_id", table_name="agent_execution_records")
    op.drop_table("agent_execution_records")

    op.drop_index("ix_agent_registry_records_category", table_name="agent_registry_records")
    op.drop_index("ix_agent_registry_records_agent_role", table_name="agent_registry_records")
    op.drop_index("ix_agent_registry_records_enabled", table_name="agent_registry_records")
    op.drop_table("agent_registry_records")
