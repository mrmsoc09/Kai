from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScopeAssetInput(BaseModel):
    target: str = Field(..., min_length=1, max_length=2048)
    target_type: str = Field(default="domain", min_length=1, max_length=64)
    monitoring_enabled: bool = True
    safe_mode_required: bool = True
    priority_tier: int = Field(default=3, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=2000)


class ProgramOpportunityImportRequest(BaseModel):
    source: str = Field(default="manual", min_length=1, max_length=128)
    platform: str | None = Field(default=None, max_length=128)
    name: str = Field(..., min_length=1, max_length=500)
    handle: str | None = Field(default=None, max_length=255)
    program_key: str | None = Field(default=None, max_length=255)
    program_url: str | None = Field(default=None, max_length=2048)
    status: str = Field(default="ACTIVE", min_length=1, max_length=64)
    rules_text: str | None = None
    submission_guidelines: str | None = None
    testing_restrictions: list[str] = Field(default_factory=list)
    disclosure_restrictions: list[str] = Field(default_factory=list)
    disclosure_policy: str | None = None
    allowed_asset_types: list[str] = Field(default_factory=list)
    disallowed_workflows: list[str] = Field(default_factory=list)
    require_safe_mode: bool = True
    reward_metadata: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    in_scope_assets: list[ScopeAssetInput] = Field(default_factory=list)
    out_of_scope_assets: list[ScopeAssetInput] = Field(default_factory=list)


class ProgramOpportunityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_key: str | None = None
    name: str
    platform: str | None = None
    handle: str | None = None
    status: str
    policy_url: str | None = None
    created_by: str | None = None
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class MonitoredTargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    target: str
    target_type: str
    is_in_scope: bool
    monitoring_enabled: bool
    monitoring_priority_tier: int
    monitoring_status: str
    monitoring_source: str | None = None
    monitoring_notes: str | None = None
    safe_mode_required: bool
    last_checked_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    next_scheduled_run_at: datetime | None = None
    details_json: dict[str, Any]


class MonitoredTargetUpdateRequest(BaseModel):
    monitoring_enabled: bool | None = None
    monitoring_priority_tier: int | None = Field(default=None, ge=1, le=5)
    monitoring_status: str | None = Field(default=None, max_length=64)
    monitoring_source: str | None = Field(default=None, max_length=128)
    monitoring_notes: str | None = Field(default=None, max_length=2000)
    safe_mode_required: bool | None = None
    next_scheduled_run_at: datetime | None = None
    details_json: dict[str, Any] | None = None


class HuntScheduleCreateRequest(BaseModel):
    program_id: UUID
    scope_target_id: UUID
    workflow_template: str = Field(..., min_length=1, max_length=255)
    schedule_type: str = Field(default="interval", pattern="^(interval|cron)$")
    interval_minutes: int | None = Field(default=60, ge=1)
    cron_expr: str | None = None
    safe_mode: bool = True
    dry_run: bool = False
    priority_tier: int = Field(default=3, ge=1, le=5)
    max_concurrency: int = Field(default=1, ge=1, le=32)
    cooldown_minutes: int = Field(default=60, ge=0, le=10080)
    failure_backoff_minutes: int = Field(default=240, ge=0, le=10080)
    failure_pause_threshold: int = Field(default=3, ge=1, le=100)
    next_scheduled_run_at: datetime | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field(default="operator.bugbounty", min_length=1, max_length=255)


class HuntScheduleUpdateRequest(BaseModel):
    status: str | None = Field(default=None, max_length=64)
    interval_minutes: int | None = Field(default=None, ge=1)
    cron_expr: str | None = None
    safe_mode: bool | None = None
    dry_run: bool | None = None
    max_concurrency: int | None = Field(default=None, ge=1, le=32)
    cooldown_minutes: int | None = Field(default=None, ge=0, le=10080)
    failure_backoff_minutes: int | None = Field(default=None, ge=0, le=10080)
    failure_pause_threshold: int | None = Field(default=None, ge=1, le=100)
    next_scheduled_run_at: datetime | None = None
    paused_reason: str | None = Field(default=None, max_length=2000)
    config_json: dict[str, Any] | None = None
    updated_by: str = Field(default="operator.bugbounty", min_length=1, max_length=255)


class HuntScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID
    workflow_template: str
    schedule_type: str
    interval_minutes: int | None = None
    cron_expr: str | None = None
    status: str
    safe_mode: bool
    dry_run: bool
    priority_tier: int
    max_concurrency: int
    cooldown_minutes: int
    failure_backoff_minutes: int
    failure_pause_threshold: int
    consecutive_failures: int
    last_run_started_at: datetime | None = None
    last_run_finished_at: datetime | None = None
    last_run_status: str | None = None
    last_failure_reason: str | None = None
    next_scheduled_run_at: datetime | None = None
    paused_at: datetime | None = None
    paused_reason: str | None = None
    created_by: str | None = None
    updated_by: str | None = None
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ReadinessCheckResponse(BaseModel):
    decision_status: str
    reason: str
    details: dict[str, Any]
    record_id: UUID | None = None


class ScheduleTriggerResponse(BaseModel):
    schedule_id: UUID
    decision_status: str
    reason: str
    readiness_record_id: UUID | None = None
    campaign_id: UUID | None = None
    workflow_run_id: UUID | None = None
    run_id: str | None = None
    next_scheduled_run_at: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ScheduleDispatchResponse(BaseModel):
    schedule_id: UUID
    worker_task_id: str | None = None
    worker_role: str
    decision_status: str
    reason: str


class WorkflowDeltaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    schedule_job_id: UUID | None = None
    program_id: UUID
    scope_target_id: UUID
    workflow_run_id: UUID
    previous_workflow_run_id: UUID | None = None
    delta_type: str
    delta_key: str
    change_type: str
    severity_hint: str | None = None
    details_json: dict[str, Any]
    created_at: datetime


class AnalystQueueItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID
    workflow_run_id: UUID
    workflow_finding_id: UUID | None = None
    finding_id: UUID | None = None
    workflow_template: str
    finding_type: str | None = None
    vulnerability_type: str
    affected_asset: str
    affected_endpoint: str | None = None
    parameter: str | None = None
    evidence_summary: str | None = None
    confidence_score: float | None = None
    severity_hint: str | None = None
    novelty_score: float | None = None
    reportability_score: float | None = None
    duplicate_risk_hint: str | None = None
    policy_fit_status: str | None = None
    status: str
    artifact_ref: str | None = None
    assigned_to: str | None = None
    last_transition_at: datetime | None = None
    details_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CandidateQueueUpdateRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=64)
    assigned_to: str | None = Field(default=None, max_length=255)
    analyst_notes: str | None = Field(default=None, max_length=4000)
    actor: str = Field(default="operator.bugbounty.queue", min_length=1, max_length=255)


class SchedulerStatusResponse(BaseModel):
    total_schedules: int
    active_schedules: int
    paused_schedules: int
    disabled_schedules: int
    error_schedules: int
    due_schedules: int
    blocked_readiness_last_24h: int
    ready_readiness_last_24h: int


class GenerateReportDraftRequest(BaseModel):
    actor: str = Field(default="operator.report_draft", min_length=1, max_length=255)
    analyst_notes: str | None = None


class GenerateReportDraftResponse(BaseModel):
    queue_item_id: UUID
    submission_draft_id: UUID
    artifact_id: UUID
    draft_path: str
    status: str


class InferenceRunRequest(BaseModel):
    actor: str = Field(default="operator.phase6.inference", min_length=1, max_length=255)
    program_id: UUID | None = None
    apply_adaptive: bool = True


class InferenceRunResponse(BaseModel):
    created_signals: int
    considered_records: int
    scores_created: int
    swarm_records_created: int
    adaptive_actions_applied: int


class SignalIntelligenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    source: str
    source_record_id: str | None = None
    signal_type: str
    signal_key: str
    confidence_score: float | None = None
    severity_hint: str | None = None
    evidence_refs_json: list[str]
    correlation_refs_json: list[str]
    details_json: dict[str, Any]
    observed_at: datetime
    created_at: datetime
    updated_at: datetime


class OpportunityInferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    recommended_workflow: str
    next_best_action: str
    opportunity_score: float
    target_priority_score: float
    reasoning_summary: str
    supporting_evidence_json: list[str]
    details_json: dict[str, Any]
    inferred_at: datetime
    created_at: datetime
    updated_at: datetime


class SwarmReasoningRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    opportunity_inference_id: UUID | None = None
    agent_role: str
    confidence_score: float | None = None
    output_json: dict[str, Any]
    details_json: dict[str, Any]
    reasoned_at: datetime
    created_at: datetime
    updated_at: datetime


class AdaptiveScheduleActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID | None = None
    schedule_job_id: UUID | None = None
    opportunity_inference_id: UUID | None = None
    action_type: str
    action_status: str
    reason: str
    details_json: dict[str, Any]
    executed_at: datetime
    created_at: datetime
    updated_at: datetime


class AnalystBriefingResponse(BaseModel):
    generated_at: str
    top_targets: list[dict[str, Any]]
    top_candidates: list[dict[str, Any]]
    adaptive_actions: list[dict[str, Any]]
