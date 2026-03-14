import type { AuditEvent } from "@/lib/types/api";

export type CandidateQueueStatus =
  | "new"
  | "acknowledged"
  | "triaged"
  | "needs_manual_validation"
  | "ready_for_report"
  | "dismissed"
  | "duplicate_suspected"
  | "submitted_externally";

export type ReadinessDecisionStatus =
  | "READY"
  | "BLOCKED_BY_SCOPE"
  | "BLOCKED_BY_PROGRAM_POLICY"
  | "BLOCKED_BY_HEALTH"
  | "BLOCKED_BY_CONFIG"
  | "BLOCKED_BY_COOLDOWN"
  | "BLOCKED_BY_DISABLED_TARGET"
  | "BLOCKED_BY_SAFETY_POLICY";

export type AlertSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type AlertUrgency = "LOW" | "MEDIUM" | "HIGH" | "IMMEDIATE";
export type AlertStatus = "OPEN" | "ACKNOWLEDGED" | "SUPPRESSED" | "RESOLVED";

export type CaseStatus =
  | "new"
  | "acknowledged"
  | "triaging"
  | "needs_manual_validation"
  | "ready_for_report"
  | "dismissed"
  | "duplicate"
  | "escalated"
  | "submitted"
  | "closed";

export type CasePriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type ProgramOpportunity = {
  id: string;
  program_key: string | null;
  name: string;
  platform: string | null;
  handle: string | null;
  status: string;
  policy_url: string | null;
  created_by: string | null;
  config_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type MonitoredTarget = {
  id: string;
  program_id: string;
  target: string;
  target_type: string;
  is_in_scope: boolean;
  monitoring_enabled: boolean;
  monitoring_priority_tier: number;
  monitoring_status: string;
  monitoring_source: string | null;
  monitoring_notes: string | null;
  safe_mode_required: boolean;
  last_checked_at: string | null;
  last_success_at: string | null;
  last_failure_at: string | null;
  next_scheduled_run_at: string | null;
  details_json: Record<string, unknown>;
};

export type HuntSchedule = {
  id: string;
  program_id: string;
  scope_target_id: string;
  workflow_template: string;
  schedule_type: string;
  interval_minutes: number | null;
  cron_expr: string | null;
  status: string;
  safe_mode: boolean;
  dry_run: boolean;
  priority_tier: number;
  max_concurrency: number;
  cooldown_minutes: number;
  failure_backoff_minutes: number;
  failure_pause_threshold: number;
  consecutive_failures: number;
  last_run_started_at: string | null;
  last_run_finished_at: string | null;
  last_run_status: string | null;
  last_failure_reason: string | null;
  next_scheduled_run_at: string | null;
  paused_at: string | null;
  paused_reason: string | null;
  created_by: string | null;
  updated_by: string | null;
  config_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type SchedulerStatus = {
  total_schedules: number;
  active_schedules: number;
  paused_schedules: number;
  disabled_schedules: number;
  error_schedules: number;
  due_schedules: number;
  blocked_readiness_last_24h: number;
  ready_readiness_last_24h: number;
};

export type ReadinessRecord = {
  decision_status: ReadinessDecisionStatus;
  reason: string;
  details: Record<string, unknown>;
  record_id: string | null;
};

export type WorkflowDelta = {
  id: string;
  schedule_job_id: string | null;
  program_id: string;
  scope_target_id: string;
  workflow_run_id: string;
  previous_workflow_run_id: string | null;
  delta_type: string;
  delta_key: string;
  change_type: string;
  severity_hint: string | null;
  details_json: Record<string, unknown>;
  created_at: string;
};

export type CandidateQueueItem = {
  id: string;
  program_id: string;
  scope_target_id: string;
  workflow_run_id: string;
  workflow_finding_id: string | null;
  finding_id: string | null;
  workflow_template: string;
  finding_type: string | null;
  vulnerability_type: string;
  affected_asset: string;
  affected_endpoint: string | null;
  parameter: string | null;
  evidence_summary: string | null;
  confidence_score: number | null;
  severity_hint: string | null;
  novelty_score: number | null;
  reportability_score: number | null;
  duplicate_risk_hint: string | null;
  policy_fit_status: string | null;
  status: CandidateQueueStatus;
  artifact_ref: string | null;
  assigned_to: string | null;
  last_transition_at: string | null;
  details_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type NotificationAlert = {
  id: string;
  program_id: string;
  scope_target_id: string | null;
  workflow_run_id: string | null;
  analyst_queue_item_id: string | null;
  prediction_record_id: string | null;
  recommendation_record_id: string | null;
  submission_draft_id: string | null;
  alert_type: string;
  severity: AlertSeverity;
  urgency: AlertUrgency;
  alert_fingerprint: string;
  summary: string;
  reasoning_summary: string | null;
  supporting_signal_ids_json: string[];
  supporting_record_ids_json: string[];
  status: AlertStatus;
  occurrence_count: number;
  first_seen_at: string;
  last_seen_at: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  details_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type AlertCaseSummary = {
  unresolved_alert_count: number;
  high_severity_alert_count: number;
  open_case_count: number;
  ready_for_report_case_count: number;
  stale_unowned_case_count: number;
};

export type AlertSyncResponse = {
  scanned_sources: number;
  created_alerts: number;
  updated_alerts: number;
  suppressed_alerts: number;
};

export type AnalystCase = {
  id: string;
  program_id: string;
  scope_target_id: string | null;
  workflow_run_id: string | null;
  alert_id: string | null;
  analyst_queue_item_id: string | null;
  prediction_record_id: string | null;
  recommendation_record_id: string | null;
  submission_draft_id: string | null;
  title: string;
  summary: string;
  reasoning_summary: string | null;
  priority: CasePriority;
  status: CaseStatus;
  owner: string | null;
  last_actor: string | null;
  assigned_at: string | null;
  last_transition_at: string | null;
  closed_at: string | null;
  closure_reason: string | null;
  evidence_refs_json: string[];
  triage_notes_json: Array<Record<string, unknown>>;
  details_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type SignalIntelligence = {
  id: string;
  program_id: string;
  scope_target_id: string | null;
  workflow_run_id: string | null;
  source: string;
  source_record_id: string | null;
  signal_type: string;
  signal_key: string;
  confidence_score: number | null;
  severity_hint: string | null;
  evidence_refs_json: string[];
  correlation_refs_json: string[];
  details_json: Record<string, unknown>;
  observed_at: string;
  created_at: string;
  updated_at: string;
};

export type OpportunityInference = {
  id: string;
  program_id: string;
  scope_target_id: string | null;
  workflow_run_id: string | null;
  recommended_workflow: string;
  next_best_action: string;
  opportunity_score: number;
  target_priority_score: number;
  reasoning_summary: string;
  supporting_evidence_json: string[];
  details_json: Record<string, unknown>;
  inferred_at: string;
  created_at: string;
  updated_at: string;
};

export type AdaptiveScheduleAction = {
  id: string;
  program_id: string;
  scope_target_id: string | null;
  schedule_job_id: string | null;
  opportunity_inference_id: string | null;
  action_type: string;
  action_status: string;
  reason: string;
  details_json: Record<string, unknown>;
  executed_at: string;
  created_at: string;
  updated_at: string;
};

export type AnalystBriefing = {
  generated_at: string;
  top_targets: Array<{
    program_id: string;
    scope_target_id: string | null;
    opportunity_score: number;
    target_priority_score: number;
    recommended_workflow: string;
    next_best_action: string;
  }>;
  top_candidates: Array<{
    queue_item_id: string;
    affected_asset: string;
    vulnerability_type: string;
    reportability_score: number | null;
    status: string;
  }>;
  adaptive_actions: Array<{
    action_id: string;
    action_status: string;
    action_type: string;
    reason: string;
  }>;
};

export type TargetYieldScore = {
  id: string;
  program_id: string;
  scope_target_id: string | null;
  workflow_run_id: string | null;
  signal_density_score: number;
  novelty_score: number;
  coverage_quality_score: number;
  candidate_quality_score: number;
  duplicate_penalty_score: number;
  confidence_score: number;
  yield_score: number;
  details_json: Record<string, unknown>;
  scored_at: string;
  created_at: string;
  updated_at: string;
};

export type DuplicateRisk = {
  id: string;
  program_id: string;
  scope_target_id: string | null;
  workflow_run_id: string | null;
  analyst_queue_item_id: string | null;
  candidate_key: string;
  duplicate_risk_score: number;
  risk_band: string;
  reasoning_summary: string;
  supporting_signal_ids_json: string[];
  details_json: Record<string, unknown>;
  assessed_at: string;
  created_at: string;
  updated_at: string;
};

export type EvidenceCompleteness = {
  id: string;
  program_id: string;
  scope_target_id: string | null;
  workflow_run_id: string | null;
  analyst_queue_item_id: string | null;
  candidate_key: string;
  evidence_completeness_score: number;
  readiness_state: string;
  missing_fields_json: string[];
  reasoning_summary: string;
  details_json: Record<string, unknown>;
  assessed_at: string;
  created_at: string;
  updated_at: string;
};

export type VulnerabilityPrediction = {
  id: string;
  program_id: string;
  scope_target_id: string | null;
  workflow_run_id: string | null;
  analyst_queue_item_id: string | null;
  predicted_vulnerability_type: string;
  confidence_score: number;
  novelty_score: number;
  duplicate_risk_score: number;
  reportability_score: number;
  evidence_completeness_score: number;
  opportunity_score: number;
  recommended_next_workflow: string;
  recommended_follow_up_action: string;
  reasoning_summary: string;
  supporting_signal_ids_json: string[];
  details_json: Record<string, unknown>;
  predicted_at: string;
  created_at: string;
  updated_at: string;
};

export type OpportunitySelection = {
  id: string;
  program_id: string;
  scope_target_id: string | null;
  workflow_run_id: string | null;
  analyst_queue_item_id: string | null;
  subject_type: string;
  subject_key: string;
  selection_score: number;
  priority_rank: number | null;
  confidence_score: number | null;
  duplicate_risk_score: number | null;
  evidence_completeness_score: number | null;
  reasoning_summary: string;
  details_json: Record<string, unknown>;
  scored_at: string;
  created_at: string;
  updated_at: string;
};

export type WorkflowRecommendation = {
  id: string;
  program_id: string;
  scope_target_id: string | null;
  workflow_run_id: string | null;
  analyst_queue_item_id: string | null;
  prediction_record_id: string | null;
  selection_record_id: string | null;
  target_yield_score_id: string | null;
  recommended_workflow: string;
  recommended_action: string;
  action_priority: number;
  recommendation_status: string;
  reasoning_summary: string;
  supporting_record_ids_json: string[];
  details_json: Record<string, unknown>;
  recommended_at: string;
  created_at: string;
  updated_at: string;
};

export type Phase7AnalystSupport = {
  generated_at: string;
  top_predictions: Array<{
    prediction_id: string;
    program_id: string;
    scope_target_id: string | null;
    predicted_vulnerability_type: string;
    reportability_score: number;
    duplicate_risk_score: number;
    evidence_completeness_score: number;
    recommended_next_workflow: string;
    recommended_follow_up_action: string;
  }>;
  top_target_yields: Array<{
    yield_record_id: string;
    program_id: string;
    scope_target_id: string | null;
    yield_score: number;
    confidence_score: number;
  }>;
  top_recommendations: Array<{
    recommendation_id: string;
    recommended_workflow: string;
    recommended_action: string;
    recommendation_status: string;
    action_priority: number;
  }>;
};

export type Phase7RunResponse = {
  predictions_created: number;
  rankings_created: number;
  recommendations_created: number;
  yield_scores_created: number;
  duplicate_records_created: number;
  evidence_records_created: number;
  adaptive_actions_applied: number;
};

export type RetrospectiveRunResponse = {
  feedback_signals_recorded: number;
  decision_outcomes_recorded: number;
  workflow_performance_records_created: number;
  target_performance_records_created: number;
  recommendation_outcomes_recorded: number;
  alert_outcomes_recorded: number;
};

export type RetrospectiveSummary = {
  generated_at: string;
  window_days: number;
  top_programs: Array<Record<string, unknown>>;
  top_targets: Array<Record<string, unknown>>;
  workflow_value_leaders: Array<Record<string, unknown>>;
  alert_noise_summary: Record<string, unknown>;
  recommendation_success_summary: Record<string, unknown>;
};

export type WorkflowPerformance = {
  id: string;
  program_id: string;
  workflow_template: string;
  window_start: string;
  window_end: string;
  signals_generated: number;
  candidates_produced: number;
  cases_created: number;
  reportable_outcomes: number;
  duplicate_outcomes: number;
  dismissed_outcomes: number;
  workflow_signal_value: number;
  workflow_reportability_rate: number;
  workflow_noise_rate: number;
  details_json: Record<string, unknown>;
  computed_at: string;
  created_at: string;
  updated_at: string;
};

export type TargetPerformance = {
  id: string;
  program_id: string;
  scope_target_id: string | null;
  window_start: string;
  window_end: string;
  signal_count: number;
  candidate_count: number;
  case_count: number;
  reportable_count: number;
  duplicate_count: number;
  dismissed_count: number;
  target_signal_rate: number;
  target_duplicate_rate: number;
  target_reportability_rate: number;
  target_yield_score: number;
  details_json: Record<string, unknown>;
  computed_at: string;
  created_at: string;
  updated_at: string;
};

export type RecommendationOutcome = {
  id: string;
  program_id: string;
  recommendation_record_id: string;
  scope_target_id: string | null;
  workflow_run_id: string | null;
  analyst_case_id: string | null;
  outcome_status: string;
  success_score: number;
  reasoning_summary: string | null;
  details_json: Record<string, unknown>;
  decided_at: string;
  created_at: string;
  updated_at: string;
};

export type AlertOutcome = {
  id: string;
  program_id: string;
  alert_id: string;
  scope_target_id: string | null;
  analyst_case_id: string | null;
  outcome_status: string;
  acknowledgement_latency_seconds: number | null;
  led_to_case: boolean;
  led_to_reportable: boolean;
  reasoning_summary: string | null;
  details_json: Record<string, unknown>;
  evaluated_at: string;
  created_at: string;
  updated_at: string;
};

export type ToolHealthSummary = {
  total: number;
  healthy: number;
  degraded: number;
  unavailable: number;
  unchecked: number;
  total_tools: number;
  healthy_tools: number;
  tools_missing_binary: number;
  tools_missing_credentials: number;
  tools_with_failed_verification: number;
};

export type ToolHealthDashboard = {
  status: string;
  timestamp: string;
  total_tools: number;
  generated_at: string;
  install_timeout_seconds: number;
  summary: ToolHealthSummary;
  by_category: Record<string, ToolHealthSummary>;
  tools: Array<{
    tool_name: string;
    category: string;
    enabled: boolean;
    execution_mode: string;
    credential_status: string;
    install_verification_status: string;
    wrapper_smoke_test_status: string;
    safe_mode_compatibility: { compatible: boolean; requires_override: boolean; detail: string };
    last_execution_status: string | null;
    last_failure_reason: string | null;
  }>;
  report_path: string | null;
};

export type ToolHealthEnvelope = {
  success: boolean;
  data: ToolHealthDashboard;
  error?: string | null;
  message?: string | null;
  timestamp?: string;
  status_code?: number;
};

export type CandidateQueueUpdateRequest = {
  status: CandidateQueueStatus;
  assigned_to?: string;
  analyst_notes?: string;
  actor?: string;
};

export type CandidateQueueReportDraftResponse = {
  queue_item_id: string;
  submission_draft_id: string;
  artifact_id: string;
  draft_path: string;
  status: string;
};

export type BountyTimelineEvent = AuditEvent;

export type AgentRegistryRecord = {
  id: string;
  agent_id: string;
  agent_name: string;
  agent_role: string;
  category: string;
  purpose: string;
  allowed_tools_json: string[];
  forbidden_tools_json: string[];
  input_schema_reference: string;
  output_schema_reference: string;
  model_preference: string;
  model_runtime: string;
  confidence_threshold: number;
  max_runtime_seconds: number;
  retry_policy_json: Record<string, unknown>;
  escalation_agent_id: string | null;
  enabled: boolean;
  safety_notes: string | null;
  observability_tags_json: string[];
  details_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type AgentExecutionRecord = {
  id: string;
  agent_registry_id: string | null;
  agent_id: string;
  program_id: string;
  scope_target_id: string | null;
  workflow_run_id: string | null;
  analyst_case_id: string | null;
  analyst_queue_item_id: string | null;
  input_ref: string | null;
  input_hash: string | null;
  output_json: Record<string, unknown>;
  model_used: string;
  routing_policy: string;
  confidence: number | null;
  execution_status: string;
  failure_reason: string | null;
  escalation_taken: boolean;
  escalation_agent_id: string | null;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  log_path: string | null;
  artifact_refs_json: string[];
  details_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type AgentEvaluationRecord = {
  id: string;
  agent_registry_id: string | null;
  agent_id: string;
  benchmark_name: string;
  model_used: string;
  fixture_count: number;
  passed_count: number;
  failed_count: number;
  avg_confidence: number | null;
  avg_latency_ms: number | null;
  success_rate: number;
  status: string;
  results_json: Record<string, unknown>;
  run_by: string | null;
  run_reason: string | null;
  executed_at: string;
  created_at: string;
  updated_at: string;
};

export type AgentRegistrySyncResponse = {
  created: number;
  updated: number;
  total: number;
};
