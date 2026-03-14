"""phase 6 recon intelligence and inference persistence

Revision ID: 0007_phase6_recon_inference_engine
Revises: 0006_bug_bounty_continuous_hunting
Create Date: 2026-03-13 22:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0007_phase6_recon_inference_engine"
down_revision = "0006_bug_bounty_continuous_hunting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_intelligence_records",
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
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_record_id", sa.Text(), nullable=True),
        sa.Column("signal_type", sa.Text(), nullable=False),
        sa.Column("signal_key", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("severity_hint", sa.Text(), nullable=True),
        sa.Column("signal_fingerprint", sa.Text(), nullable=False),
        sa.Column("evidence_refs_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("correlation_refs_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "observed_at",
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
        sa.UniqueConstraint(
            "signal_fingerprint",
            name="uq_signal_intelligence_records_fingerprint",
        ),
        sa.CheckConstraint("btrim(source) <> ''", name="signal_intelligence_records_source_not_empty"),
        sa.CheckConstraint("btrim(signal_type) <> ''", name="signal_intelligence_records_type_not_empty"),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="signal_intelligence_records_confidence_bounds",
        ),
    )
    op.create_index(
        "ix_signal_intelligence_records_program_id",
        "signal_intelligence_records",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_signal_intelligence_records_scope_target_id",
        "signal_intelligence_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_signal_intelligence_records_workflow_run_id",
        "signal_intelligence_records",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_signal_intelligence_records_signal_type",
        "signal_intelligence_records",
        ["signal_type"],
        unique=False,
    )
    op.create_index(
        "ix_signal_intelligence_records_observed_at",
        "signal_intelligence_records",
        ["observed_at"],
        unique=False,
    )

    op.create_table(
        "opportunity_inference_records",
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
        sa.Column("recommended_workflow", sa.Text(), nullable=False),
        sa.Column("next_best_action", sa.Text(), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("target_priority_score", sa.Float(), nullable=False),
        sa.Column("reasoning_summary", sa.Text(), nullable=False),
        sa.Column("supporting_evidence_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "inferred_at",
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
            "opportunity_score >= 0.0 AND opportunity_score <= 100.0",
            name="opportunity_inference_records_opportunity_score_bounds",
        ),
        sa.CheckConstraint(
            "target_priority_score >= 0.0 AND target_priority_score <= 100.0",
            name="opportunity_inference_records_target_priority_score_bounds",
        ),
    )
    op.create_index(
        "ix_opportunity_inference_records_program_id",
        "opportunity_inference_records",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_opportunity_inference_records_scope_target_id",
        "opportunity_inference_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_opportunity_inference_records_workflow_run_id",
        "opportunity_inference_records",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_opportunity_inference_records_inferred_at",
        "opportunity_inference_records",
        ["inferred_at"],
        unique=False,
    )

    op.create_table(
        "swarm_reasoning_records",
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
            "opportunity_inference_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opportunity_inference_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("agent_role", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "reasoned_at",
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
        sa.CheckConstraint("btrim(agent_role) <> ''", name="swarm_reasoning_records_agent_role_not_empty"),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="swarm_reasoning_records_confidence_bounds",
        ),
    )
    op.create_index(
        "ix_swarm_reasoning_records_program_id",
        "swarm_reasoning_records",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_swarm_reasoning_records_scope_target_id",
        "swarm_reasoning_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_swarm_reasoning_records_workflow_run_id",
        "swarm_reasoning_records",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_swarm_reasoning_records_agent_role",
        "swarm_reasoning_records",
        ["agent_role"],
        unique=False,
    )
    op.create_index(
        "ix_swarm_reasoning_records_reasoned_at",
        "swarm_reasoning_records",
        ["reasoned_at"],
        unique=False,
    )

    op.create_table(
        "adaptive_schedule_action_records",
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
            "schedule_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hunt_schedule_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "opportunity_inference_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opportunity_inference_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("action_status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "executed_at",
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
            "action_status IN ('APPLIED', 'BLOCKED', 'SKIPPED')",
            name="adaptive_schedule_action_records_status_allowed",
        ),
        sa.CheckConstraint(
            "btrim(action_type) <> ''",
            name="adaptive_schedule_action_records_action_not_empty",
        ),
    )
    op.create_index(
        "ix_adaptive_schedule_action_records_program_id",
        "adaptive_schedule_action_records",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_adaptive_schedule_action_records_scope_target_id",
        "adaptive_schedule_action_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_adaptive_schedule_action_records_schedule_job_id",
        "adaptive_schedule_action_records",
        ["schedule_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_adaptive_schedule_action_records_action_status",
        "adaptive_schedule_action_records",
        ["action_status"],
        unique=False,
    )
    op.create_index(
        "ix_adaptive_schedule_action_records_executed_at",
        "adaptive_schedule_action_records",
        ["executed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_adaptive_schedule_action_records_executed_at", table_name="adaptive_schedule_action_records")
    op.drop_index("ix_adaptive_schedule_action_records_action_status", table_name="adaptive_schedule_action_records")
    op.drop_index("ix_adaptive_schedule_action_records_schedule_job_id", table_name="adaptive_schedule_action_records")
    op.drop_index("ix_adaptive_schedule_action_records_scope_target_id", table_name="adaptive_schedule_action_records")
    op.drop_index("ix_adaptive_schedule_action_records_program_id", table_name="adaptive_schedule_action_records")
    op.drop_table("adaptive_schedule_action_records")

    op.drop_index("ix_swarm_reasoning_records_reasoned_at", table_name="swarm_reasoning_records")
    op.drop_index("ix_swarm_reasoning_records_agent_role", table_name="swarm_reasoning_records")
    op.drop_index("ix_swarm_reasoning_records_workflow_run_id", table_name="swarm_reasoning_records")
    op.drop_index("ix_swarm_reasoning_records_scope_target_id", table_name="swarm_reasoning_records")
    op.drop_index("ix_swarm_reasoning_records_program_id", table_name="swarm_reasoning_records")
    op.drop_table("swarm_reasoning_records")

    op.drop_index("ix_opportunity_inference_records_inferred_at", table_name="opportunity_inference_records")
    op.drop_index("ix_opportunity_inference_records_workflow_run_id", table_name="opportunity_inference_records")
    op.drop_index("ix_opportunity_inference_records_scope_target_id", table_name="opportunity_inference_records")
    op.drop_index("ix_opportunity_inference_records_program_id", table_name="opportunity_inference_records")
    op.drop_table("opportunity_inference_records")

    op.drop_index("ix_signal_intelligence_records_observed_at", table_name="signal_intelligence_records")
    op.drop_index("ix_signal_intelligence_records_signal_type", table_name="signal_intelligence_records")
    op.drop_index("ix_signal_intelligence_records_workflow_run_id", table_name="signal_intelligence_records")
    op.drop_index("ix_signal_intelligence_records_scope_target_id", table_name="signal_intelligence_records")
    op.drop_index("ix_signal_intelligence_records_program_id", table_name="signal_intelligence_records")
    op.drop_table("signal_intelligence_records")
