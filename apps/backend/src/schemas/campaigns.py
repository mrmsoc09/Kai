from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ..models.enums import (
    ApprovalGateStatusEnum,
    ArtifactTypeEnum,
    BranchStatusEnum,
    CampaignStatusEnum,
    ObservationTypeEnum,
    PhaseJobStatusEnum,
    RiskPolicyClassEnum,
    ToolExecutionStatusEnum,
)


class ProgramCreate(BaseModel):
    program_key: str | None = Field(default=None, max_length=255)
    name: str = Field(..., min_length=1, max_length=500)
    platform: str | None = Field(default=None, max_length=255)
    handle: str | None = Field(default=None, max_length=255)
    policy_url: str | None = Field(default=None, max_length=2048)
    created_by: str | None = Field(default=None, max_length=255)
    config_json: dict = Field(default_factory=dict)


class ProgramRead(BaseModel):
    id: UUID
    program_key: str | None = None
    name: str
    platform: str | None = None
    handle: str | None = None
    policy_url: str | None = None
    status: str
    created_by: str | None = None
    config_json: dict
    created_at: datetime
    updated_at: datetime


class ScopeTargetCreate(BaseModel):
    program_id: UUID
    target: str = Field(..., min_length=1, max_length=2048)
    target_type: str = Field(..., min_length=1, max_length=64)
    is_in_scope: bool = True
    policy_class: RiskPolicyClassEnum | None = None
    normalization_key: str | None = Field(default=None, max_length=255)
    details_json: dict = Field(default_factory=dict)


class ScopeTargetRead(BaseModel):
    id: UUID
    program_id: UUID
    target: str
    target_type: str
    is_in_scope: bool
    policy_class: RiskPolicyClassEnum | None = None
    normalization_key: str | None = None
    details_json: dict
    created_at: datetime
    updated_at: datetime


class CampaignRunCreate(BaseModel):
    program_id: UUID
    primary_scope_target_id: UUID | None = None
    idempotency_key: UUID | None = None
    campaign_name: str | None = Field(default=None, max_length=255)
    initiated_by: str = Field(..., min_length=1, max_length=255)
    declared_goal: str = Field(..., min_length=1, max_length=2000)
    declared_reason: str | None = Field(default=None, max_length=4000)
    policy_basis: str | None = Field(default=None, max_length=4000)
    risk_class: RiskPolicyClassEnum | None = None
    approval_required: bool = False
    run_config_json: dict = Field(default_factory=dict)


class CampaignRunRead(BaseModel):
    id: UUID
    program_id: UUID
    primary_scope_target_id: UUID | None = None
    idempotency_key: UUID | None = None
    campaign_name: str | None = None
    initiated_by: str
    declared_goal: str
    declared_reason: str | None = None
    policy_basis: str | None = None
    risk_class: RiskPolicyClassEnum | None = None
    approval_required: bool
    status: CampaignStatusEnum
    queued_at: datetime | None = None
    started_at: datetime | None = None
    paused_at: datetime | None = None
    ended_at: datetime | None = None
    canceled_at: datetime | None = None
    canceled_by: str | None = None
    blocked_reason: str | None = None
    retry_count: int
    max_retries: int
    last_error: str | None = None
    run_config_json: dict
    created_at: datetime
    updated_at: datetime


class ExecutionBranchCreate(BaseModel):
    campaign_id: UUID
    parent_branch_id: UUID | None = None
    depends_on_branch_id: UUID | None = None
    branch_key: str = Field(..., min_length=1, max_length=255)
    branch_name: str | None = Field(default=None, max_length=255)
    declared_goal: str | None = Field(default=None, max_length=2000)
    policy_basis: str | None = Field(default=None, max_length=4000)
    risk_class: RiskPolicyClassEnum | None = None
    approval_required: bool = False
    max_retries: int = 0
    branch_config_json: dict = Field(default_factory=dict)


class ExecutionBranchRead(BaseModel):
    id: UUID
    campaign_id: UUID
    parent_branch_id: UUID | None = None
    depends_on_branch_id: UUID | None = None
    branch_key: str
    branch_name: str | None = None
    status: BranchStatusEnum
    declared_goal: str | None = None
    policy_basis: str | None = None
    risk_class: RiskPolicyClassEnum | None = None
    approval_required: bool
    queued_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    canceled_at: datetime | None = None
    canceled_by: str | None = None
    blocked_reason: str | None = None
    retry_count: int
    max_retries: int
    branch_config_json: dict
    created_at: datetime
    updated_at: datetime


class PhaseJobCreate(BaseModel):
    campaign_id: UUID
    branch_id: UUID
    depends_on_job_id: UUID | None = None
    phase_name: str = Field(..., min_length=1, max_length=255)
    phase_order: int = 0
    policy_class: RiskPolicyClassEnum | None = None
    approval_required: bool = False
    queue_name: str | None = Field(default=None, max_length=255)
    max_retries: int = 0
    input_payload_json: dict = Field(default_factory=dict)


class PhaseJobRead(BaseModel):
    id: UUID
    campaign_id: UUID
    branch_id: UUID
    depends_on_job_id: UUID | None = None
    phase_name: str
    phase_order: int
    status: PhaseJobStatusEnum
    policy_class: RiskPolicyClassEnum | None = None
    approval_required: bool
    queued_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    canceled_at: datetime | None = None
    canceled_by: str | None = None
    blocked_reason: str | None = None
    worker_task_id: str | None = None
    queue_name: str | None = None
    retry_count: int
    max_retries: int
    input_payload_json: dict
    output_summary_json: dict
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ApprovalGateCreate(BaseModel):
    campaign_id: UUID
    branch_id: UUID | None = None
    phase_job_id: UUID | None = None
    intention_id: UUID | None = None
    gate_reason: str = Field(..., min_length=1, max_length=4000)
    policy_basis: str | None = Field(default=None, max_length=4000)
    risk_class: RiskPolicyClassEnum | None = None
    requested_by: str = Field(..., min_length=1, max_length=255)
    expires_at: datetime | None = None
    operator_notes: str | None = Field(default=None, max_length=4000)
    decision_payload_json: dict = Field(default_factory=dict)


class ApprovalGateDecision(BaseModel):
    status: ApprovalGateStatusEnum
    decided_by: str = Field(..., min_length=1, max_length=255)
    operator_notes: str | None = Field(default=None, max_length=4000)
    decision_payload_json: dict = Field(default_factory=dict)


class ApprovalGateRead(BaseModel):
    id: UUID
    campaign_id: UUID
    branch_id: UUID | None = None
    phase_job_id: UUID | None = None
    intention_id: UUID | None = None
    status: ApprovalGateStatusEnum
    gate_reason: str
    policy_basis: str | None = None
    risk_class: RiskPolicyClassEnum | None = None
    requested_by: str
    requested_at: datetime
    decided_by: str | None = None
    decided_at: datetime | None = None
    expires_at: datetime | None = None
    canceled_at: datetime | None = None
    canceled_by: str | None = None
    operator_notes: str | None = None
    decision_payload_json: dict
    created_at: datetime
    updated_at: datetime


class ToolExecutionCreate(BaseModel):
    campaign_id: UUID
    branch_id: UUID | None = None
    phase_job_id: UUID | None = None
    approval_gate_id: UUID | None = None
    intention_id: UUID | None = None
    tool_name: str = Field(..., min_length=1, max_length=255)
    adapter_name: str | None = Field(default=None, max_length=255)
    input_target: str | None = Field(default=None, max_length=2048)
    input_payload_json: dict = Field(default_factory=dict)
    policy_class: RiskPolicyClassEnum | None = None
    max_retries: int = 0


class ToolExecutionRead(BaseModel):
    id: UUID
    campaign_id: UUID
    branch_id: UUID | None = None
    phase_job_id: UUID | None = None
    approval_gate_id: UUID | None = None
    intention_id: UUID | None = None
    tool_name: str
    adapter_name: str | None = None
    status: ToolExecutionStatusEnum
    input_target: str | None = None
    input_payload_json: dict
    stdout_ref: str | None = None
    stderr_ref: str | None = None
    stdout_summary: str | None = None
    stderr_summary: str | None = None
    exit_code: int | None = None
    policy_class: RiskPolicyClassEnum | None = None
    queued_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    canceled_at: datetime | None = None
    canceled_by: str | None = None
    worker_task_id: str | None = None
    retry_count: int
    max_retries: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ArtifactCreate(BaseModel):
    campaign_id: UUID
    branch_id: UUID | None = None
    phase_job_id: UUID | None = None
    tool_execution_id: UUID | None = None
    finding_id: UUID | None = None
    report_id: UUID | None = None
    intention_id: UUID | None = None
    artifact_type: ArtifactTypeEnum = ArtifactTypeEnum.RAW_OUTPUT
    uri: str = Field(..., min_length=1, max_length=2048)
    content_hash: str | None = Field(default=None, max_length=128)
    mime_type: str | None = Field(default=None, max_length=255)
    size_bytes: int | None = None
    description: str | None = Field(default=None, max_length=1000)
    policy_class: RiskPolicyClassEnum | None = None
    details_json: dict = Field(default_factory=dict)


class ArtifactRead(BaseModel):
    id: UUID
    campaign_id: UUID
    branch_id: UUID | None = None
    phase_job_id: UUID | None = None
    tool_execution_id: UUID | None = None
    finding_id: UUID | None = None
    report_id: UUID | None = None
    intention_id: UUID | None = None
    artifact_type: ArtifactTypeEnum
    uri: str
    content_hash: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    description: str | None = None
    policy_class: RiskPolicyClassEnum | None = None
    details_json: dict
    created_at: datetime
    updated_at: datetime


class ObservationCreate(BaseModel):
    campaign_id: UUID
    branch_id: UUID | None = None
    phase_job_id: UUID | None = None
    tool_execution_id: UUID | None = None
    source_artifact_id: UUID | None = None
    finding_id: UUID | None = None
    intention_id: UUID | None = None
    observation_type: ObservationTypeEnum = ObservationTypeEnum.SIGNAL
    category: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=500)
    summary: str | None = Field(default=None, max_length=4000)
    confidence: float | None = None
    policy_class: RiskPolicyClassEnum | None = None
    normalized_ref: str | None = Field(default=None, max_length=2000)
    payload_json: dict = Field(default_factory=dict)


class ObservationRead(BaseModel):
    id: UUID
    campaign_id: UUID
    branch_id: UUID | None = None
    phase_job_id: UUID | None = None
    tool_execution_id: UUID | None = None
    source_artifact_id: UUID | None = None
    finding_id: UUID | None = None
    intention_id: UUID | None = None
    observation_type: ObservationTypeEnum
    category: str | None = None
    title: str | None = None
    summary: str | None = None
    confidence: float | None = None
    policy_class: RiskPolicyClassEnum | None = None
    normalized_ref: str | None = None
    payload_json: dict
    created_at: datetime
    updated_at: datetime


class ScanNoteCreate(BaseModel):
    campaign_id: UUID
    branch_id: UUID | None = None
    phase_job_id: UUID | None = None
    tool_execution_id: UUID | None = None
    finding_id: UUID | None = None
    report_id: UUID | None = None
    intention_id: UUID | None = None
    author: str = Field(..., min_length=1, max_length=255)
    note_type: str = Field(default="GENERAL", min_length=1, max_length=128)
    body: str = Field(..., min_length=1, max_length=10000)
    is_system_generated: bool = False


class SubmissionDraftCreate(BaseModel):
    campaign_id: UUID
    branch_id: UUID | None = None
    finding_id: UUID | None = None
    report_id: UUID | None = None
    intention_id: UUID | None = None
    status: str = Field(default="DRAFT", min_length=1, max_length=128)
    title: str | None = Field(default=None, max_length=500)
    content_uri: str | None = Field(default=None, max_length=2048)
    content_hash: str | None = Field(default=None, max_length=128)
    prepared_by: str | None = Field(default=None, max_length=255)
    details_json: dict = Field(default_factory=dict)


class AuditEventCreate(BaseModel):
    campaign_id: UUID | None = None
    branch_id: UUID | None = None
    phase_job_id: UUID | None = None
    tool_execution_id: UUID | None = None
    approval_gate_id: UUID | None = None
    artifact_id: UUID | None = None
    observation_id: UUID | None = None
    finding_id: UUID | None = None
    report_id: UUID | None = None
    intention_id: UUID | None = None
    event_type: str = Field(..., min_length=1, max_length=255)
    actor: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, max_length=4000)
    policy_basis: str | None = Field(default=None, max_length=4000)
    policy_class: RiskPolicyClassEnum | None = None
    risk_posture_changed: bool = False
    happened_at: datetime | None = None
    correlation_id: UUID | None = None
    event_payload_json: dict = Field(default_factory=dict)


class PhaseSeedSpec(BaseModel):
    phase_name: str = Field(..., min_length=1, max_length=255)
    phase_order: int = Field(default=0, ge=0)
    approval_required: bool = False
    queue_name: str | None = Field(default=None, max_length=255)
    input_payload_json: dict = Field(default_factory=dict)


class CampaignStartRequest(BaseModel):
    program_id: UUID | None = None
    program_name: str | None = Field(default=None, max_length=500)
    program_key: str | None = Field(default=None, max_length=255)
    target: str | None = Field(default=None, max_length=2048)
    target_type: str = Field(default="domain", min_length=1, max_length=64)
    campaign_name: str | None = Field(default=None, max_length=255)
    initiated_by: str = Field(..., min_length=1, max_length=255)
    declared_goal: str = Field(..., min_length=1, max_length=2000)
    declared_reason: str | None = Field(default=None, max_length=4000)
    policy_basis: str | None = Field(default=None, max_length=4000)
    risk_class: RiskPolicyClassEnum | None = None
    approval_required: bool = False
    idempotency_key: UUID | None = None
    initial_branch_key: str = Field(default="root", min_length=1, max_length=255)
    initial_branch_name: str | None = Field(default="primary", max_length=255)
    run_config_json: dict = Field(default_factory=dict)
    phases: list[PhaseSeedSpec] | None = None
    phase_approval_overrides: dict[str, bool] = Field(default_factory=dict)


class CampaignScheduleSummary(BaseModel):
    campaign_id: UUID
    considered_jobs: int
    queued_jobs: int
    blocked_jobs: int
    waiting_approval_jobs: int
    created_approval_gates: int
    dispatched_tool_executions: int


class CampaignStartResponse(BaseModel):
    campaign_id: UUID
    program_id: UUID
    branch_id: UUID
    campaign_status: CampaignStatusEnum
    branch_status: BranchStatusEnum
    phase_jobs: list[PhaseJobRead]
    scheduler: CampaignScheduleSummary
    idempotent_replay: bool = False


class ExecutionResultArtifactInput(BaseModel):
    artifact_type: ArtifactTypeEnum = ArtifactTypeEnum.RAW_OUTPUT
    uri: str | None = Field(default=None, max_length=2048)
    content_hash: str | None = Field(default=None, max_length=128)
    mime_type: str | None = Field(default=None, max_length=255)
    size_bytes: int | None = None
    description: str | None = Field(default=None, max_length=1000)
    details_json: dict = Field(default_factory=dict)


class ExecutionResultObservationInput(BaseModel):
    observation_type: ObservationTypeEnum = ObservationTypeEnum.SIGNAL
    category: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=500)
    summary: str | None = Field(default=None, max_length=4000)
    confidence: float | None = None
    normalized_ref: str | None = Field(default=None, max_length=2000)
    payload_json: dict = Field(default_factory=dict)


class ExecutionResultIngestRequest(BaseModel):
    execution_id: UUID | None = None
    worker_task_id: str | None = Field(default=None, max_length=255)
    phase_job_id: UUID | None = None
    tool_status: ToolExecutionStatusEnum
    actor: str | None = Field(default=None, max_length=255)
    intention_id: UUID | None = None
    exit_code: int | None = None
    error_message: str | None = Field(default=None, max_length=4000)
    canceled_by: str | None = Field(default=None, max_length=255)
    approval_reason: str | None = Field(default=None, max_length=4000)
    stdout_ref: str | None = Field(default=None, max_length=2048)
    stderr_ref: str | None = Field(default=None, max_length=2048)
    stdout_summary: str | None = Field(default=None, max_length=4000)
    stderr_summary: str | None = Field(default=None, max_length=4000)
    result_payload_json: dict = Field(default_factory=dict)
    artifacts: list[ExecutionResultArtifactInput] = Field(default_factory=list)
    observations: list[ExecutionResultObservationInput] = Field(default_factory=list)
    trigger_scheduler: bool = True


class ExecutionResultIngestResponse(BaseModel):
    campaign_id: UUID
    branch_id: UUID | None = None
    phase_job_id: UUID | None = None
    execution_id: UUID
    tool_status: ToolExecutionStatusEnum
    phase_status: PhaseJobStatusEnum | None = None
    branch_status: BranchStatusEnum | None = None
    campaign_status: CampaignStatusEnum | None = None
    artifact_ids: list[UUID] = Field(default_factory=list)
    observation_ids: list[UUID] = Field(default_factory=list)
    scheduler: CampaignScheduleSummary | None = None


class CampaignApprovalDecisionRequest(BaseModel):
    status: ApprovalGateStatusEnum
    decided_by: str = Field(..., min_length=1, max_length=255)
    operator_notes: str | None = Field(default=None, max_length=4000)
    decision_payload_json: dict = Field(default_factory=dict)
    intention_id: UUID | None = None
    trigger_scheduler: bool = True


class CampaignApprovalDecisionResponse(BaseModel):
    gate_id: UUID
    campaign_id: UUID
    status: ApprovalGateStatusEnum
    decided_by: str | None = None
    decided_at: datetime | None = None
    scheduler: CampaignScheduleSummary | None = None
