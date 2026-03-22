"""campaign execution schema

Revision ID: 0003_campaign_execution_schema
Revises: 0002_add_reproducibility_score
Create Date: 2026-03-08 23:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0003_campaign_execution_schema"
down_revision = "0002_add_reproducibility_score"
branch_labels = None
depends_on = None


def upgrade() -> None:
    campaign_status_enum = postgresql.ENUM(
        "CREATED",
        "READY",
        "RUNNING",
        "PAUSED",
        "BLOCKED",
        "COMPLETED",
        "FAILED",
        "CANCELED",
        name="campaign_status_enum",
        create_type=False,
    )
    branch_status_enum = postgresql.ENUM(
        "PENDING",
        "READY",
        "RUNNING",
        "WAITING_APPROVAL",
        "BLOCKED",
        "COMPLETED",
        "FAILED",
        "CANCELED",
        name="branch_status_enum",
        create_type=False,
    )
    phase_job_status_enum = postgresql.ENUM(
        "CREATED",
        "QUEUED",
        "RUNNING",
        "WAITING_APPROVAL",
        "BLOCKED",
        "COMPLETED",
        "FAILED",
        "SKIPPED",
        "CANCELED",
        name="phase_job_status_enum",
        create_type=False,
    )
    approval_gate_status_enum = postgresql.ENUM(
        "PENDING",
        "APPROVED",
        "REJECTED",
        "DEFERRED",
        "EXPIRED",
        "CANCELED",
        name="approval_gate_status_enum",
        create_type=False,
    )
    tool_execution_status_enum = postgresql.ENUM(
        "CREATED",
        "QUEUED",
        "RUNNING",
        "WAITING_APPROVAL",
        "COMPLETED",
        "FAILED",
        "CANCELED",
        name="tool_execution_status_enum",
        create_type=False,
    )
    artifact_type_enum = postgresql.ENUM(
        "RAW_OUTPUT",
        "LOG",
        "HTTP_TRACE",
        "SCREENSHOT",
        "REQUEST_CAPTURE",
        "RESPONSE_CAPTURE",
        "EVIDENCE_BUNDLE",
        "REPORT_DRAFT",
        "OTHER",
        name="artifact_type_enum",
        create_type=False,
    )
    observation_type_enum = postgresql.ENUM(
        "DISCOVERY",
        "SIGNAL",
        "VULNERABILITY",
        "VALIDATION",
        "CONTEXT",
        "DECISION",
        "METRIC",
        "OTHER",
        name="observation_type_enum",
        create_type=False,
    )
    intention_source_enum = postgresql.ENUM(
        "USER",
        "AGENT",
        "SYSTEM",
        "POLICY_ENGINE",
        "OPERATOR",
        name="intention_source_enum",
        create_type=False,
    )
    intention_type_enum = postgresql.ENUM(
        "CAMPAIGN_START",
        "BRANCH_PLAN",
        "PHASE_EXECUTION",
        "TOOL_EXECUTION",
        "APPROVAL_REQUEST",
        "APPROVAL_DECISION",
        "NOTE",
        "REPORT_DRAFT",
        "POLICY_OVERRIDE",
        "SYSTEM_MAINTENANCE",
        name="intention_type_enum",
        create_type=False,
    )
    risk_policy_class_enum = postgresql.ENUM(
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
        "RESTRICTED",
        "OUT_OF_SCOPE",
        "POLICY_EXCEPTION",
        name="risk_policy_class_enum",
        create_type=False,
    )

    bind = op.get_bind()
    campaign_status_enum.create(bind, checkfirst=True)
    branch_status_enum.create(bind, checkfirst=True)
    phase_job_status_enum.create(bind, checkfirst=True)
    approval_gate_status_enum.create(bind, checkfirst=True)
    tool_execution_status_enum.create(bind, checkfirst=True)
    artifact_type_enum.create(bind, checkfirst=True)
    observation_type_enum.create(bind, checkfirst=True)
    intention_source_enum.create(bind, checkfirst=True)
    intention_type_enum.create(bind, checkfirst=True)
    risk_policy_class_enum.create(bind, checkfirst=True)

    op.create_table(
        "programs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_key", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=True),
        sa.Column("handle", sa.Text(), nullable=True),
        sa.Column("policy_url", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_programs_programs_name_not_empty"),
        sa.PrimaryKeyConstraint("id", name="pk_programs"),
        sa.UniqueConstraint("program_key", name="uq_programs_program_key"),
    )
    op.create_index("ix_programs_status", "programs", ["status"], unique=False)

    op.create_table(
        "scope_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("is_in_scope", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("policy_class", risk_policy_class_enum, nullable=True),
        sa.Column("normalization_key", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("btrim(target) <> ''", name="ck_scope_targets_scope_targets_target_not_empty"),
        sa.CheckConstraint(
            "btrim(target_type) <> ''",
            name="ck_scope_targets_scope_targets_target_type_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["programs.id"],
            name="fk_scope_targets_program_id_programs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scope_targets"),
        sa.UniqueConstraint(
            "program_id",
            "target",
            "target_type",
            name="uq_scope_targets_program_target_type",
        ),
    )
    op.create_index("ix_scope_targets_program_id", "scope_targets", ["program_id"], unique=False)
    op.create_index("ix_scope_targets_is_in_scope", "scope_targets", ["is_in_scope"], unique=False)

    op.create_table(
        "campaign_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("primary_scope_target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("campaign_name", sa.Text(), nullable=True),
        sa.Column("initiated_by", sa.Text(), nullable=False),
        sa.Column("declared_goal", sa.Text(), nullable=False),
        sa.Column("declared_reason", sa.Text(), nullable=True),
        sa.Column("policy_basis", sa.Text(), nullable=True),
        sa.Column("risk_class", risk_policy_class_enum, nullable=True),
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", campaign_status_enum, nullable=False, server_default="CREATED"),
        sa.Column("queued_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("paused_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("canceled_by", sa.Text(), nullable=True),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("run_config_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "btrim(initiated_by) <> ''",
            name="ck_campaign_runs_campaign_runs_initiated_by_not_empty",
        ),
        sa.CheckConstraint(
            "btrim(declared_goal) <> ''",
            name="ck_campaign_runs_campaign_runs_declared_goal_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["primary_scope_target_id"],
            ["scope_targets.id"],
            name="fk_campaign_runs_primary_scope_target_id_scope_targets",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["programs.id"],
            name="fk_campaign_runs_program_id_programs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_campaign_runs"),
        sa.UniqueConstraint("idempotency_key", name="uq_campaign_runs_idempotency_key"),
    )
    op.create_index("ix_campaign_runs_program_id", "campaign_runs", ["program_id"], unique=False)
    op.create_index("ix_campaign_runs_status", "campaign_runs", ["status"], unique=False)
    op.create_index(
        "ix_campaign_runs_primary_scope_target_id",
        "campaign_runs",
        ["primary_scope_target_id"],
        unique=False,
    )

    op.create_table(
        "execution_branches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("depends_on_branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_key", sa.Text(), nullable=False),
        sa.Column("branch_name", sa.Text(), nullable=True),
        sa.Column("status", branch_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("declared_goal", sa.Text(), nullable=True),
        sa.Column("policy_basis", sa.Text(), nullable=True),
        sa.Column("risk_class", risk_policy_class_enum, nullable=True),
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("queued_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("canceled_by", sa.Text(), nullable=True),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("branch_config_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "btrim(branch_key) <> ''",
            name="ck_execution_branches_execution_branches_branch_key_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign_runs.id"],
            name="fk_execution_branches_campaign_id_campaign_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_branch_id"],
            ["execution_branches.id"],
            name="fk_execution_branches_depends_on_branch_id_execution_branches",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_branch_id"],
            ["execution_branches.id"],
            name="fk_execution_branches_parent_branch_id_execution_branches",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_execution_branches"),
        sa.UniqueConstraint("campaign_id", "branch_key", name="uq_execution_branches_campaign_branch_key"),
    )
    op.create_index("ix_execution_branches_campaign_id", "execution_branches", ["campaign_id"], unique=False)
    op.create_index("ix_execution_branches_status", "execution_branches", ["status"], unique=False)
    op.create_index(
        "ix_execution_branches_parent_branch_id",
        "execution_branches",
        ["parent_branch_id"],
        unique=False,
    )
    op.create_index(
        "ix_execution_branches_depends_on_branch_id",
        "execution_branches",
        ["depends_on_branch_id"],
        unique=False,
    )

    op.create_table(
        "phase_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("depends_on_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phase_name", sa.Text(), nullable=False),
        sa.Column("phase_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", phase_job_status_enum, nullable=False, server_default="CREATED"),
        sa.Column("policy_class", risk_policy_class_enum, nullable=True),
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("queued_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("canceled_by", sa.Text(), nullable=True),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("worker_task_id", sa.Text(), nullable=True),
        sa.Column("queue_name", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_payload_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("output_summary_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("btrim(phase_name) <> ''", name="ck_phase_jobs_phase_jobs_phase_name_not_empty"),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["execution_branches.id"],
            name="fk_phase_jobs_branch_id_execution_branches",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign_runs.id"],
            name="fk_phase_jobs_campaign_id_campaign_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_job_id"],
            ["phase_jobs.id"],
            name="fk_phase_jobs_depends_on_job_id_phase_jobs",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_phase_jobs"),
    )
    op.create_index("ix_phase_jobs_campaign_id", "phase_jobs", ["campaign_id"], unique=False)
    op.create_index("ix_phase_jobs_branch_id", "phase_jobs", ["branch_id"], unique=False)
    op.create_index("ix_phase_jobs_status", "phase_jobs", ["status"], unique=False)
    op.create_index("ix_phase_jobs_depends_on_job_id", "phase_jobs", ["depends_on_job_id"], unique=False)

    op.create_table(
        "intention_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phase_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_intention_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", intention_source_enum, nullable=False),
        sa.Column("intention_type", intention_type_enum, nullable=False),
        sa.Column("initiated_by", sa.Text(), nullable=False),
        sa.Column("declared_goal", sa.Text(), nullable=False),
        sa.Column("declared_reason", sa.Text(), nullable=True),
        sa.Column("policy_basis", sa.Text(), nullable=True),
        sa.Column("risk_class", risk_policy_class_enum, nullable=True),
        sa.Column("risk_posture_changed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approval_reason", sa.Text(), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "btrim(initiated_by) <> ''",
            name="ck_intention_records_intention_initiated_by_not_empty",
        ),
        sa.CheckConstraint(
            "btrim(declared_goal) <> ''",
            name="ck_intention_records_intention_declared_goal_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["execution_branches.id"],
            name="fk_intention_records_branch_id_execution_branches",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign_runs.id"],
            name="fk_intention_records_campaign_id_campaign_runs",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_intention_id"],
            ["intention_records.id"],
            name="fk_intention_records_parent_intention_id_intention_records",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["phase_job_id"],
            ["phase_jobs.id"],
            name="fk_intention_records_phase_job_id_phase_jobs",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_intention_records"),
    )
    op.create_index("ix_intention_records_campaign_id", "intention_records", ["campaign_id"], unique=False)
    op.create_index("ix_intention_records_branch_id", "intention_records", ["branch_id"], unique=False)
    op.create_index("ix_intention_records_phase_job_id", "intention_records", ["phase_job_id"], unique=False)
    op.create_index("ix_intention_records_source", "intention_records", ["source"], unique=False)
    op.create_index(
        "ix_intention_records_intention_type",
        "intention_records",
        ["intention_type"],
        unique=False,
    )

    op.create_table(
        "approval_gates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phase_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intention_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", approval_gate_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("gate_reason", sa.Text(), nullable=False),
        sa.Column("policy_basis", sa.Text(), nullable=True),
        sa.Column("risk_class", risk_policy_class_enum, nullable=True),
        sa.Column("requested_by", sa.Text(), nullable=False),
        sa.Column("requested_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_by", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("canceled_by", sa.Text(), nullable=True),
        sa.Column("operator_notes", sa.Text(), nullable=True),
        sa.Column("decision_payload_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "btrim(gate_reason) <> ''",
            name="ck_approval_gates_approval_gates_reason_not_empty",
        ),
        sa.CheckConstraint(
            "btrim(requested_by) <> ''",
            name="ck_approval_gates_approval_gates_requested_by_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["execution_branches.id"],
            name="fk_approval_gates_branch_id_execution_branches",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign_runs.id"],
            name="fk_approval_gates_campaign_id_campaign_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["intention_id"],
            ["intention_records.id"],
            name="fk_approval_gates_intention_id_intention_records",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["phase_job_id"],
            ["phase_jobs.id"],
            name="fk_approval_gates_phase_job_id_phase_jobs",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_approval_gates"),
    )
    op.create_index("ix_approval_gates_campaign_id", "approval_gates", ["campaign_id"], unique=False)
    op.create_index("ix_approval_gates_branch_id", "approval_gates", ["branch_id"], unique=False)
    op.create_index("ix_approval_gates_phase_job_id", "approval_gates", ["phase_job_id"], unique=False)
    op.create_index("ix_approval_gates_status", "approval_gates", ["status"], unique=False)
    op.create_index("ix_approval_gates_requested_at", "approval_gates", ["requested_at"], unique=False)

    op.create_table(
        "tool_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phase_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approval_gate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intention_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("adapter_name", sa.Text(), nullable=True),
        sa.Column("status", tool_execution_status_enum, nullable=False, server_default="CREATED"),
        sa.Column("input_target", sa.Text(), nullable=True),
        sa.Column("input_payload_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("stdout_ref", sa.Text(), nullable=True),
        sa.Column("stderr_ref", sa.Text(), nullable=True),
        sa.Column("stdout_summary", sa.Text(), nullable=True),
        sa.Column("stderr_summary", sa.Text(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("policy_class", risk_policy_class_enum, nullable=True),
        sa.Column("queued_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("canceled_by", sa.Text(), nullable=True),
        sa.Column("worker_task_id", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "btrim(tool_name) <> ''",
            name="ck_tool_executions_tool_executions_tool_name_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["approval_gate_id"],
            ["approval_gates.id"],
            name="fk_tool_executions_approval_gate_id_approval_gates",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["execution_branches.id"],
            name="fk_tool_executions_branch_id_execution_branches",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign_runs.id"],
            name="fk_tool_executions_campaign_id_campaign_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["intention_id"],
            ["intention_records.id"],
            name="fk_tool_executions_intention_id_intention_records",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["phase_job_id"],
            ["phase_jobs.id"],
            name="fk_tool_executions_phase_job_id_phase_jobs",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tool_executions"),
    )
    op.create_index("ix_tool_executions_campaign_id", "tool_executions", ["campaign_id"], unique=False)
    op.create_index("ix_tool_executions_branch_id", "tool_executions", ["branch_id"], unique=False)
    op.create_index("ix_tool_executions_phase_job_id", "tool_executions", ["phase_job_id"], unique=False)
    op.create_index("ix_tool_executions_status", "tool_executions", ["status"], unique=False)
    op.create_index("ix_tool_executions_approval_gate_id", "tool_executions", ["approval_gate_id"], unique=False)
    op.create_index("ix_tool_executions_intention_id", "tool_executions", ["intention_id"], unique=False)

    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phase_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intention_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artifact_type", artifact_type_enum, nullable=False, server_default="RAW_OUTPUT"),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("policy_class", risk_policy_class_enum, nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("btrim(uri) <> ''", name="ck_artifacts_artifacts_uri_not_empty"),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["execution_branches.id"],
            name="fk_artifacts_branch_id_execution_branches",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign_runs.id"],
            name="fk_artifacts_campaign_id_campaign_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            name="fk_artifacts_finding_id_findings",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["intention_id"],
            ["intention_records.id"],
            name="fk_artifacts_intention_id_intention_records",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["phase_job_id"],
            ["phase_jobs.id"],
            name="fk_artifacts_phase_job_id_phase_jobs",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name="fk_artifacts_report_id_reports",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tool_execution_id"],
            ["tool_executions.id"],
            name="fk_artifacts_tool_execution_id_tool_executions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_artifacts"),
    )
    op.create_index("ix_artifacts_campaign_id", "artifacts", ["campaign_id"], unique=False)
    op.create_index("ix_artifacts_branch_id", "artifacts", ["branch_id"], unique=False)
    op.create_index("ix_artifacts_phase_job_id", "artifacts", ["phase_job_id"], unique=False)
    op.create_index("ix_artifacts_tool_execution_id", "artifacts", ["tool_execution_id"], unique=False)
    op.create_index("ix_artifacts_finding_id", "artifacts", ["finding_id"], unique=False)
    op.create_index("ix_artifacts_report_id", "artifacts", ["report_id"], unique=False)
    op.create_index("ix_artifacts_artifact_type", "artifacts", ["artifact_type"], unique=False)

    op.create_table(
        "observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phase_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intention_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("observation_type", observation_type_enum, nullable=False, server_default="SIGNAL"),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("policy_class", risk_policy_class_enum, nullable=True),
        sa.Column("normalized_ref", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["execution_branches.id"],
            name="fk_observations_branch_id_execution_branches",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign_runs.id"],
            name="fk_observations_campaign_id_campaign_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            name="fk_observations_finding_id_findings",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["intention_id"],
            ["intention_records.id"],
            name="fk_observations_intention_id_intention_records",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["phase_job_id"],
            ["phase_jobs.id"],
            name="fk_observations_phase_job_id_phase_jobs",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"],
            ["artifacts.id"],
            name="fk_observations_source_artifact_id_artifacts",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tool_execution_id"],
            ["tool_executions.id"],
            name="fk_observations_tool_execution_id_tool_executions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_observations"),
    )
    op.create_index("ix_observations_campaign_id", "observations", ["campaign_id"], unique=False)
    op.create_index("ix_observations_branch_id", "observations", ["branch_id"], unique=False)
    op.create_index("ix_observations_phase_job_id", "observations", ["phase_job_id"], unique=False)
    op.create_index(
        "ix_observations_tool_execution_id",
        "observations",
        ["tool_execution_id"],
        unique=False,
    )
    op.create_index(
        "ix_observations_source_artifact_id",
        "observations",
        ["source_artifact_id"],
        unique=False,
    )
    op.create_index(
        "ix_observations_observation_type",
        "observations",
        ["observation_type"],
        unique=False,
    )

    op.create_table(
        "scan_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phase_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intention_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("note_type", sa.Text(), nullable=False, server_default="GENERAL"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_system_generated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("btrim(author) <> ''", name="ck_scan_notes_scan_notes_author_not_empty"),
        sa.CheckConstraint("btrim(body) <> ''", name="ck_scan_notes_scan_notes_body_not_empty"),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["execution_branches.id"],
            name="fk_scan_notes_branch_id_execution_branches",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign_runs.id"],
            name="fk_scan_notes_campaign_id_campaign_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            name="fk_scan_notes_finding_id_findings",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["intention_id"],
            ["intention_records.id"],
            name="fk_scan_notes_intention_id_intention_records",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["phase_job_id"],
            ["phase_jobs.id"],
            name="fk_scan_notes_phase_job_id_phase_jobs",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name="fk_scan_notes_report_id_reports",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tool_execution_id"],
            ["tool_executions.id"],
            name="fk_scan_notes_tool_execution_id_tool_executions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scan_notes"),
    )
    op.create_index("ix_scan_notes_campaign_id", "scan_notes", ["campaign_id"], unique=False)
    op.create_index("ix_scan_notes_branch_id", "scan_notes", ["branch_id"], unique=False)
    op.create_index("ix_scan_notes_phase_job_id", "scan_notes", ["phase_job_id"], unique=False)
    op.create_index("ix_scan_notes_tool_execution_id", "scan_notes", ["tool_execution_id"], unique=False)
    op.create_index("ix_scan_notes_finding_id", "scan_notes", ["finding_id"], unique=False)

    op.create_table(
        "submission_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intention_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="DRAFT"),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content_uri", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("prepared_by", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("external_submission_id", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "btrim(status) <> ''",
            name="ck_submission_drafts_submission_drafts_status_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["execution_branches.id"],
            name="fk_submission_drafts_branch_id_execution_branches",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign_runs.id"],
            name="fk_submission_drafts_campaign_id_campaign_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            name="fk_submission_drafts_finding_id_findings",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["intention_id"],
            ["intention_records.id"],
            name="fk_submission_drafts_intention_id_intention_records",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name="fk_submission_drafts_report_id_reports",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_submission_drafts"),
    )
    op.create_index("ix_submission_drafts_campaign_id", "submission_drafts", ["campaign_id"], unique=False)
    op.create_index("ix_submission_drafts_branch_id", "submission_drafts", ["branch_id"], unique=False)
    op.create_index("ix_submission_drafts_finding_id", "submission_drafts", ["finding_id"], unique=False)
    op.create_index("ix_submission_drafts_report_id", "submission_drafts", ["report_id"], unique=False)
    op.create_index("ix_submission_drafts_status", "submission_drafts", ["status"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phase_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approval_gate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("intention_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("policy_basis", sa.Text(), nullable=True),
        sa.Column("policy_class", risk_policy_class_enum, nullable=True),
        sa.Column("risk_posture_changed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("happened_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_payload_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "btrim(event_type) <> ''",
            name="ck_audit_events_audit_events_event_type_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["approval_gate_id"],
            ["approval_gates.id"],
            name="fk_audit_events_approval_gate_id_approval_gates",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name="fk_audit_events_artifact_id_artifacts",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["execution_branches.id"],
            name="fk_audit_events_branch_id_execution_branches",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign_runs.id"],
            name="fk_audit_events_campaign_id_campaign_runs",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            name="fk_audit_events_finding_id_findings",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["intention_id"],
            ["intention_records.id"],
            name="fk_audit_events_intention_id_intention_records",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["observations.id"],
            name="fk_audit_events_observation_id_observations",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["phase_job_id"],
            ["phase_jobs.id"],
            name="fk_audit_events_phase_job_id_phase_jobs",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name="fk_audit_events_report_id_reports",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tool_execution_id"],
            ["tool_executions.id"],
            name="fk_audit_events_tool_execution_id_tool_executions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index("ix_audit_events_campaign_id", "audit_events", ["campaign_id"], unique=False)
    op.create_index("ix_audit_events_branch_id", "audit_events", ["branch_id"], unique=False)
    op.create_index("ix_audit_events_phase_job_id", "audit_events", ["phase_job_id"], unique=False)
    op.create_index("ix_audit_events_tool_execution_id", "audit_events", ["tool_execution_id"], unique=False)
    op.create_index("ix_audit_events_approval_gate_id", "audit_events", ["approval_gate_id"], unique=False)
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"], unique=False)
    op.create_index("ix_audit_events_happened_at", "audit_events", ["happened_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_events_happened_at", table_name="audit_events")
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_approval_gate_id", table_name="audit_events")
    op.drop_index("ix_audit_events_tool_execution_id", table_name="audit_events")
    op.drop_index("ix_audit_events_phase_job_id", table_name="audit_events")
    op.drop_index("ix_audit_events_branch_id", table_name="audit_events")
    op.drop_index("ix_audit_events_campaign_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_submission_drafts_status", table_name="submission_drafts")
    op.drop_index("ix_submission_drafts_report_id", table_name="submission_drafts")
    op.drop_index("ix_submission_drafts_finding_id", table_name="submission_drafts")
    op.drop_index("ix_submission_drafts_branch_id", table_name="submission_drafts")
    op.drop_index("ix_submission_drafts_campaign_id", table_name="submission_drafts")
    op.drop_table("submission_drafts")

    op.drop_index("ix_scan_notes_finding_id", table_name="scan_notes")
    op.drop_index("ix_scan_notes_tool_execution_id", table_name="scan_notes")
    op.drop_index("ix_scan_notes_phase_job_id", table_name="scan_notes")
    op.drop_index("ix_scan_notes_branch_id", table_name="scan_notes")
    op.drop_index("ix_scan_notes_campaign_id", table_name="scan_notes")
    op.drop_table("scan_notes")

    op.drop_index("ix_observations_observation_type", table_name="observations")
    op.drop_index("ix_observations_source_artifact_id", table_name="observations")
    op.drop_index("ix_observations_tool_execution_id", table_name="observations")
    op.drop_index("ix_observations_phase_job_id", table_name="observations")
    op.drop_index("ix_observations_branch_id", table_name="observations")
    op.drop_index("ix_observations_campaign_id", table_name="observations")
    op.drop_table("observations")

    op.drop_index("ix_artifacts_artifact_type", table_name="artifacts")
    op.drop_index("ix_artifacts_report_id", table_name="artifacts")
    op.drop_index("ix_artifacts_finding_id", table_name="artifacts")
    op.drop_index("ix_artifacts_tool_execution_id", table_name="artifacts")
    op.drop_index("ix_artifacts_phase_job_id", table_name="artifacts")
    op.drop_index("ix_artifacts_branch_id", table_name="artifacts")
    op.drop_index("ix_artifacts_campaign_id", table_name="artifacts")
    op.drop_table("artifacts")

    op.drop_index("ix_tool_executions_intention_id", table_name="tool_executions")
    op.drop_index("ix_tool_executions_approval_gate_id", table_name="tool_executions")
    op.drop_index("ix_tool_executions_status", table_name="tool_executions")
    op.drop_index("ix_tool_executions_phase_job_id", table_name="tool_executions")
    op.drop_index("ix_tool_executions_branch_id", table_name="tool_executions")
    op.drop_index("ix_tool_executions_campaign_id", table_name="tool_executions")
    op.drop_table("tool_executions")

    op.drop_index("ix_approval_gates_requested_at", table_name="approval_gates")
    op.drop_index("ix_approval_gates_status", table_name="approval_gates")
    op.drop_index("ix_approval_gates_phase_job_id", table_name="approval_gates")
    op.drop_index("ix_approval_gates_branch_id", table_name="approval_gates")
    op.drop_index("ix_approval_gates_campaign_id", table_name="approval_gates")
    op.drop_table("approval_gates")

    op.drop_index("ix_intention_records_intention_type", table_name="intention_records")
    op.drop_index("ix_intention_records_source", table_name="intention_records")
    op.drop_index("ix_intention_records_phase_job_id", table_name="intention_records")
    op.drop_index("ix_intention_records_branch_id", table_name="intention_records")
    op.drop_index("ix_intention_records_campaign_id", table_name="intention_records")
    op.drop_table("intention_records")

    op.drop_index("ix_phase_jobs_depends_on_job_id", table_name="phase_jobs")
    op.drop_index("ix_phase_jobs_status", table_name="phase_jobs")
    op.drop_index("ix_phase_jobs_branch_id", table_name="phase_jobs")
    op.drop_index("ix_phase_jobs_campaign_id", table_name="phase_jobs")
    op.drop_table("phase_jobs")

    op.drop_index("ix_execution_branches_depends_on_branch_id", table_name="execution_branches")
    op.drop_index("ix_execution_branches_parent_branch_id", table_name="execution_branches")
    op.drop_index("ix_execution_branches_status", table_name="execution_branches")
    op.drop_index("ix_execution_branches_campaign_id", table_name="execution_branches")
    op.drop_table("execution_branches")

    op.drop_index("ix_campaign_runs_primary_scope_target_id", table_name="campaign_runs")
    op.drop_index("ix_campaign_runs_status", table_name="campaign_runs")
    op.drop_index("ix_campaign_runs_program_id", table_name="campaign_runs")
    op.drop_table("campaign_runs")

    op.drop_index("ix_scope_targets_is_in_scope", table_name="scope_targets")
    op.drop_index("ix_scope_targets_program_id", table_name="scope_targets")
    op.drop_table("scope_targets")

    op.drop_index("ix_programs_status", table_name="programs")
    op.drop_table("programs")

    bind = op.get_bind()
    postgresql.ENUM(name="risk_policy_class_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="intention_type_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="intention_source_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="observation_type_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="artifact_type_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="tool_execution_status_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="approval_gate_status_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="phase_job_status_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="branch_status_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="campaign_status_enum").drop(bind, checkfirst=True)
