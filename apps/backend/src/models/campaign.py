from __future__ import annotations

import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base
from .enums import (
    ApprovalGateStatusEnum,
    ArtifactTypeEnum,
    BranchStatusEnum,
    CampaignStatusEnum,
    ObservationTypeEnum,
    PhaseJobStatusEnum,
    RiskPolicyClassEnum,
    ToolExecutionStatusEnum,
)
from .mixins import TimestampMixin, UTCAwareDatetime
from .types import EncryptedText


class Program(Base, TimestampMixin):
    __tablename__ = "programs"
    __table_args__ = (
        UniqueConstraint("program_key", name="uq_programs_program_key"),
        CheckConstraint("btrim(name) <> ''", name="programs_name_not_empty"),
        Index("ix_programs_status", "status"),
        Index("ix_programs_program_key", "program_key"),
        Index("ix_programs_created_by", "created_by"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_key = Column(Text, nullable=True)
    name = Column(Text, nullable=False)
    platform = Column(Text, nullable=True)
    handle = Column(Text, nullable=True)
    policy_url = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default="ACTIVE")
    created_by = Column(Text, nullable=True)
    config_json = Column(JSON, nullable=False, server_default="{}")

    scope_targets = relationship("ScopeTarget", back_populates="program")
    campaign_runs = relationship("CampaignRun", back_populates="program")
    findings = relationship("ScanFinding", back_populates="program", foreign_keys="ScanFinding.program_id")
    scans = relationship("ScanExecution", back_populates="program", foreign_keys="ScanExecution.program_id")


class ScopeTarget(Base, TimestampMixin):
    __tablename__ = "scope_targets"
    __table_args__ = (
        UniqueConstraint(
            "program_id",
            "target",
            "target_type",
            name="uq_scope_targets_program_target_type",
        ),
        CheckConstraint("btrim(target) <> ''", name="scope_targets_target_not_empty"),
        CheckConstraint("btrim(target_type) <> ''", name="scope_targets_target_type_not_empty"),
        Index("ix_scope_targets_program_id", "program_id"),
        Index("ix_scope_targets_is_in_scope", "is_in_scope"),
        Index("ix_scope_targets_monitoring_enabled", "monitoring_enabled"),
        Index("ix_scope_targets_next_scheduled_run_at", "next_scheduled_run_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(UUID(as_uuid=True), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False)
    target = Column(Text, nullable=False)
    target_type = Column(Text, nullable=False)
    is_in_scope = Column(Boolean, nullable=False, default=True, server_default="true")
    policy_class = Column(
        SAEnum(
            RiskPolicyClassEnum,
            name="risk_policy_class_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=True,
    )
    normalization_key = Column(Text, nullable=True)
    details_json = Column(JSON, nullable=False, server_default="{}")
    monitoring_enabled = Column(Boolean, nullable=False, server_default="true")
    monitoring_priority_tier = Column(Integer, nullable=False, server_default="3")
    monitoring_status = Column(Text, nullable=False, server_default="ACTIVE")
    monitoring_source = Column(Text, nullable=True)
    monitoring_notes = Column(Text, nullable=True)
    safe_mode_required = Column(Boolean, nullable=False, server_default="true")
    last_checked_at = Column(UTCAwareDatetime, nullable=True)
    last_success_at = Column(UTCAwareDatetime, nullable=True)
    last_failure_at = Column(UTCAwareDatetime, nullable=True)
    next_scheduled_run_at = Column(UTCAwareDatetime, nullable=True)

    program = relationship("Program", back_populates="scope_targets")
    campaign_runs = relationship("CampaignRun", back_populates="primary_scope_target")


class CampaignRun(Base, TimestampMixin):
    __tablename__ = "campaign_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_campaign_runs_idempotency_key"),
        CheckConstraint("btrim(initiated_by) <> ''", name="campaign_runs_initiated_by_not_empty"),
        CheckConstraint("btrim(declared_goal) <> ''", name="campaign_runs_declared_goal_not_empty"),
        Index("ix_campaign_runs_program_id", "program_id"),
        Index("ix_campaign_runs_status", "status"),
        Index("ix_campaign_runs_primary_scope_target_id", "primary_scope_target_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(UUID(as_uuid=True), ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False)
    primary_scope_target_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scope_targets.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key = Column(UUID(as_uuid=True), nullable=True)
    campaign_name = Column(Text, nullable=True)
    initiated_by = Column(Text, nullable=False)
    declared_goal = Column(Text, nullable=False)
    declared_reason = Column(Text, nullable=True)
    policy_basis = Column(Text, nullable=True)
    risk_class = Column(
        SAEnum(
            RiskPolicyClassEnum,
            name="risk_policy_class_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=True,
    )
    approval_required = Column(Boolean, nullable=False, default=False, server_default="false")
    status = Column(
        SAEnum(
            CampaignStatusEnum,
            name="campaign_status_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        server_default=CampaignStatusEnum.CREATED.value,
    )
    queued_at = Column(UTCAwareDatetime, nullable=True)
    started_at = Column(UTCAwareDatetime, nullable=True)
    paused_at = Column(UTCAwareDatetime, nullable=True)
    ended_at = Column(UTCAwareDatetime, nullable=True)
    canceled_at = Column(UTCAwareDatetime, nullable=True)
    canceled_by = Column(Text, nullable=True)
    blocked_reason = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    max_retries = Column(Integer, nullable=False, default=0, server_default="0")
    last_error = Column(Text, nullable=True)
    run_config_json = Column(JSON, nullable=False, server_default="{}")

    program = relationship("Program", back_populates="campaign_runs")
    primary_scope_target = relationship("ScopeTarget", back_populates="campaign_runs")
    workflow_runs = relationship(
        "WorkflowRun", back_populates="campaign_run", cascade="all, delete-orphan"
    )
    branches = relationship("ExecutionBranch", back_populates="campaign")
    phase_jobs = relationship("PhaseJob", back_populates="campaign")
    approval_gates = relationship("ApprovalGate", back_populates="campaign")
    tool_executions = relationship("ToolExecution", back_populates="campaign")
    artifacts = relationship("Artifact", back_populates="campaign")
    observations = relationship("Observation", back_populates="campaign")
    scan_notes = relationship("ScanNote", back_populates="campaign")
    submission_drafts = relationship("SubmissionDraft", back_populates="campaign")
    audit_events = relationship("AuditEvent", back_populates="campaign")
    intentions = relationship("IntentionRecord", back_populates="campaign_run")


class ExecutionBranch(Base, TimestampMixin):
    __tablename__ = "execution_branches"
    __table_args__ = (
        UniqueConstraint("campaign_id", "branch_key", name="uq_execution_branches_campaign_branch_key"),
        CheckConstraint("btrim(branch_key) <> ''", name="execution_branches_branch_key_not_empty"),
        Index("ix_execution_branches_campaign_id", "campaign_id"),
        Index("ix_execution_branches_status", "status"),
        Index("ix_execution_branches_parent_branch_id", "parent_branch_id"),
        Index("ix_execution_branches_depends_on_branch_id", "depends_on_branch_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_branches.id", ondelete="SET NULL"),
        nullable=True,
    )
    depends_on_branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_branches.id", ondelete="SET NULL"),
        nullable=True,
    )
    branch_key = Column(Text, nullable=False)
    branch_name = Column(Text, nullable=True)
    status = Column(
        SAEnum(
            BranchStatusEnum,
            name="branch_status_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        server_default=BranchStatusEnum.PENDING.value,
    )
    declared_goal = Column(Text, nullable=True)
    policy_basis = Column(Text, nullable=True)
    risk_class = Column(
        SAEnum(
            RiskPolicyClassEnum,
            name="risk_policy_class_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=True,
    )
    approval_required = Column(Boolean, nullable=False, default=False, server_default="false")
    queued_at = Column(UTCAwareDatetime, nullable=True)
    started_at = Column(UTCAwareDatetime, nullable=True)
    ended_at = Column(UTCAwareDatetime, nullable=True)
    canceled_at = Column(UTCAwareDatetime, nullable=True)
    canceled_by = Column(Text, nullable=True)
    blocked_reason = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    max_retries = Column(Integer, nullable=False, default=0, server_default="0")
    branch_config_json = Column(JSON, nullable=False, server_default="{}")

    campaign = relationship("CampaignRun", back_populates="branches")
    parent_branch = relationship(
        "ExecutionBranch",
        remote_side=[id],
        foreign_keys=[parent_branch_id],
        back_populates="child_branches",
        post_update=True,
    )
    child_branches = relationship(
        "ExecutionBranch",
        foreign_keys=[parent_branch_id],
        back_populates="parent_branch",
    )
    depends_on_branch = relationship(
        "ExecutionBranch",
        remote_side=[id],
        foreign_keys=[depends_on_branch_id],
        back_populates="dependent_branches",
        post_update=True,
    )
    dependent_branches = relationship(
        "ExecutionBranch",
        foreign_keys=[depends_on_branch_id],
        back_populates="depends_on_branch",
    )
    phase_jobs = relationship("PhaseJob", back_populates="branch")
    approval_gates = relationship("ApprovalGate", back_populates="branch")
    tool_executions = relationship("ToolExecution", back_populates="branch")
    artifacts = relationship("Artifact", back_populates="branch")
    observations = relationship("Observation", back_populates="branch")
    scan_notes = relationship("ScanNote", back_populates="branch")
    submission_drafts = relationship("SubmissionDraft", back_populates="branch")
    audit_events = relationship("AuditEvent", back_populates="branch")
    intentions = relationship("IntentionRecord", back_populates="branch")


class PhaseJob(Base, TimestampMixin):
    __tablename__ = "phase_jobs"
    __table_args__ = (
        CheckConstraint("btrim(phase_name) <> ''", name="phase_jobs_phase_name_not_empty"),
        Index("ix_phase_jobs_campaign_id", "campaign_id"),
        Index("ix_phase_jobs_branch_id", "branch_id"),
        Index("ix_phase_jobs_status", "status"),
        Index("ix_phase_jobs_depends_on_job_id", "depends_on_job_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_branches.id", ondelete="CASCADE"),
        nullable=False,
    )
    depends_on_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("phase_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    phase_name = Column(Text, nullable=False)
    phase_order = Column(Integer, nullable=False, default=0, server_default="0")
    status = Column(
        SAEnum(
            PhaseJobStatusEnum,
            name="phase_job_status_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        server_default=PhaseJobStatusEnum.CREATED.value,
    )
    policy_class = Column(
        SAEnum(
            RiskPolicyClassEnum,
            name="risk_policy_class_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=True,
    )
    approval_required = Column(Boolean, nullable=False, default=False, server_default="false")
    queued_at = Column(UTCAwareDatetime, nullable=True)
    started_at = Column(UTCAwareDatetime, nullable=True)
    ended_at = Column(UTCAwareDatetime, nullable=True)
    canceled_at = Column(UTCAwareDatetime, nullable=True)
    canceled_by = Column(Text, nullable=True)
    blocked_reason = Column(Text, nullable=True)
    worker_task_id = Column(Text, nullable=True)
    queue_name = Column(Text, nullable=True)
    workflow_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    stage_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stage_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    max_retries = Column(Integer, nullable=False, default=0, server_default="0")
    input_payload_json = Column(JSON, nullable=False, server_default="{}")
    output_summary_json = Column(JSON, nullable=False, server_default="{}")
    error_message = Column(Text, nullable=True)

    campaign = relationship("CampaignRun", back_populates="phase_jobs")
    branch = relationship("ExecutionBranch", back_populates="phase_jobs")
    workflow_run = relationship(
        "WorkflowRun",
        back_populates="phase_jobs",
        foreign_keys="[PhaseJob.workflow_run_id]",
    )
    stage_run = relationship(
        "StageRun",
        back_populates="phase_jobs",
        foreign_keys="[PhaseJob.stage_run_id]",
    )
    depends_on_job = relationship(
        "PhaseJob",
        remote_side=[id],
        foreign_keys=[depends_on_job_id],
        back_populates="dependent_jobs",
        post_update=True,
    )
    dependent_jobs = relationship(
        "PhaseJob",
        foreign_keys=[depends_on_job_id],
        back_populates="depends_on_job",
    )
    approval_gates = relationship("ApprovalGate", back_populates="phase_job")
    tool_executions = relationship("ToolExecution", back_populates="phase_job")
    artifacts = relationship("Artifact", back_populates="phase_job")
    observations = relationship("Observation", back_populates="phase_job")
    audit_events = relationship("AuditEvent", back_populates="phase_job")
    intentions = relationship("IntentionRecord", back_populates="phase_job")


class ApprovalGate(Base, TimestampMixin):
    __tablename__ = "approval_gates"
    __table_args__ = (
        CheckConstraint("btrim(gate_reason) <> ''", name="approval_gates_reason_not_empty"),
        CheckConstraint("btrim(requested_by) <> ''", name="approval_gates_requested_by_not_empty"),
        Index("ix_approval_gates_campaign_id", "campaign_id"),
        Index("ix_approval_gates_branch_id", "branch_id"),
        Index("ix_approval_gates_phase_job_id", "phase_job_id"),
        Index("ix_approval_gates_status", "status"),
        Index("ix_approval_gates_requested_at", "requested_at"),
        Index("ix_approval_gates_tenant_id", "tenant_id"),
        UniqueConstraint("id", "tenant_id", name="uq_approval_gate_tenant_id") # Unique constraint for safety
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_branches.id", ondelete="SET NULL"),
        nullable=True,
    )
    phase_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("phase_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    intention_id = Column(
        UUID(as_uuid=True),
        ForeignKey("intention_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(
        SAEnum(
            ApprovalGateStatusEnum,
            name="approval_gate_status_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        server_default=ApprovalGateStatusEnum.PENDING.value,
    )
    gate_reason = Column(Text, nullable=False)
    policy_basis = Column(Text, nullable=True)
    risk_class = Column(
        SAEnum(
            RiskPolicyClassEnum,
            name="risk_policy_class_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=True,
    )
    requested_by = Column(Text, nullable=False)
    requested_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )
    decided_by = Column(Text, nullable=True)
    decided_at = Column(UTCAwareDatetime, nullable=True)
    expires_at = Column(UTCAwareDatetime, nullable=True)
    canceled_at = Column(UTCAwareDatetime, nullable=True)
    canceled_by = Column(Text, nullable=True)
    operator_notes = Column(Text, nullable=True)
    decision_payload_json = Column(JSON, nullable=False, server_default="{}")

    campaign = relationship("CampaignRun", back_populates="approval_gates")
    tenant = relationship("Tenant") # One-way for tenant_id filtering
    branch = relationship("ExecutionBranch", back_populates="approval_gates")
    phase_job = relationship("PhaseJob", back_populates="approval_gates")
    intention = relationship("IntentionRecord", back_populates="approval_gates")
    tool_executions = relationship("ToolExecution", back_populates="approval_gate")
    audit_events = relationship("AuditEvent", back_populates="approval_gate")


class ToolExecution(Base, TimestampMixin):
    __tablename__ = "tool_executions"
    __table_args__ = (
        CheckConstraint("btrim(tool_name) <> ''", name="tool_executions_tool_name_not_empty"),
        Index("ix_tool_executions_campaign_id", "campaign_id"),
        Index("ix_tool_executions_branch_id", "branch_id"),
        Index("ix_tool_executions_phase_job_id", "phase_job_id"),
        Index("ix_tool_executions_stage_run_id", "stage_run_id"),
        Index("ix_tool_executions_status", "status"),
        Index("ix_tool_executions_approval_gate_id", "approval_gate_id"),
        Index("ix_tool_executions_intention_id", "intention_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_branches.id", ondelete="SET NULL"),
        nullable=True,
    )
    phase_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("phase_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    stage_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stage_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    approval_gate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("approval_gates.id", ondelete="SET NULL"),
        nullable=True,
    )
    intention_id = Column(
        UUID(as_uuid=True),
        ForeignKey("intention_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_name = Column(Text, nullable=False)
    adapter_name = Column(Text, nullable=True)
    execution_mode = Column(Text, nullable=True)
    status = Column(
        SAEnum(
            ToolExecutionStatusEnum,
            name="tool_execution_status_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        server_default=ToolExecutionStatusEnum.CREATED.value,
    )
    input_target = Column(Text, nullable=True)
    input_payload_json = Column(JSON, nullable=False, server_default="{}")
    stdout_ref = Column(Text, nullable=True)
    stderr_ref = Column(Text, nullable=True)
    stdout_summary = Column(Text, nullable=True)
    stderr_summary = Column(Text, nullable=True)
    artifact_path = Column(Text, nullable=True)
    exit_code = Column(Integer, nullable=True)
    duration_ms = Column(Float, nullable=True)
    policy_class = Column(
        SAEnum(
            RiskPolicyClassEnum,
            name="risk_policy_class_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=True,
    )
    queued_at = Column(UTCAwareDatetime, nullable=True)
    started_at = Column(UTCAwareDatetime, nullable=True)
    ended_at = Column(UTCAwareDatetime, nullable=True)
    canceled_at = Column(UTCAwareDatetime, nullable=True)
    canceled_by = Column(Text, nullable=True)
    worker_task_id = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    max_retries = Column(Integer, nullable=False, default=0, server_default="0")
    error_message = Column(Text, nullable=True)

    campaign = relationship("CampaignRun", back_populates="tool_executions")
    branch = relationship("ExecutionBranch", back_populates="tool_executions")
    phase_job = relationship("PhaseJob", back_populates="tool_executions")
    stage_run = relationship("StageRun", back_populates="tool_executions")
    approval_gate = relationship("ApprovalGate", back_populates="tool_executions")
    intention = relationship("IntentionRecord", back_populates="tool_executions")
    artifacts = relationship("Artifact", back_populates="tool_execution")
    observations = relationship("Observation", back_populates="tool_execution")
    audit_events = relationship("AuditEvent", back_populates="tool_execution")


class Artifact(Base, TimestampMixin):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint("btrim(uri) <> ''", name="artifacts_uri_not_empty"),
        Index("ix_artifacts_campaign_id", "campaign_id"),
        Index("ix_artifacts_branch_id", "branch_id"),
        Index("ix_artifacts_phase_job_id", "phase_job_id"),
        Index("ix_artifacts_tool_execution_id", "tool_execution_id"),
        Index("ix_artifacts_finding_id", "finding_id"),
        Index("ix_artifacts_report_id", "report_id"),
        Index("ix_artifacts_artifact_type", "artifact_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_branches.id", ondelete="SET NULL"),
        nullable=True,
    )
    phase_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("phase_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tool_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    finding_id = Column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    intention_id = Column(
        UUID(as_uuid=True),
        ForeignKey("intention_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    artifact_type = Column(
        SAEnum(
            ArtifactTypeEnum,
            name="artifact_type_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        server_default=ArtifactTypeEnum.RAW_OUTPUT.value,
    )
    uri = Column(Text, nullable=False)
    content_hash = Column(Text, nullable=True)
    mime_type = Column(Text, nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    description = Column(Text, nullable=True)
    policy_class = Column(
        SAEnum(
            RiskPolicyClassEnum,
            name="risk_policy_class_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=True,
    )
    details_json = Column(JSON, nullable=False, server_default="{}")

    campaign = relationship("CampaignRun", back_populates="artifacts")
    branch = relationship("ExecutionBranch", back_populates="artifacts")
    phase_job = relationship("PhaseJob", back_populates="artifacts")
    tool_execution = relationship("ToolExecution", back_populates="artifacts")
    intention = relationship("IntentionRecord", back_populates="artifacts")
    observations = relationship("Observation", back_populates="source_artifact")
    audit_events = relationship("AuditEvent", back_populates="artifact")


class Observation(Base, TimestampMixin):
    __tablename__ = "observations"
    __table_args__ = (
        Index("ix_observations_campaign_id", "campaign_id"),
        Index("ix_observations_branch_id", "branch_id"),
        Index("ix_observations_phase_job_id", "phase_job_id"),
        Index("ix_observations_tool_execution_id", "tool_execution_id"),
        Index("ix_observations_source_artifact_id", "source_artifact_id"),
        Index("ix_observations_observation_type", "observation_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_branches.id", ondelete="SET NULL"),
        nullable=True,
    )
    phase_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("phase_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tool_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_artifact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    finding_id = Column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)
    intention_id = Column(
        UUID(as_uuid=True),
        ForeignKey("intention_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    observation_type = Column(
        SAEnum(
            ObservationTypeEnum,
            name="observation_type_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        server_default=ObservationTypeEnum.SIGNAL.value,
    )
    category = Column(Text, nullable=True)
    title = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    policy_class = Column(
        SAEnum(
            RiskPolicyClassEnum,
            name="risk_policy_class_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=True,
    )
    normalized_ref = Column(Text, nullable=True)
    payload_json = Column(EncryptedText, nullable=False, server_default="{}")

    campaign = relationship("CampaignRun", back_populates="observations")
    branch = relationship("ExecutionBranch", back_populates="observations")
    phase_job = relationship("PhaseJob", back_populates="observations")
    tool_execution = relationship("ToolExecution", back_populates="observations")
    source_artifact = relationship("Artifact", back_populates="observations")
    intention = relationship("IntentionRecord", back_populates="observations")
    audit_events = relationship("AuditEvent", back_populates="observation")


class ScanNote(Base, TimestampMixin):
    __tablename__ = "scan_notes"
    __table_args__ = (
        CheckConstraint("btrim(author) <> ''", name="scan_notes_author_not_empty"),
        CheckConstraint("btrim(body) <> ''", name="scan_notes_body_not_empty"),
        Index("ix_scan_notes_campaign_id", "campaign_id"),
        Index("ix_scan_notes_branch_id", "branch_id"),
        Index("ix_scan_notes_phase_job_id", "phase_job_id"),
        Index("ix_scan_notes_tool_execution_id", "tool_execution_id"),
        Index("ix_scan_notes_finding_id", "finding_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_branches.id", ondelete="SET NULL"),
        nullable=True,
    )
    phase_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("phase_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tool_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    finding_id = Column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    intention_id = Column(
        UUID(as_uuid=True),
        ForeignKey("intention_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    author = Column(Text, nullable=False)
    note_type = Column(Text, nullable=False, server_default="GENERAL")
    body = Column(Text, nullable=False)
    is_system_generated = Column(Boolean, nullable=False, default=False, server_default="false")

    campaign = relationship("CampaignRun", back_populates="scan_notes")
    branch = relationship("ExecutionBranch", back_populates="scan_notes")
    intention = relationship("IntentionRecord", back_populates="scan_notes")


class SubmissionDraft(Base, TimestampMixin):
    __tablename__ = "submission_drafts"
    __table_args__ = (
        CheckConstraint("btrim(status) <> ''", name="submission_drafts_status_not_empty"),
        Index("ix_submission_drafts_campaign_id", "campaign_id"),
        Index("ix_submission_drafts_branch_id", "branch_id"),
        Index("ix_submission_drafts_finding_id", "finding_id"),
        Index("ix_submission_drafts_report_id", "report_id"),
        Index("ix_submission_drafts_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_branches.id", ondelete="SET NULL"),
        nullable=True,
    )
    finding_id = Column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    intention_id = Column(
        UUID(as_uuid=True),
        ForeignKey("intention_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(Text, nullable=False, server_default="DRAFT")
    title = Column(Text, nullable=True)
    content_uri = Column(EncryptedText, nullable=True)
    content_hash = Column(Text, nullable=True)
    prepared_by = Column(Text, nullable=True)
    approved_by = Column(Text, nullable=True)
    approved_at = Column(UTCAwareDatetime, nullable=True)
    submitted_at = Column(UTCAwareDatetime, nullable=True)
    external_submission_id = Column(Text, nullable=True)
    details_json = Column(JSON, nullable=False, server_default="{}")

    campaign = relationship("CampaignRun", back_populates="submission_drafts")
    branch = relationship("ExecutionBranch", back_populates="submission_drafts")
    intention = relationship("IntentionRecord", back_populates="submission_drafts")


class AuditEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("btrim(event_type) <> ''", name="audit_events_event_type_not_empty"),
        Index("ix_audit_events_campaign_id", "campaign_id"),
        Index("ix_audit_events_branch_id", "branch_id"),
        Index("ix_audit_events_phase_job_id", "phase_job_id"),
        Index("ix_audit_events_tool_execution_id", "tool_execution_id"),
        Index("ix_audit_events_approval_gate_id", "approval_gate_id"),
        Index("ix_audit_events_event_type", "event_type"),
        Index("ix_audit_events_happened_at", "happened_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_branches.id", ondelete="SET NULL"),
        nullable=True,
    )
    phase_job_id = Column(UUID(as_uuid=True), ForeignKey("phase_jobs.id", ondelete="SET NULL"), nullable=True)
    tool_execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tool_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    approval_gate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("approval_gates.id", ondelete="SET NULL"),
        nullable=True,
    )
    artifact_id = Column(UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="SET NULL"), nullable=True)
    observation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("observations.id", ondelete="SET NULL"),
        nullable=True,
    )
    finding_id = Column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    intention_id = Column(
        UUID(as_uuid=True),
        ForeignKey("intention_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type = Column(Text, nullable=False)
    actor = Column(Text, nullable=True)
    message = Column(Text, nullable=True)
    policy_basis = Column(Text, nullable=True)
    policy_class = Column(
        SAEnum(
            RiskPolicyClassEnum,
            name="risk_policy_class_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=True,
    )
    risk_posture_changed = Column(Boolean, nullable=False, default=False, server_default="false")
    happened_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )
    correlation_id = Column(UUID(as_uuid=True), nullable=True)
    event_payload_json = Column(JSON, nullable=False, server_default="{}")

    campaign = relationship("CampaignRun", back_populates="audit_events")
    branch = relationship("ExecutionBranch", back_populates="audit_events")
    phase_job = relationship("PhaseJob", back_populates="audit_events")
    tool_execution = relationship("ToolExecution", back_populates="audit_events")
    approval_gate = relationship("ApprovalGate", back_populates="audit_events")
    artifact = relationship("Artifact", back_populates="audit_events")
    observation = relationship("Observation", back_populates="audit_events")
    intention = relationship("IntentionRecord", back_populates="audit_events")
