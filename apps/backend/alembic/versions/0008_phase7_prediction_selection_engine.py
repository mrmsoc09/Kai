"""phase 7 vulnerability prediction and opportunity selection persistence

Revision ID: 0008_phase7_prediction_selection_engine
Revises: 0007_phase6_recon_inference_engine
Create Date: 2026-03-13 23:55:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_phase7_prediction_selection_engine"
down_revision = "0007_phase6_recon_inference_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "target_yield_score_records",
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
            sa.ForeignKey("scope_targets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("signal_density_score", sa.Float(), nullable=False),
        sa.Column("novelty_score", sa.Float(), nullable=False),
        sa.Column("coverage_quality_score", sa.Float(), nullable=False),
        sa.Column("candidate_quality_score", sa.Float(), nullable=False),
        sa.Column("duplicate_penalty_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("yield_score", sa.Float(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "scored_at",
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
        sa.CheckConstraint(
            "signal_density_score >= 0.0 AND signal_density_score <= 1.0",
            name="target_yield_score_records_signal_density_bounds",
        ),
        sa.CheckConstraint(
            "novelty_score >= 0.0 AND novelty_score <= 1.0",
            name="target_yield_score_records_novelty_bounds",
        ),
        sa.CheckConstraint(
            "coverage_quality_score >= 0.0 AND coverage_quality_score <= 1.0",
            name="target_yield_score_records_coverage_bounds",
        ),
        sa.CheckConstraint(
            "candidate_quality_score >= 0.0 AND candidate_quality_score <= 1.0",
            name="target_yield_score_records_candidate_quality_bounds",
        ),
        sa.CheckConstraint(
            "duplicate_penalty_score >= 0.0 AND duplicate_penalty_score <= 1.0",
            name="target_yield_score_records_duplicate_penalty_bounds",
        ),
        sa.CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="target_yield_score_records_confidence_bounds",
        ),
        sa.CheckConstraint(
            "yield_score >= 0.0 AND yield_score <= 100.0",
            name="target_yield_score_records_yield_bounds",
        ),
    )
    op.create_index(
        "ix_target_yield_score_records_program_id",
        "target_yield_score_records",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_target_yield_score_records_scope_target_id",
        "target_yield_score_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_target_yield_score_records_workflow_run_id",
        "target_yield_score_records",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_target_yield_score_records_scored_at",
        "target_yield_score_records",
        ["scored_at"],
        unique=False,
    )

    op.create_table(
        "duplicate_risk_records",
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
            "analyst_queue_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("candidate_key", sa.Text(), nullable=False),
        sa.Column("duplicate_risk_score", sa.Float(), nullable=False),
        sa.Column("risk_band", sa.Text(), nullable=False),
        sa.Column("reasoning_summary", sa.Text(), nullable=False),
        sa.Column(
            "supporting_signal_ids_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "assessed_at",
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
        sa.CheckConstraint(
            "duplicate_risk_score >= 0.0 AND duplicate_risk_score <= 1.0",
            name="duplicate_risk_records_score_bounds",
        ),
        sa.CheckConstraint(
            "risk_band IN ('LOW', 'MEDIUM', 'HIGH')",
            name="duplicate_risk_records_band_allowed",
        ),
        sa.CheckConstraint(
            "btrim(candidate_key) <> ''",
            name="duplicate_risk_records_candidate_key_not_empty",
        ),
    )
    op.create_index(
        "ix_duplicate_risk_records_program_id",
        "duplicate_risk_records",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_duplicate_risk_records_scope_target_id",
        "duplicate_risk_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_duplicate_risk_records_workflow_run_id",
        "duplicate_risk_records",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_duplicate_risk_records_queue_item_id",
        "duplicate_risk_records",
        ["analyst_queue_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_duplicate_risk_records_assessed_at",
        "duplicate_risk_records",
        ["assessed_at"],
        unique=False,
    )

    op.create_table(
        "evidence_completeness_records",
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
            "analyst_queue_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("candidate_key", sa.Text(), nullable=False),
        sa.Column("evidence_completeness_score", sa.Float(), nullable=False),
        sa.Column("readiness_state", sa.Text(), nullable=False),
        sa.Column("missing_fields_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("reasoning_summary", sa.Text(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "assessed_at",
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
        sa.CheckConstraint(
            "evidence_completeness_score >= 0.0 AND evidence_completeness_score <= 1.0",
            name="evidence_completeness_records_score_bounds",
        ),
        sa.CheckConstraint(
            "readiness_state IN ('INSUFFICIENT', 'PARTIAL', 'READY_FOR_REVIEW', 'READY_FOR_REPORT')",
            name="evidence_completeness_records_state_allowed",
        ),
        sa.CheckConstraint(
            "btrim(candidate_key) <> ''",
            name="evidence_completeness_records_candidate_key_not_empty",
        ),
    )
    op.create_index(
        "ix_evidence_completeness_records_program_id",
        "evidence_completeness_records",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_evidence_completeness_records_scope_target_id",
        "evidence_completeness_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_evidence_completeness_records_workflow_run_id",
        "evidence_completeness_records",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_evidence_completeness_records_queue_item_id",
        "evidence_completeness_records",
        ["analyst_queue_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_evidence_completeness_records_assessed_at",
        "evidence_completeness_records",
        ["assessed_at"],
        unique=False,
    )

    op.create_table(
        "vulnerability_prediction_records",
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
            "analyst_queue_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("predicted_vulnerability_type", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("novelty_score", sa.Float(), nullable=False),
        sa.Column("duplicate_risk_score", sa.Float(), nullable=False),
        sa.Column("reportability_score", sa.Float(), nullable=False),
        sa.Column("evidence_completeness_score", sa.Float(), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("recommended_next_workflow", sa.Text(), nullable=False),
        sa.Column("recommended_follow_up_action", sa.Text(), nullable=False),
        sa.Column("reasoning_summary", sa.Text(), nullable=False),
        sa.Column(
            "supporting_signal_ids_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "predicted_at",
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
        sa.CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="vulnerability_prediction_records_confidence_bounds",
        ),
        sa.CheckConstraint(
            "novelty_score >= 0.0 AND novelty_score <= 1.0",
            name="vulnerability_prediction_records_novelty_bounds",
        ),
        sa.CheckConstraint(
            "duplicate_risk_score >= 0.0 AND duplicate_risk_score <= 1.0",
            name="vulnerability_prediction_records_duplicate_bounds",
        ),
        sa.CheckConstraint(
            "reportability_score >= 0.0 AND reportability_score <= 1.0",
            name="vulnerability_prediction_records_reportability_bounds",
        ),
        sa.CheckConstraint(
            "evidence_completeness_score >= 0.0 AND evidence_completeness_score <= 1.0",
            name="vulnerability_prediction_records_evidence_bounds",
        ),
        sa.CheckConstraint(
            "opportunity_score >= 0.0 AND opportunity_score <= 100.0",
            name="vulnerability_prediction_records_opportunity_bounds",
        ),
        sa.CheckConstraint(
            "btrim(predicted_vulnerability_type) <> ''",
            name="vulnerability_prediction_records_type_not_empty",
        ),
    )
    op.create_index(
        "ix_vulnerability_prediction_records_program_id",
        "vulnerability_prediction_records",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_vulnerability_prediction_records_scope_target_id",
        "vulnerability_prediction_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_vulnerability_prediction_records_workflow_run_id",
        "vulnerability_prediction_records",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_vulnerability_prediction_records_queue_item_id",
        "vulnerability_prediction_records",
        ["analyst_queue_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_vulnerability_prediction_records_created_at",
        "vulnerability_prediction_records",
        ["predicted_at"],
        unique=False,
    )

    op.create_table(
        "opportunity_selection_records",
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
            "analyst_queue_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_key", sa.Text(), nullable=False),
        sa.Column("selection_score", sa.Float(), nullable=False),
        sa.Column("priority_rank", sa.Integer(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("duplicate_risk_score", sa.Float(), nullable=True),
        sa.Column("evidence_completeness_score", sa.Float(), nullable=True),
        sa.Column("reasoning_summary", sa.Text(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "scored_at",
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
        sa.CheckConstraint(
            "subject_type IN ('PROGRAM', 'TARGET', 'CANDIDATE', 'CLUSTER')",
            name="opportunity_selection_records_subject_type_allowed",
        ),
        sa.CheckConstraint(
            "btrim(subject_key) <> ''",
            name="opportunity_selection_records_subject_key_not_empty",
        ),
        sa.CheckConstraint(
            "selection_score >= 0.0 AND selection_score <= 100.0",
            name="opportunity_selection_records_score_bounds",
        ),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="opportunity_selection_records_confidence_bounds",
        ),
        sa.CheckConstraint(
            "duplicate_risk_score IS NULL OR (duplicate_risk_score >= 0.0 AND duplicate_risk_score <= 1.0)",
            name="opportunity_selection_records_duplicate_bounds",
        ),
        sa.CheckConstraint(
            "evidence_completeness_score IS NULL OR (evidence_completeness_score >= 0.0 AND evidence_completeness_score <= 1.0)",
            name="opportunity_selection_records_evidence_bounds",
        ),
        sa.CheckConstraint(
            "priority_rank IS NULL OR priority_rank >= 1",
            name="opportunity_selection_records_rank_positive",
        ),
    )
    op.create_index(
        "ix_opportunity_selection_records_program_id",
        "opportunity_selection_records",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_opportunity_selection_records_scope_target_id",
        "opportunity_selection_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_opportunity_selection_records_workflow_run_id",
        "opportunity_selection_records",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_opportunity_selection_records_queue_item_id",
        "opportunity_selection_records",
        ["analyst_queue_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_opportunity_selection_records_subject",
        "opportunity_selection_records",
        ["subject_type", "subject_key"],
        unique=False,
    )
    op.create_index(
        "ix_opportunity_selection_records_scored_at",
        "opportunity_selection_records",
        ["scored_at"],
        unique=False,
    )

    op.create_table(
        "workflow_recommendation_records",
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
            "analyst_queue_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "prediction_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerability_prediction_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "selection_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opportunity_selection_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "target_yield_score_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("target_yield_score_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("recommended_workflow", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("action_priority", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("recommendation_status", sa.Text(), nullable=False, server_default=sa.text("'PROPOSED'")),
        sa.Column("reasoning_summary", sa.Text(), nullable=False),
        sa.Column(
            "supporting_record_ids_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "recommended_at",
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
        sa.CheckConstraint(
            "recommendation_status IN ('PROPOSED', 'APPLIED', 'BLOCKED', 'DEFERRED')",
            name="workflow_recommendation_records_status_allowed",
        ),
        sa.CheckConstraint(
            "action_priority >= 1",
            name="workflow_recommendation_records_priority_positive",
        ),
        sa.CheckConstraint(
            "btrim(recommended_workflow) <> ''",
            name="workflow_recommendation_records_workflow_not_empty",
        ),
        sa.CheckConstraint(
            "btrim(recommended_action) <> ''",
            name="workflow_recommendation_records_action_not_empty",
        ),
    )
    op.create_index(
        "ix_workflow_recommendation_records_program_id",
        "workflow_recommendation_records",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_recommendation_records_scope_target_id",
        "workflow_recommendation_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_recommendation_records_workflow_run_id",
        "workflow_recommendation_records",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_recommendation_records_queue_item_id",
        "workflow_recommendation_records",
        ["analyst_queue_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_recommendation_records_prediction_id",
        "workflow_recommendation_records",
        ["prediction_record_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_recommendation_records_selection_id",
        "workflow_recommendation_records",
        ["selection_record_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_recommendation_records_status",
        "workflow_recommendation_records",
        ["recommendation_status"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_recommendation_records_recommended_at",
        "workflow_recommendation_records",
        ["recommended_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_recommendation_records_recommended_at",
        table_name="workflow_recommendation_records",
    )
    op.drop_index(
        "ix_workflow_recommendation_records_status",
        table_name="workflow_recommendation_records",
    )
    op.drop_index(
        "ix_workflow_recommendation_records_selection_id",
        table_name="workflow_recommendation_records",
    )
    op.drop_index(
        "ix_workflow_recommendation_records_prediction_id",
        table_name="workflow_recommendation_records",
    )
    op.drop_index(
        "ix_workflow_recommendation_records_queue_item_id",
        table_name="workflow_recommendation_records",
    )
    op.drop_index(
        "ix_workflow_recommendation_records_workflow_run_id",
        table_name="workflow_recommendation_records",
    )
    op.drop_index(
        "ix_workflow_recommendation_records_scope_target_id",
        table_name="workflow_recommendation_records",
    )
    op.drop_index(
        "ix_workflow_recommendation_records_program_id",
        table_name="workflow_recommendation_records",
    )
    op.drop_table("workflow_recommendation_records")

    op.drop_index(
        "ix_opportunity_selection_records_scored_at",
        table_name="opportunity_selection_records",
    )
    op.drop_index(
        "ix_opportunity_selection_records_subject",
        table_name="opportunity_selection_records",
    )
    op.drop_index(
        "ix_opportunity_selection_records_queue_item_id",
        table_name="opportunity_selection_records",
    )
    op.drop_index(
        "ix_opportunity_selection_records_workflow_run_id",
        table_name="opportunity_selection_records",
    )
    op.drop_index(
        "ix_opportunity_selection_records_scope_target_id",
        table_name="opportunity_selection_records",
    )
    op.drop_index(
        "ix_opportunity_selection_records_program_id",
        table_name="opportunity_selection_records",
    )
    op.drop_table("opportunity_selection_records")

    op.drop_index(
        "ix_vulnerability_prediction_records_created_at",
        table_name="vulnerability_prediction_records",
    )
    op.drop_index(
        "ix_vulnerability_prediction_records_queue_item_id",
        table_name="vulnerability_prediction_records",
    )
    op.drop_index(
        "ix_vulnerability_prediction_records_workflow_run_id",
        table_name="vulnerability_prediction_records",
    )
    op.drop_index(
        "ix_vulnerability_prediction_records_scope_target_id",
        table_name="vulnerability_prediction_records",
    )
    op.drop_index(
        "ix_vulnerability_prediction_records_program_id",
        table_name="vulnerability_prediction_records",
    )
    op.drop_table("vulnerability_prediction_records")

    op.drop_index(
        "ix_evidence_completeness_records_assessed_at",
        table_name="evidence_completeness_records",
    )
    op.drop_index(
        "ix_evidence_completeness_records_queue_item_id",
        table_name="evidence_completeness_records",
    )
    op.drop_index(
        "ix_evidence_completeness_records_workflow_run_id",
        table_name="evidence_completeness_records",
    )
    op.drop_index(
        "ix_evidence_completeness_records_scope_target_id",
        table_name="evidence_completeness_records",
    )
    op.drop_index(
        "ix_evidence_completeness_records_program_id",
        table_name="evidence_completeness_records",
    )
    op.drop_table("evidence_completeness_records")

    op.drop_index(
        "ix_duplicate_risk_records_assessed_at",
        table_name="duplicate_risk_records",
    )
    op.drop_index(
        "ix_duplicate_risk_records_queue_item_id",
        table_name="duplicate_risk_records",
    )
    op.drop_index(
        "ix_duplicate_risk_records_workflow_run_id",
        table_name="duplicate_risk_records",
    )
    op.drop_index(
        "ix_duplicate_risk_records_scope_target_id",
        table_name="duplicate_risk_records",
    )
    op.drop_index(
        "ix_duplicate_risk_records_program_id",
        table_name="duplicate_risk_records",
    )
    op.drop_table("duplicate_risk_records")

    op.drop_index(
        "ix_target_yield_score_records_scored_at",
        table_name="target_yield_score_records",
    )
    op.drop_index(
        "ix_target_yield_score_records_workflow_run_id",
        table_name="target_yield_score_records",
    )
    op.drop_index(
        "ix_target_yield_score_records_scope_target_id",
        table_name="target_yield_score_records",
    )
    op.drop_index(
        "ix_target_yield_score_records_program_id",
        table_name="target_yield_score_records",
    )
    op.drop_table("target_yield_score_records")
