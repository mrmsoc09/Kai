"""phase 10 retrospective and feedback learning persistence

Revision ID: 0010_phase10_retrospective_feedback_engine
Revises: 0009_phase9_alerting_case_management
Create Date: 2026-03-14 13:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010_phase10_retrospective_feedback_engine"
down_revision = "0009_phase9_alerting_case_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback_signal_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("programs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope_target_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scope_targets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("analyst_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analyst_case_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("notification_alert_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("analyst_queue_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analyst_queue_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recommendation_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_recommendation_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_entity_type", sa.Text(), nullable=False),
        sa.Column("source_entity_id", sa.Text(), nullable=False),
        sa.Column("outcome_classification", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column("signal_fingerprint", sa.Text(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("signal_fingerprint", name="uq_feedback_signal_records_fingerprint"),
        sa.CheckConstraint("btrim(source_entity_type) <> ''", name="feedback_signal_records_source_type_not_empty"),
        sa.CheckConstraint("btrim(source_entity_id) <> ''", name="feedback_signal_records_source_id_not_empty"),
        sa.CheckConstraint("btrim(outcome_classification) <> ''", name="feedback_signal_records_outcome_not_empty"),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="feedback_signal_records_confidence_bounds",
        ),
    )
    op.create_index("ix_feedback_signal_records_program_id", "feedback_signal_records", ["program_id"], unique=False)
    op.create_index("ix_feedback_signal_records_scope_target_id", "feedback_signal_records", ["scope_target_id"], unique=False)
    op.create_index("ix_feedback_signal_records_workflow_run_id", "feedback_signal_records", ["workflow_run_id"], unique=False)
    op.create_index("ix_feedback_signal_records_case_id", "feedback_signal_records", ["analyst_case_id"], unique=False)
    op.create_index("ix_feedback_signal_records_alert_id", "feedback_signal_records", ["alert_id"], unique=False)
    op.create_index("ix_feedback_signal_records_recommendation_id", "feedback_signal_records", ["recommendation_record_id"], unique=False)
    op.create_index("ix_feedback_signal_records_outcome_classification", "feedback_signal_records", ["outcome_classification"], unique=False)
    op.create_index("ix_feedback_signal_records_observed_at", "feedback_signal_records", ["observed_at"], unique=False)

    op.create_table(
        "decision_outcome_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("programs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope_target_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scope_targets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("analyst_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analyst_case_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("notification_alert_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recommendation_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_recommendation_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decision_type", sa.Text(), nullable=False),
        sa.Column("decision_status", sa.Text(), nullable=False),
        sa.Column("outcome_classification", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.Text(), nullable=True),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column("outcome_fingerprint", sa.Text(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("outcome_fingerprint", name="uq_decision_outcome_records_fingerprint"),
        sa.CheckConstraint("decision_type IN ('CASE', 'ALERT', 'RECOMMENDATION')", name="decision_outcome_records_type_allowed"),
        sa.CheckConstraint("btrim(decision_status) <> ''", name="decision_outcome_records_status_not_empty"),
        sa.CheckConstraint("btrim(outcome_classification) <> ''", name="decision_outcome_records_outcome_not_empty"),
    )
    op.create_index("ix_decision_outcome_records_program_id", "decision_outcome_records", ["program_id"], unique=False)
    op.create_index("ix_decision_outcome_records_scope_target_id", "decision_outcome_records", ["scope_target_id"], unique=False)
    op.create_index("ix_decision_outcome_records_workflow_run_id", "decision_outcome_records", ["workflow_run_id"], unique=False)
    op.create_index("ix_decision_outcome_records_case_id", "decision_outcome_records", ["analyst_case_id"], unique=False)
    op.create_index("ix_decision_outcome_records_alert_id", "decision_outcome_records", ["alert_id"], unique=False)
    op.create_index("ix_decision_outcome_records_recommendation_id", "decision_outcome_records", ["recommendation_record_id"], unique=False)
    op.create_index("ix_decision_outcome_records_decision_type", "decision_outcome_records", ["decision_type"], unique=False)
    op.create_index("ix_decision_outcome_records_decided_at", "decision_outcome_records", ["decided_at"], unique=False)

    op.create_table(
        "workflow_performance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("programs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_template", sa.Text(), nullable=False),
        sa.Column("window_start", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("window_end", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("signals_generated", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("candidates_produced", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cases_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reportable_outcomes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("duplicate_outcomes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("dismissed_outcomes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("workflow_signal_value", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("workflow_reportability_rate", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("workflow_noise_rate", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("computed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("btrim(workflow_template) <> ''", name="workflow_performance_records_template_not_empty"),
        sa.CheckConstraint("signals_generated >= 0", name="workflow_performance_records_signals_non_negative"),
        sa.CheckConstraint("candidates_produced >= 0", name="workflow_performance_records_candidates_non_negative"),
        sa.CheckConstraint("cases_created >= 0", name="workflow_performance_records_cases_non_negative"),
        sa.CheckConstraint("reportable_outcomes >= 0", name="workflow_performance_records_reportable_non_negative"),
        sa.CheckConstraint("duplicate_outcomes >= 0", name="workflow_performance_records_duplicate_non_negative"),
        sa.CheckConstraint("dismissed_outcomes >= 0", name="workflow_performance_records_dismissed_non_negative"),
        sa.CheckConstraint(
            "workflow_signal_value >= 0.0 AND workflow_signal_value <= 100.0",
            name="workflow_performance_records_signal_value_bounds",
        ),
        sa.CheckConstraint(
            "workflow_reportability_rate >= 0.0 AND workflow_reportability_rate <= 1.0",
            name="workflow_performance_records_reportability_bounds",
        ),
        sa.CheckConstraint(
            "workflow_noise_rate >= 0.0 AND workflow_noise_rate <= 1.0",
            name="workflow_performance_records_noise_bounds",
        ),
    )
    op.create_index("ix_workflow_performance_records_program_id", "workflow_performance_records", ["program_id"], unique=False)
    op.create_index("ix_workflow_performance_records_template", "workflow_performance_records", ["workflow_template"], unique=False)
    op.create_index("ix_workflow_performance_records_window_end", "workflow_performance_records", ["window_end"], unique=False)
    op.create_index("ix_workflow_performance_records_computed_at", "workflow_performance_records", ["computed_at"], unique=False)

    op.create_table(
        "target_performance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("programs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope_target_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scope_targets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("window_start", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("window_end", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("signal_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("case_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reportable_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("dismissed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("target_signal_rate", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("target_duplicate_rate", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("target_reportability_rate", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("target_yield_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("computed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("signal_count >= 0", name="target_performance_records_signal_count_non_negative"),
        sa.CheckConstraint("candidate_count >= 0", name="target_performance_records_candidate_count_non_negative"),
        sa.CheckConstraint("case_count >= 0", name="target_performance_records_case_count_non_negative"),
        sa.CheckConstraint("reportable_count >= 0", name="target_performance_records_reportable_count_non_negative"),
        sa.CheckConstraint("duplicate_count >= 0", name="target_performance_records_duplicate_count_non_negative"),
        sa.CheckConstraint("dismissed_count >= 0", name="target_performance_records_dismissed_count_non_negative"),
        sa.CheckConstraint(
            "target_signal_rate >= 0.0 AND target_signal_rate <= 1.0",
            name="target_performance_records_signal_rate_bounds",
        ),
        sa.CheckConstraint(
            "target_duplicate_rate >= 0.0 AND target_duplicate_rate <= 1.0",
            name="target_performance_records_duplicate_rate_bounds",
        ),
        sa.CheckConstraint(
            "target_reportability_rate >= 0.0 AND target_reportability_rate <= 1.0",
            name="target_performance_records_reportability_rate_bounds",
        ),
        sa.CheckConstraint(
            "target_yield_score >= 0.0 AND target_yield_score <= 100.0",
            name="target_performance_records_yield_score_bounds",
        ),
    )
    op.create_index("ix_target_performance_records_program_id", "target_performance_records", ["program_id"], unique=False)
    op.create_index("ix_target_performance_records_scope_target_id", "target_performance_records", ["scope_target_id"], unique=False)
    op.create_index("ix_target_performance_records_window_end", "target_performance_records", ["window_end"], unique=False)
    op.create_index("ix_target_performance_records_computed_at", "target_performance_records", ["computed_at"], unique=False)

    op.create_table(
        "recommendation_outcome_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("programs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "recommendation_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_recommendation_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope_target_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scope_targets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("analyst_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analyst_case_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("outcome_status", sa.Text(), nullable=False),
        sa.Column("success_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column("outcome_fingerprint", sa.Text(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("outcome_fingerprint", name="uq_recommendation_outcome_records_fingerprint"),
        sa.CheckConstraint(
            "outcome_status IN ('SUCCEEDED', 'USED', 'ABANDONED', 'BLOCKED', 'FAILED')",
            name="recommendation_outcome_records_status_allowed",
        ),
        sa.CheckConstraint(
            "success_score >= 0.0 AND success_score <= 1.0",
            name="recommendation_outcome_records_success_bounds",
        ),
    )
    op.create_index("ix_recommendation_outcome_records_program_id", "recommendation_outcome_records", ["program_id"], unique=False)
    op.create_index("ix_recommendation_outcome_records_recommendation_id", "recommendation_outcome_records", ["recommendation_record_id"], unique=False)
    op.create_index("ix_recommendation_outcome_records_scope_target_id", "recommendation_outcome_records", ["scope_target_id"], unique=False)
    op.create_index("ix_recommendation_outcome_records_outcome_status", "recommendation_outcome_records", ["outcome_status"], unique=False)
    op.create_index("ix_recommendation_outcome_records_decided_at", "recommendation_outcome_records", ["decided_at"], unique=False)

    op.create_table(
        "alert_outcome_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("programs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "alert_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notification_alert_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope_target_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scope_targets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("analyst_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analyst_case_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("outcome_status", sa.Text(), nullable=False),
        sa.Column("acknowledgement_latency_seconds", sa.Integer(), nullable=True),
        sa.Column("led_to_case", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("led_to_reportable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column("outcome_fingerprint", sa.Text(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("evaluated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("outcome_fingerprint", name="uq_alert_outcome_records_fingerprint"),
        sa.CheckConstraint(
            "outcome_status IN ('ESCALATED', 'ACKNOWLEDGED', 'IGNORED', 'RESOLVED_ACTIONABLE', 'RESOLVED_NOISE', 'OPEN_TRACKING')",
            name="alert_outcome_records_status_allowed",
        ),
        sa.CheckConstraint(
            "acknowledgement_latency_seconds IS NULL OR acknowledgement_latency_seconds >= 0",
            name="alert_outcome_records_latency_non_negative",
        ),
    )
    op.create_index("ix_alert_outcome_records_program_id", "alert_outcome_records", ["program_id"], unique=False)
    op.create_index("ix_alert_outcome_records_alert_id", "alert_outcome_records", ["alert_id"], unique=False)
    op.create_index("ix_alert_outcome_records_scope_target_id", "alert_outcome_records", ["scope_target_id"], unique=False)
    op.create_index("ix_alert_outcome_records_outcome_status", "alert_outcome_records", ["outcome_status"], unique=False)
    op.create_index("ix_alert_outcome_records_evaluated_at", "alert_outcome_records", ["evaluated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_alert_outcome_records_evaluated_at", table_name="alert_outcome_records")
    op.drop_index("ix_alert_outcome_records_outcome_status", table_name="alert_outcome_records")
    op.drop_index("ix_alert_outcome_records_scope_target_id", table_name="alert_outcome_records")
    op.drop_index("ix_alert_outcome_records_alert_id", table_name="alert_outcome_records")
    op.drop_index("ix_alert_outcome_records_program_id", table_name="alert_outcome_records")
    op.drop_table("alert_outcome_records")

    op.drop_index("ix_recommendation_outcome_records_decided_at", table_name="recommendation_outcome_records")
    op.drop_index("ix_recommendation_outcome_records_outcome_status", table_name="recommendation_outcome_records")
    op.drop_index("ix_recommendation_outcome_records_scope_target_id", table_name="recommendation_outcome_records")
    op.drop_index("ix_recommendation_outcome_records_recommendation_id", table_name="recommendation_outcome_records")
    op.drop_index("ix_recommendation_outcome_records_program_id", table_name="recommendation_outcome_records")
    op.drop_table("recommendation_outcome_records")

    op.drop_index("ix_target_performance_records_computed_at", table_name="target_performance_records")
    op.drop_index("ix_target_performance_records_window_end", table_name="target_performance_records")
    op.drop_index("ix_target_performance_records_scope_target_id", table_name="target_performance_records")
    op.drop_index("ix_target_performance_records_program_id", table_name="target_performance_records")
    op.drop_table("target_performance_records")

    op.drop_index("ix_workflow_performance_records_computed_at", table_name="workflow_performance_records")
    op.drop_index("ix_workflow_performance_records_window_end", table_name="workflow_performance_records")
    op.drop_index("ix_workflow_performance_records_template", table_name="workflow_performance_records")
    op.drop_index("ix_workflow_performance_records_program_id", table_name="workflow_performance_records")
    op.drop_table("workflow_performance_records")

    op.drop_index("ix_decision_outcome_records_decided_at", table_name="decision_outcome_records")
    op.drop_index("ix_decision_outcome_records_decision_type", table_name="decision_outcome_records")
    op.drop_index("ix_decision_outcome_records_recommendation_id", table_name="decision_outcome_records")
    op.drop_index("ix_decision_outcome_records_alert_id", table_name="decision_outcome_records")
    op.drop_index("ix_decision_outcome_records_case_id", table_name="decision_outcome_records")
    op.drop_index("ix_decision_outcome_records_workflow_run_id", table_name="decision_outcome_records")
    op.drop_index("ix_decision_outcome_records_scope_target_id", table_name="decision_outcome_records")
    op.drop_index("ix_decision_outcome_records_program_id", table_name="decision_outcome_records")
    op.drop_table("decision_outcome_records")

    op.drop_index("ix_feedback_signal_records_observed_at", table_name="feedback_signal_records")
    op.drop_index("ix_feedback_signal_records_outcome_classification", table_name="feedback_signal_records")
    op.drop_index("ix_feedback_signal_records_recommendation_id", table_name="feedback_signal_records")
    op.drop_index("ix_feedback_signal_records_alert_id", table_name="feedback_signal_records")
    op.drop_index("ix_feedback_signal_records_case_id", table_name="feedback_signal_records")
    op.drop_index("ix_feedback_signal_records_workflow_run_id", table_name="feedback_signal_records")
    op.drop_index("ix_feedback_signal_records_scope_target_id", table_name="feedback_signal_records")
    op.drop_index("ix_feedback_signal_records_program_id", table_name="feedback_signal_records")
    op.drop_table("feedback_signal_records")
