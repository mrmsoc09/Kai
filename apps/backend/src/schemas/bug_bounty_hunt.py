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
    auto_fetch_platform_data: bool = True
    allow_partial_platform_data: bool = True
    platform_api_key: str | None = Field(default=None, max_length=2048, repr=False, exclude=True)
    platform_api_secret: str | None = Field(default=None, max_length=2048, repr=False, exclude=True)


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


class Phase7RunRequest(BaseModel):
    actor: str = Field(default="operator.phase7.prediction", min_length=1, max_length=255)
    program_id: UUID | None = None
    apply_adaptive: bool = True


class Phase7RunResponse(BaseModel):
    predictions_created: int
    rankings_created: int
    recommendations_created: int
    yield_scores_created: int
    duplicate_records_created: int
    evidence_records_created: int
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


class TargetYieldScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    signal_density_score: float
    novelty_score: float
    coverage_quality_score: float
    candidate_quality_score: float
    duplicate_penalty_score: float
    confidence_score: float
    yield_score: float
    details_json: dict[str, Any]
    scored_at: datetime
    created_at: datetime
    updated_at: datetime


class DuplicateRiskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    analyst_queue_item_id: UUID | None = None
    candidate_key: str
    duplicate_risk_score: float
    risk_band: str
    reasoning_summary: str
    supporting_signal_ids_json: list[str]
    details_json: dict[str, Any]
    assessed_at: datetime
    created_at: datetime
    updated_at: datetime


class EvidenceCompletenessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    analyst_queue_item_id: UUID | None = None
    candidate_key: str
    evidence_completeness_score: float
    readiness_state: str
    missing_fields_json: list[str]
    reasoning_summary: str
    details_json: dict[str, Any]
    assessed_at: datetime
    created_at: datetime
    updated_at: datetime


class VulnerabilityPredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    analyst_queue_item_id: UUID | None = None
    predicted_vulnerability_type: str
    confidence_score: float
    novelty_score: float
    duplicate_risk_score: float
    reportability_score: float
    evidence_completeness_score: float
    opportunity_score: float
    recommended_next_workflow: str
    recommended_follow_up_action: str
    reasoning_summary: str
    supporting_signal_ids_json: list[str]
    details_json: dict[str, Any]
    predicted_at: datetime
    created_at: datetime
    updated_at: datetime


class OpportunitySelectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    analyst_queue_item_id: UUID | None = None
    subject_type: str
    subject_key: str
    selection_score: float
    priority_rank: int | None = None
    confidence_score: float | None = None
    duplicate_risk_score: float | None = None
    evidence_completeness_score: float | None = None
    reasoning_summary: str
    details_json: dict[str, Any]
    scored_at: datetime
    created_at: datetime
    updated_at: datetime


class WorkflowRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    analyst_queue_item_id: UUID | None = None
    prediction_record_id: UUID | None = None
    selection_record_id: UUID | None = None
    target_yield_score_id: UUID | None = None
    recommended_workflow: str
    recommended_action: str
    action_priority: int
    recommendation_status: str
    reasoning_summary: str
    supporting_record_ids_json: list[str]
    details_json: dict[str, Any]
    recommended_at: datetime
    created_at: datetime
    updated_at: datetime


class AnalystBriefingResponse(BaseModel):
    generated_at: str
    top_targets: list[dict[str, Any]]
    top_candidates: list[dict[str, Any]]
    adaptive_actions: list[dict[str, Any]]


class Phase7AnalystSupportResponse(BaseModel):
    generated_at: str
    top_predictions: list[dict[str, Any]]
    top_target_yields: list[dict[str, Any]]
    top_recommendations: list[dict[str, Any]]


class AlertSyncRequest(BaseModel):
    actor: str = Field(default="operator.phase9.alerts", min_length=1, max_length=255)
    program_id: UUID | None = None
    cooldown_minutes: int = Field(default=120, ge=1, le=10080)


class AlertSyncResponse(BaseModel):
    scanned_sources: int
    created_alerts: int
    updated_alerts: int
    suppressed_alerts: int


class NotificationAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    analyst_queue_item_id: UUID | None = None
    prediction_record_id: UUID | None = None
    recommendation_record_id: UUID | None = None
    submission_draft_id: UUID | None = None
    alert_type: str
    severity: str
    urgency: str
    alert_fingerprint: str
    summary: str
    reasoning_summary: str | None = None
    supporting_signal_ids_json: list[str]
    supporting_record_ids_json: list[str]
    status: str
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    details_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AlertActionRequest(BaseModel):
    actor: str = Field(default="operator.phase9.alerts", min_length=1, max_length=255)
    note: str | None = Field(default=None, max_length=4000)


class AlertCaseCreateRequest(BaseModel):
    owner: str | None = Field(default=None, max_length=255)
    actor: str = Field(default="operator.phase9.cases", min_length=1, max_length=255)


class CaseCreateRequest(BaseModel):
    program_id: UUID
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    alert_id: UUID | None = None
    analyst_queue_item_id: UUID | None = None
    prediction_record_id: UUID | None = None
    recommendation_record_id: UUID | None = None
    submission_draft_id: UUID | None = None
    title: str = Field(..., min_length=1, max_length=500)
    summary: str = Field(..., min_length=1, max_length=4000)
    reasoning_summary: str | None = Field(default=None, max_length=4000)
    priority: str = Field(default="MEDIUM", min_length=1, max_length=32)
    owner: str | None = Field(default=None, max_length=255)
    evidence_refs_json: list[str] = Field(default_factory=list)
    actor: str = Field(default="operator.phase9.cases", min_length=1, max_length=255)


class CaseUpdateRequest(BaseModel):
    status: str | None = Field(default=None, min_length=1, max_length=64)
    priority: str | None = Field(default=None, min_length=1, max_length=32)
    summary: str | None = Field(default=None, max_length=4000)
    reasoning_summary: str | None = Field(default=None, max_length=4000)
    closure_reason: str | None = Field(default=None, max_length=4000)
    actor: str = Field(default="operator.phase9.cases", min_length=1, max_length=255)


class CaseAssignRequest(BaseModel):
    owner: str = Field(..., min_length=1, max_length=255)
    actor: str = Field(default="operator.phase9.cases", min_length=1, max_length=255)


class CaseNoteRequest(BaseModel):
    note: str = Field(..., min_length=1, max_length=4000)
    actor: str = Field(default="operator.phase9.cases", min_length=1, max_length=255)


class AnalystCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    alert_id: UUID | None = None
    analyst_queue_item_id: UUID | None = None
    prediction_record_id: UUID | None = None
    recommendation_record_id: UUID | None = None
    submission_draft_id: UUID | None = None
    title: str
    summary: str
    reasoning_summary: str | None = None
    priority: str
    status: str
    owner: str | None = None
    last_actor: str | None = None
    assigned_at: datetime | None = None
    last_transition_at: datetime | None = None
    closed_at: datetime | None = None
    closure_reason: str | None = None
    evidence_refs_json: list[str]
    triage_notes_json: list[dict[str, Any]]
    details_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RetrospectiveRunRequest(BaseModel):
    actor: str = Field(default="operator.phase10.retrospective", min_length=1, max_length=255)
    program_id: UUID | None = None
    window_days: int = Field(default=30, ge=1, le=365)


class RetrospectiveRunResponse(BaseModel):
    feedback_signals_recorded: int
    decision_outcomes_recorded: int
    workflow_performance_records_created: int
    target_performance_records_created: int
    recommendation_outcomes_recorded: int
    alert_outcomes_recorded: int


class RetrospectiveSummaryResponse(BaseModel):
    generated_at: str
    window_days: int
    top_programs: list[dict[str, Any]]
    top_targets: list[dict[str, Any]]
    workflow_value_leaders: list[dict[str, Any]]
    alert_noise_summary: dict[str, Any]
    recommendation_success_summary: dict[str, Any]


class WorkflowPerformanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    workflow_template: str
    window_start: datetime
    window_end: datetime
    signals_generated: int
    candidates_produced: int
    cases_created: int
    reportable_outcomes: int
    duplicate_outcomes: int
    dismissed_outcomes: int
    workflow_signal_value: float
    workflow_reportability_rate: float
    workflow_noise_rate: float
    details_json: dict[str, Any]
    computed_at: datetime
    created_at: datetime
    updated_at: datetime


class TargetPerformanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    scope_target_id: UUID | None = None
    window_start: datetime
    window_end: datetime
    signal_count: int
    candidate_count: int
    case_count: int
    reportable_count: int
    duplicate_count: int
    dismissed_count: int
    target_signal_rate: float
    target_duplicate_rate: float
    target_reportability_rate: float
    target_yield_score: float
    details_json: dict[str, Any]
    computed_at: datetime
    created_at: datetime
    updated_at: datetime


class RecommendationOutcomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    recommendation_record_id: UUID
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    analyst_case_id: UUID | None = None
    outcome_status: str
    success_score: float
    reasoning_summary: str | None = None
    details_json: dict[str, Any]
    decided_at: datetime
    created_at: datetime
    updated_at: datetime


class AlertOutcomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_id: UUID
    alert_id: UUID
    scope_target_id: UUID | None = None
    analyst_case_id: UUID | None = None
    outcome_status: str
    acknowledgement_latency_seconds: int | None = None
    led_to_case: bool
    led_to_reportable: bool
    reasoning_summary: str | None = None
    details_json: dict[str, Any]
    evaluated_at: datetime
    created_at: datetime
    updated_at: datetime


class AgentRegistryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: str
    agent_name: str
    agent_role: str
    category: str
    purpose: str
    allowed_tools_json: list[str]
    forbidden_tools_json: list[str]
    input_schema_reference: str
    output_schema_reference: str
    model_preference: str
    model_runtime: str
    confidence_threshold: float
    max_runtime_seconds: int
    retry_policy_json: dict[str, Any]
    escalation_agent_id: str | None = None
    enabled: bool
    safety_notes: str | None = None
    observability_tags_json: list[str]
    details_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AgentExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_registry_id: UUID | None = None
    agent_id: str
    program_id: UUID
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    analyst_case_id: UUID | None = None
    analyst_queue_item_id: UUID | None = None
    input_ref: str | None = None
    input_hash: str | None = None
    output_json: dict[str, Any]
    model_used: str
    routing_policy: str
    confidence: float | None = None
    execution_status: str
    failure_reason: str | None = None
    escalation_taken: bool
    escalation_agent_id: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    log_path: str | None = None
    artifact_refs_json: list[str]
    details_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AgentEvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_registry_id: UUID | None = None
    agent_id: str
    benchmark_name: str
    model_used: str
    fixture_count: int
    passed_count: int
    failed_count: int
    avg_confidence: float | None = None
    avg_latency_ms: int | None = None
    success_rate: float
    status: str
    results_json: dict[str, Any]
    run_by: str | None = None
    run_reason: str | None = None
    executed_at: datetime
    created_at: datetime
    updated_at: datetime


class AgentRegistrySyncResponse(BaseModel):
    created: int
    updated: int
    total: int


class AgentRunRequest(BaseModel):
    actor: str = Field(default="operator.phase10_5.agent", min_length=1, max_length=255)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    program_id: UUID | None = None
    scope_target_id: UUID | None = None
    workflow_run_id: UUID | None = None
    analyst_case_id: UUID | None = None
    analyst_queue_item_id: UUID | None = None


class AgentEvaluateRequest(BaseModel):
    actor: str = Field(default="operator.phase10_5.agent_eval", min_length=1, max_length=255)
    benchmark_name: str = Field(default="default", min_length=1, max_length=255)
