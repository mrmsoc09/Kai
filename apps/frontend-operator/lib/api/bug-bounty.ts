import { ApiError, requestJson } from "@/lib/api/client";
import type {
  AdaptiveScheduleAction,
  AgentEvaluationRecord,
  AgentExecutionRecord,
  AgentRegistryRecord,
  AgentRegistrySyncResponse,
  AlertCaseSummary,
  AlertSyncResponse,
  AnalystCase,
  AnalystBriefing,
  CandidateQueueItem,
  CandidateQueueReportDraftResponse,
  CandidateQueueUpdateRequest,
  DuplicateRisk,
  EvidenceCompleteness,
  HuntSchedule,
  MonitoredTarget,
  NotificationAlert,
  OpportunityInference,
  OpportunitySelection,
  RetrospectiveRunResponse,
  RetrospectiveSummary,
  Phase7AnalystSupport,
  Phase7RunResponse,
  ProgramOpportunity,
  RecommendationOutcome,
  ReadinessRecord,
  SchedulerStatus,
  SignalIntelligence,
  TargetYieldScore,
  TargetPerformance,
  ToolHealthEnvelope,
  AlertOutcome,
  VulnerabilityPrediction,
  WorkflowPerformance,
  WorkflowDelta,
  WorkflowRecommendation
} from "@/lib/types";

function withQuery(
  path: string,
  params: Record<string, string | number | boolean | undefined | null>
): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    query.set(key, String(value));
  }
  const suffix = query.toString();
  return suffix ? `${path}?${suffix}` : path;
}

function ensureArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function normalizeAnalystBriefing(value: AnalystBriefing | null | undefined): AnalystBriefing {
  return {
    generated_at: value?.generated_at ?? new Date().toISOString(),
    top_targets: ensureArray(value?.top_targets),
    top_candidates: ensureArray(value?.top_candidates),
    adaptive_actions: ensureArray(value?.adaptive_actions)
  };
}

function normalizePhase7AnalystSupport(value: Phase7AnalystSupport | null | undefined): Phase7AnalystSupport {
  return {
    generated_at: value?.generated_at ?? new Date().toISOString(),
    top_predictions: ensureArray(value?.top_predictions),
    top_target_yields: ensureArray(value?.top_target_yields),
    top_recommendations: ensureArray(value?.top_recommendations)
  };
}

function normalizeRetrospectiveSummary(
  value: RetrospectiveSummary | null | undefined,
  windowDays = 30
): RetrospectiveSummary {
  return {
    generated_at: value?.generated_at ?? new Date().toISOString(),
    window_days: value?.window_days ?? windowDays,
    top_programs: ensureArray(value?.top_programs),
    top_targets: ensureArray(value?.top_targets),
    workflow_value_leaders: ensureArray(value?.workflow_value_leaders),
    alert_noise_summary:
      value?.alert_noise_summary && typeof value.alert_noise_summary === "object"
        ? value.alert_noise_summary
        : {},
    recommendation_success_summary:
      value?.recommendation_success_summary &&
      typeof value.recommendation_success_summary === "object"
        ? value.recommendation_success_summary
        : {}
  };
}

export function listBountyPrograms(signal?: AbortSignal) {
  return requestJson<ProgramOpportunity[]>("/api/v1/bug-bounty/programs", { signal }).then(ensureArray);
}

export function listMonitoredTargets(programId: string, signal?: AbortSignal) {
  return requestJson<MonitoredTarget[]>(
    `/api/v1/bug-bounty/programs/${programId}/targets`,
    { signal }
  ).then(ensureArray);
}

export function listSchedules(params?: { programId?: string; status?: string; signal?: AbortSignal }) {
  return requestJson<HuntSchedule[]>(
    withQuery("/api/v1/bug-bounty/schedules", {
      program_id: params?.programId,
      status: params?.status
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function getSchedulerStatus(params?: { programId?: string; signal?: AbortSignal }) {
  return requestJson<SchedulerStatus>(
    withQuery("/api/v1/bug-bounty/schedules/status", { program_id: params?.programId }),
    { signal: params?.signal }
  );
}

export function listReadinessRecords(params?: {
  programId?: string;
  decisionStatus?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<ReadinessRecord[]>(
    withQuery("/api/v1/bug-bounty/readiness-records", {
      program_id: params?.programId,
      decision_status: params?.decisionStatus,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function listDeltas(params?: {
  programId?: string;
  scopeTargetId?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<WorkflowDelta[]>(
    withQuery("/api/v1/bug-bounty/deltas", {
      program_id: params?.programId,
      scope_target_id: params?.scopeTargetId,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function listCandidateQueue(params?: {
  programId?: string;
  status?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<CandidateQueueItem[]>(
    withQuery("/api/v1/bug-bounty/candidates", {
      program_id: params?.programId,
      status: params?.status,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function syncAlerts(body?: { actor?: string; program_id?: string; cooldown_minutes?: number }) {
  return requestJson<AlertSyncResponse>("/api/v1/bug-bounty/alerts/sync", {
    method: "POST",
    body
  });
}

export function listAlerts(params?: {
  programId?: string;
  status?: string;
  severity?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<NotificationAlert[]>(
    withQuery("/api/v1/bug-bounty/alerts", {
      program_id: params?.programId,
      status: params?.status,
      severity: params?.severity,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function getAlertCaseSummary(params?: { programId?: string; signal?: AbortSignal }) {
  return requestJson<AlertCaseSummary>(
    withQuery("/api/v1/bug-bounty/alerts/summary", {
      program_id: params?.programId
    }),
    { signal: params?.signal }
  );
}

export function acknowledgeAlert(alertId: string, body?: { actor?: string; note?: string }) {
  return requestJson<NotificationAlert>(`/api/v1/bug-bounty/alerts/${alertId}/acknowledge`, {
    method: "POST",
    body
  });
}

export function resolveAlert(alertId: string, body?: { actor?: string; note?: string }) {
  return requestJson<NotificationAlert>(`/api/v1/bug-bounty/alerts/${alertId}/resolve`, {
    method: "POST",
    body
  });
}

export function createCaseFromAlert(alertId: string, body?: { actor?: string; owner?: string }) {
  return requestJson<AnalystCase>(`/api/v1/bug-bounty/alerts/${alertId}/case`, {
    method: "POST",
    body
  });
}

export function listCases(params?: {
  programId?: string;
  status?: string;
  priority?: string;
  owner?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<AnalystCase[]>(
    withQuery("/api/v1/bug-bounty/cases", {
      program_id: params?.programId,
      status: params?.status,
      priority: params?.priority,
      owner: params?.owner,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function getCase(caseId: string, signal?: AbortSignal) {
  return requestJson<AnalystCase>(`/api/v1/bug-bounty/cases/${caseId}`, { signal });
}

export function createCase(body: {
  actor?: string;
  program_id: string;
  title: string;
  summary: string;
  priority?: string;
  owner?: string;
  alert_id?: string;
  analyst_queue_item_id?: string;
  prediction_record_id?: string;
  recommendation_record_id?: string;
  submission_draft_id?: string;
  scope_target_id?: string;
  workflow_run_id?: string;
  reasoning_summary?: string;
  evidence_refs_json?: string[];
}) {
  return requestJson<AnalystCase>("/api/v1/bug-bounty/cases", {
    method: "POST",
    body
  });
}

export function updateCase(
  caseId: string,
  body: {
    actor?: string;
    status?: string;
    priority?: string;
    summary?: string;
    reasoning_summary?: string;
    closure_reason?: string;
  }
) {
  return requestJson<AnalystCase>(`/api/v1/bug-bounty/cases/${caseId}`, {
    method: "PATCH",
    body
  });
}

export function assignCase(caseId: string, body: { owner: string; actor?: string }) {
  return requestJson<AnalystCase>(`/api/v1/bug-bounty/cases/${caseId}/assign`, {
    method: "POST",
    body
  });
}

export function addCaseNote(caseId: string, body: { note: string; actor?: string }) {
  return requestJson<AnalystCase>(`/api/v1/bug-bounty/cases/${caseId}/notes`, {
    method: "POST",
    body
  });
}

export function updateCandidateQueueItem(queueItemId: string, body: CandidateQueueUpdateRequest) {
  return requestJson<CandidateQueueItem>(`/api/v1/bug-bounty/candidates/${queueItemId}`, {
    method: "PATCH",
    body
  });
}

export function generateCandidateReportDraft(
  queueItemId: string,
  body?: { actor?: string; analyst_notes?: string }
) {
  return requestJson<CandidateQueueReportDraftResponse>(
    `/api/v1/bug-bounty/candidates/${queueItemId}/report-draft`,
    {
      method: "POST",
      body
    }
  );
}

export function listSignals(params?: {
  programId?: string;
  scopeTargetId?: string;
  signalType?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<SignalIntelligence[]>(
    withQuery("/api/v1/bug-bounty/signals", {
      program_id: params?.programId,
      scope_target_id: params?.scopeTargetId,
      signal_type: params?.signalType,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function listOpportunityScores(params?: {
  programId?: string;
  scopeTargetId?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<OpportunityInference[]>(
    withQuery("/api/v1/bug-bounty/opportunity-scores", {
      program_id: params?.programId,
      scope_target_id: params?.scopeTargetId,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function listAdaptiveActions(params?: {
  programId?: string;
  actionStatus?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<AdaptiveScheduleAction[]>(
    withQuery("/api/v1/bug-bounty/adaptive-actions", {
      program_id: params?.programId,
      action_status: params?.actionStatus,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function getAnalystBriefing(params?: { programId?: string; limit?: number; signal?: AbortSignal }) {
  return requestJson<AnalystBriefing>(
    withQuery("/api/v1/bug-bounty/analyst-briefing", {
      program_id: params?.programId,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(normalizeAnalystBriefing);
}

export function runPhase7(body?: { actor?: string; program_id?: string; apply_adaptive?: boolean }) {
  return requestJson<Phase7RunResponse>("/api/v1/bug-bounty/phase7/run", {
    method: "POST",
    body
  });
}

export function listPhase7Predictions(params?: {
  programId?: string;
  scopeTargetId?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<VulnerabilityPrediction[]>(
    withQuery("/api/v1/bug-bounty/phase7/predictions", {
      program_id: params?.programId,
      scope_target_id: params?.scopeTargetId,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function listPhase7OpportunityRankings(params?: {
  programId?: string;
  subjectType?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<OpportunitySelection[]>(
    withQuery("/api/v1/bug-bounty/phase7/opportunity-rankings", {
      program_id: params?.programId,
      subject_type: params?.subjectType,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function listPhase7TargetYields(params?: {
  programId?: string;
  scopeTargetId?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<TargetYieldScore[]>(
    withQuery("/api/v1/bug-bounty/phase7/target-yields", {
      program_id: params?.programId,
      scope_target_id: params?.scopeTargetId,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function listPhase7DuplicateRisk(params?: {
  programId?: string;
  riskBand?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<DuplicateRisk[]>(
    withQuery("/api/v1/bug-bounty/phase7/duplicate-risk", {
      program_id: params?.programId,
      risk_band: params?.riskBand,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function listPhase7EvidenceCompleteness(params?: {
  programId?: string;
  readinessState?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<EvidenceCompleteness[]>(
    withQuery("/api/v1/bug-bounty/phase7/evidence-completeness", {
      program_id: params?.programId,
      readiness_state: params?.readinessState,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function listPhase7Recommendations(params?: {
  programId?: string;
  recommendationStatus?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<WorkflowRecommendation[]>(
    withQuery("/api/v1/bug-bounty/phase7/recommendations", {
      program_id: params?.programId,
      recommendation_status: params?.recommendationStatus,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function getPhase7AnalystSupport(params?: { programId?: string; limit?: number; signal?: AbortSignal }) {
  return requestJson<Phase7AnalystSupport>(
    withQuery("/api/v1/bug-bounty/phase7/analyst-support", {
      program_id: params?.programId,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(normalizePhase7AnalystSupport);
}

export function runRetrospective(body?: { actor?: string; program_id?: string; window_days?: number }) {
  return requestJson<RetrospectiveRunResponse>("/api/v1/bug-bounty/retrospective/run", {
    method: "POST",
    body
  });
}

export function getRetrospectiveSummary(params?: {
  programId?: string;
  windowDays?: number;
  signal?: AbortSignal;
}) {
  return requestJson<RetrospectiveSummary>(
    withQuery("/api/v1/bug-bounty/retrospective/summary", {
      program_id: params?.programId,
      window_days: params?.windowDays
    }),
    { signal: params?.signal }
  ).then((value) => normalizeRetrospectiveSummary(value, params?.windowDays ?? 30));
}

export function listRetrospectiveWorkflows(params?: {
  programId?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<WorkflowPerformance[]>(
    withQuery("/api/v1/bug-bounty/retrospective/workflows", {
      program_id: params?.programId,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function listRetrospectiveTargets(params?: {
  programId?: string;
  scopeTargetId?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<TargetPerformance[]>(
    withQuery("/api/v1/bug-bounty/retrospective/targets", {
      program_id: params?.programId,
      scope_target_id: params?.scopeTargetId,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function listRetrospectiveRecommendations(params?: {
  programId?: string;
  outcomeStatus?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<RecommendationOutcome[]>(
    withQuery("/api/v1/bug-bounty/retrospective/recommendations", {
      program_id: params?.programId,
      outcome_status: params?.outcomeStatus,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function listRetrospectiveAlerts(params?: {
  programId?: string;
  outcomeStatus?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<AlertOutcome[]>(
    withQuery("/api/v1/bug-bounty/retrospective/alerts", {
      program_id: params?.programId,
      outcome_status: params?.outcomeStatus,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export async function getToolsHealth(params?: { signal?: AbortSignal; runSmokeTests?: boolean }) {
  const response = await requestJson<ToolHealthEnvelope>(
    withQuery("/api/v1/tools/health", {
      run_smoke_tests: params?.runSmokeTests ?? false
    }),
    { signal: params?.signal }
  );
  if (!response.success || !response.data) {
    throw new ApiError(500, { detail: "Tool health response envelope was missing data." });
  }
  return response.data;
}

export function syncAgentRegistry() {
  return requestJson<AgentRegistrySyncResponse>("/api/v1/bug-bounty/agents/sync", {
    method: "POST",
    body: {}
  });
}

export function listAgents(params?: {
  enabledOnly?: boolean;
  category?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<AgentRegistryRecord[]>(
    withQuery("/api/v1/bug-bounty/agents", {
      enabled_only: params?.enabledOnly,
      category: params?.category,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function getAgent(agentId: string, signal?: AbortSignal) {
  return requestJson<AgentRegistryRecord>(`/api/v1/bug-bounty/agents/${agentId}`, { signal });
}

export function listAgentExecutions(params?: {
  programId?: string;
  agentId?: string;
  executionStatus?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<AgentExecutionRecord[]>(
    withQuery("/api/v1/bug-bounty/agents/executions", {
      program_id: params?.programId,
      agent_id: params?.agentId,
      execution_status: params?.executionStatus,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function listAgentEvaluations(params?: {
  agentId?: string;
  status?: string;
  limit?: number;
  signal?: AbortSignal;
}) {
  return requestJson<AgentEvaluationRecord[]>(
    withQuery("/api/v1/bug-bounty/agents/evaluations", {
      agent_id: params?.agentId,
      status: params?.status,
      limit: params?.limit
    }),
    { signal: params?.signal }
  ).then(ensureArray);
}

export function runAgent(
  agentId: string,
  body?: {
    actor?: string;
    input_payload?: Record<string, unknown>;
    program_id?: string;
    scope_target_id?: string;
    workflow_run_id?: string;
    analyst_case_id?: string;
    analyst_queue_item_id?: string;
  }
) {
  return requestJson<AgentExecutionRecord>(`/api/v1/bug-bounty/agents/${agentId}/run`, {
    method: "POST",
    body
  });
}

export function evaluateAgent(
  agentId: string,
  body?: { actor?: string; benchmark_name?: string }
) {
  return requestJson<AgentEvaluationRecord>(`/api/v1/bug-bounty/agents/${agentId}/evaluate`, {
    method: "POST",
    body
  });
}

export const bugBountyApi = {
  listBountyPrograms,
  listMonitoredTargets,
  listSchedules,
  getSchedulerStatus,
  listReadinessRecords,
  listDeltas,
  listCandidateQueue,
  syncAlerts,
  listAlerts,
  getAlertCaseSummary,
  acknowledgeAlert,
  resolveAlert,
  createCaseFromAlert,
  listCases,
  getCase,
  createCase,
  updateCase,
  assignCase,
  addCaseNote,
  updateCandidateQueueItem,
  generateCandidateReportDraft,
  listSignals,
  listOpportunityScores,
  listAdaptiveActions,
  getAnalystBriefing,
  runPhase7,
  runRetrospective,
  listPhase7Predictions,
  listPhase7OpportunityRankings,
  listPhase7TargetYields,
  listPhase7DuplicateRisk,
  listPhase7EvidenceCompleteness,
  listPhase7Recommendations,
  getPhase7AnalystSupport,
  getRetrospectiveSummary,
  listRetrospectiveWorkflows,
  listRetrospectiveTargets,
  listRetrospectiveRecommendations,
  listRetrospectiveAlerts,
  getToolsHealth,
  syncAgentRegistry,
  listAgents,
  getAgent,
  listAgentExecutions,
  listAgentEvaluations,
  runAgent,
  evaluateAgent
};
