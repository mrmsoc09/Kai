from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import (
    ApprovalGateStatusEnum,
    ArtifactTypeEnum,
    BranchStatusEnum,
    CampaignStatusEnum,
    FindingStatusEnum,
    ObservationTypeEnum,
    PhaseJobStatusEnum,
    RiskPolicyClassEnum,
    SeverityEnum,
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
    stage_run_id: UUID | None = None
    approval_gate_id: UUID | None = None
    intention_id: UUID | None = None
    tool_name: str = Field(..., min_length=1, max_length=255)
    adapter_name: str | None = Field(default=None, max_length=255)
    execution_mode: str | None = Field(default=None, max_length=64)
    input_target: str | None = Field(default=None, max_length=2048)
    input_payload_json: dict = Field(default_factory=dict)
    policy_class: RiskPolicyClassEnum | None = None
    max_retries: int = 0


class ToolExecutionRead(BaseModel):
    id: UUID
    campaign_id: UUID
    branch_id: UUID | None = None
    phase_job_id: UUID | None = None
    stage_run_id: UUID | None = None
    approval_gate_id: UUID | None = None
    intention_id: UUID | None = None
    tool_name: str
    adapter_name: str | None = None
    execution_mode: str | None = None
    status: ToolExecutionStatusEnum
    input_target: str | None = None
    input_payload_json: dict
    stdout_ref: str | None = None
    stderr_ref: str | None = None
    stdout_summary: str | None = None
    stderr_summary: str | None = None
    artifact_path: str | None = None
    exit_code: int | None = None
    duration_ms: float | None = None
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
    depends_on_phase_name: str | None = Field(default=None, max_length=255)
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


class WorkflowTemplateInfo(BaseModel):
    name: str
    description: str
    stage_count: int
    tools: list[str] = Field(default_factory=list)
    stages: list[str] = Field(default_factory=list)


class WorkflowStartRequest(BaseModel):
    workflow_template: str = Field(..., min_length=1, max_length=255)
    program_id: UUID | None = None
    program_name: str | None = Field(default=None, max_length=500)
    program_key: str | None = Field(default=None, max_length=255)
    target: str = Field(..., min_length=1, max_length=2048)
    target_type: str = Field(default="domain", min_length=1, max_length=64)
    campaign_name: str | None = Field(default=None, max_length=255)
    initiated_by: str = Field(..., min_length=1, max_length=255)
    declared_goal: str | None = Field(default=None, max_length=2000)
    declared_reason: str | None = Field(default=None, max_length=4000)
    policy_basis: str | None = Field(default=None, max_length=4000)
    risk_class: RiskPolicyClassEnum | None = None
    approval_required: bool = False
    idempotency_key: UUID | None = None
    initial_branch_key: str = Field(default="root", min_length=1, max_length=255)
    initial_branch_name: str | None = Field(default="primary", max_length=255)
    run_config_json: dict = Field(default_factory=dict)
    phase_approval_overrides: dict[str, bool] = Field(default_factory=dict)
    safe_mode: bool = True
    dry_run: bool = False
    enable_steps: list[str] = Field(default_factory=list)
    disable_steps: list[str] = Field(default_factory=list)
    scope_policy_path: str | None = Field(default=None, max_length=4096)


class WorkflowStartResponse(BaseModel):
    workflow_template: str
    workflow_metadata: dict = Field(default_factory=dict)
    dry_run: bool
    campaign_id: UUID | None = None
    program_id: UUID | None = None
    branch_id: UUID | None = None
    campaign_status: CampaignStatusEnum | None = None
    branch_status: BranchStatusEnum | None = None
    phase_jobs: list[dict] = Field(default_factory=list)
    scheduler: CampaignScheduleSummary | None = None
    idempotent_replay: bool = False


class WorkflowExecuteRequest(BaseModel):
    workflow_template: str = Field(..., min_length=1, max_length=255)
    target: str = Field(..., min_length=1, max_length=2048)
    run_id: str | None = Field(default=None, max_length=255)
    safe_mode: bool = True
    dry_run: bool = False
    concurrency_limit: int = Field(default=4, ge=1, le=64)
    enable_steps: list[str] = Field(default_factory=list)
    disable_steps: list[str] = Field(default_factory=list)
    scope_policy_path: str | None = Field(default=None, max_length=4096)
    resume: bool = False


class WorkflowExecuteResponse(BaseModel):
    run_id: str
    workflow_template: str
    status: str
    target: str
    manifest_path: str
    summary_path: str
    report_path: str
    stage_results: list[dict] = Field(default_factory=list)
    prioritized_findings: list[dict] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)


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


class CampaignStatusItem(BaseModel):
    id: UUID
    status: CampaignStatusEnum
    program_id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CampaignBranchStatusItem(BaseModel):
    id: UUID
    branch_key: str
    status: BranchStatusEnum
    depends_on_branch_id: UUID | None = None


class CampaignPhaseJobStatusItem(BaseModel):
    id: UUID
    phase_name: str
    phase_order: int
    status: PhaseJobStatusEnum
    depends_on_job_id: UUID | None = None
    approval_required: bool
    worker_task_id: str | None = None


class CampaignStatusResponse(BaseModel):
    campaign: CampaignStatusItem
    branches: list[CampaignBranchStatusItem]
    phase_jobs: list[CampaignPhaseJobStatusItem]


class CampaignCorrelationResponse(BaseModel):
    campaign_id: UUID
    processed: int
    created_findings: int
    attached_existing: int
    context_only: int
    duplicates: int
    evidence_created: int


class ReviewObservationSummaryItem(BaseModel):
    id: UUID
    category: str | None = None
    title: str | None = None
    summary: str | None = None


class ReviewObservationSummary(BaseModel):
    count: int
    items: list[ReviewObservationSummaryItem] = Field(default_factory=list)


class FindingReviewQueueItem(BaseModel):
    finding_id: UUID
    draft_id: UUID
    campaign_id: UUID
    branch_id: UUID | None = None
    program: str
    asset: str
    title: str
    finding_status: FindingStatusEnum
    readiness_status: str
    evidence_count: int
    observation_summary: ReviewObservationSummary


class FindingReviewQueueResponse(BaseModel):
    count: int
    items: list[FindingReviewQueueItem]


class FindingReviewResponse(BaseModel):
    finding_id: UUID
    finding_status: FindingStatusEnum
    submission_draft_id: UUID
    submission_draft_status: str
    campaign_id: UUID
    review_timestamp: datetime


class PrepareSubmissionResponse(BaseModel):
    finding_id: UUID
    submission_draft_id: UUID
    submission_draft_status: str
    package_json: dict


class SubmissionExportResponse(BaseModel):
    provider: str
    finding_id: UUID
    submission_draft_id: UUID
    ready: bool
    state: str
    missing_fields: list[str]
    warnings: list[str]
    payload: dict
    stored: bool
    exported_at: datetime | None = None


class DiagnosticsCategorySummary(BaseModel):
    total: int
    by_status: dict[str, int]


class DiagnosticsSummaryResponse(BaseModel):
    generated_at: str
    campaigns: DiagnosticsCategorySummary
    branches: DiagnosticsCategorySummary
    phase_jobs: DiagnosticsCategorySummary
    approval_gates: DiagnosticsCategorySummary
    tool_executions: DiagnosticsCategorySummary
    findings: DiagnosticsCategorySummary
    submission_drafts: DiagnosticsCategorySummary


class CampaignDiagnosticsStatusItem(BaseModel):
    id: UUID
    status: CampaignStatusEnum
    created_at: datetime | None = None
    updated_at: datetime | None = None
    blocked_reason: str | None = None
    last_error: str | None = None


class CampaignDiagnosticsCounts(BaseModel):
    branches: int
    phase_jobs: int
    tool_executions: int
    approval_gates: int
    artifacts: int
    observations: int
    submission_drafts: int


class CampaignDiagnosticsPhaseLink(BaseModel):
    phase_job_id: UUID
    phase_name: str
    phase_status: PhaseJobStatusEnum
    worker_task_id: str | None = None
    depends_on_job_id: UUID | None = None


class CampaignDiagnosticsAuditEvent(BaseModel):
    id: UUID
    event_type: str
    actor: str | None = None
    happened_at: datetime | None = None
    phase_job_id: UUID | None = None
    tool_execution_id: UUID | None = None
    approval_gate_id: UUID | None = None
    message: str | None = None
    payload: dict


class CampaignDiagnosticsResponse(BaseModel):
    campaign: CampaignDiagnosticsStatusItem
    counts: CampaignDiagnosticsCounts
    status_breakdown: dict[str, dict[str, int]]
    phase_links: list[CampaignDiagnosticsPhaseLink]
    recent_audit_events: list[CampaignDiagnosticsAuditEvent]


class FindingDiagnosticsItem(BaseModel):
    id: UUID
    program: str
    asset: str
    title: str
    status: FindingStatusEnum
    severity: SeverityEnum | None = None
    scope_json: dict


class FindingDiagnosticsCounts(BaseModel):
    evidence: int
    observations: int
    artifacts: int
    submission_drafts: int
    audit_events: int


class FindingDiagnosticsDraftItem(BaseModel):
    id: UUID
    campaign_id: UUID
    branch_id: UUID | None = None
    status: str
    prepared_by: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None


class FindingDiagnosticsObservationItem(BaseModel):
    id: UUID
    category: str | None = None
    title: str | None = None
    summary: str | None = None
    tool_execution_id: UUID | None = None
    phase_job_id: UUID | None = None


class FindingDiagnosticsAuditEvent(BaseModel):
    id: UUID
    event_type: str
    actor: str | None = None
    happened_at: datetime | None = None
    message: str | None = None
    payload: dict


class FindingDiagnosticsResponse(BaseModel):
    finding: FindingDiagnosticsItem
    counts: FindingDiagnosticsCounts
    submission_drafts: list[FindingDiagnosticsDraftItem]
    recent_observations: list[FindingDiagnosticsObservationItem]
    recent_audit_events: list[FindingDiagnosticsAuditEvent]


class WorkflowRunRead(BaseModel):
    id: UUID
    campaign_run_id: UUID
    scope_target_id: UUID | None = None
    template_name: str
    target: str
    safe_mode: bool
    dry_run: bool
    trigger_source: str
    total_phases: int
    completed_phases: int
    status: str
    artifact_manifest_path: str | None = None
    plan_artifact_path: str | None = None
    summary_artifact_path: str | None = None
    duration_ms: float | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StageRunRead(BaseModel):
    id: UUID
    workflow_run_id: UUID
    campaign_run_id: UUID
    stage_name: str
    stage_order: int
    phase_count: int
    completed_count: int
    status: str
    failure_reason: str | None = None
    duration_ms: float | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CorrelationRecordRead(BaseModel):
    id: UUID
    finding_id: UUID | None = None
    observation_id: UUID | None = None
    campaign_id: UUID | None = None
    workflow_run_id: UUID | None = None
    correlation_rule: str
    asset_identifier: str | None = None
    signal_sources_json: list[str] = Field(default_factory=list)
    confidence: float | None = None
    priority_rank: int | None = None
    explanation: str | None = None
    action: str
    duplicate_of_finding_id: UUID | None = None
    correlated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowFindingRead(BaseModel):
    id: UUID
    workflow_run_id: UUID
    campaign_id: UUID | None = None
    stage_run_id: UUID | None = None
    tool_execution_id: UUID | None = None
    asset_identifier: str
    endpoint: str | None = None
    parameter: str | None = None
    vulnerability_type: str
    confidence_score: float | None = None
    severity_hint: str | None = None
    evidence_artifact_path: str | None = None
    details_json: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
