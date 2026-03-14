# Frontend API Contracts

This document defines the canonical backend endpoints for the operator console.
Source of truth is the canonical backend routers:

- `apps/backend/src/routers/campaigns.py`
- `apps/backend/src/routers/bug_bounty.py`

## Conventions

- Base path: `/api/v1`
- Response models are enforced via Pydantic `response_model` on canonical routes.
- Error semantics:
  - `400`: invalid input (for example unsupported provider)
  - `404`: referenced resource does not exist
  - `422`: valid request shape but invalid workflow/state transition
  - `500`: unexpected internal failure
- FastAPI request-shape validation errors also return `422`.

## Campaign Routes

| Endpoint | Method | Request Body | Success Response | Error Responses |
|---|---|---|---|---|
| `/api/v1/campaigns/start` | `POST` | `CampaignStartRequest` | `CampaignStartResponse` | `400`, `422`, `500` |
| `/api/v1/campaigns/{campaign_id}/schedule` | `POST` | None | `CampaignScheduleSummary` | `404`, `422`, `500` |
| `/api/v1/campaigns/{campaign_id}` | `GET` | None | `CampaignStatusResponse` | `404`, `500` |
| `/api/v1/campaigns/executions/ingest` | `POST` | `ExecutionResultIngestRequest` | `ExecutionResultIngestResponse` | `400`, `404`, `422`, `500` |
| `/api/v1/campaigns/approvals/{gate_id}/decision` | `POST` | `CampaignApprovalDecisionRequest` | `CampaignApprovalDecisionResponse` | `404`, `422`, `500` |
| `/api/v1/campaigns/{campaign_id}/correlate` | `POST` | None | `CampaignCorrelationResponse` | `404`, `500` |
| `/api/v1/campaigns/{campaign_id}/diagnostics` | `GET` | None | `CampaignDiagnosticsResponse` | `404`, `500` |

## Findings, Review, and Export Routes

| Endpoint | Method | Request Body | Success Response | Error Responses |
|---|---|---|---|---|
| `/api/v1/findings/review-queue` | `GET` | None (query: `campaign_id`, `limit`) | `FindingReviewQueueResponse` | `500` |
| `/api/v1/findings/{finding_id}/review` | `POST` | `FindingReviewRequest` | `FindingReviewResponse` | `400`, `404`, `422`, `500` |
| `/api/v1/findings/{finding_id}/prepare-submission` | `POST` | `PrepareSubmissionRequest` | `PrepareSubmissionResponse` | `400`, `404`, `422`, `500` |
| `/api/v1/findings/{finding_id}/export/{provider}/preview` | `GET` | None (query: `actor`, `submission_draft_id`, `intention_id`) | `SubmissionExportResponse` | `400`, `404`, `422`, `500` |
| `/api/v1/findings/{finding_id}/export/{provider}` | `POST` | `FindingExportRequest \| null` | `SubmissionExportResponse` | `400`, `404`, `422`, `500` |
| `/api/v1/findings/{finding_id}/diagnostics` | `GET` | None | `FindingDiagnosticsResponse` | `404`, `500` |

### Export Route Body Contract

`POST /api/v1/findings/{finding_id}/export/{provider}` accepts an empty request body.

- Allowed:
  - No body
  - `{}`
  - Partial overrides such as `{"actor": "operator.export"}`.
- Runtime behavior:
  - Missing body is normalized to `FindingExportRequest()` defaults.

## Diagnostics Route

| Endpoint | Method | Request Body | Success Response | Error Responses |
|---|---|---|---|---|
| `/api/v1/diagnostics/summary` | `GET` | None | `DiagnosticsSummaryResponse` | `500` |

## Bug Bounty / Analyst Cockpit Routes

| Endpoint | Method | Request Body | Success Response | Error Responses |
|---|---|---|---|---|
| `/api/v1/bug-bounty/programs` | `GET` | None | `ProgramOpportunityRead[]` | `500` |
| `/api/v1/bug-bounty/programs/{program_id}/targets` | `GET` | None | `MonitoredTargetRead[]` | `404`, `500` |
| `/api/v1/bug-bounty/schedules` | `GET` | None (query: `program_id`, `status`) | `HuntScheduleRead[]` | `500` |
| `/api/v1/bug-bounty/schedules/status` | `GET` | None (query: `program_id`) | `SchedulerStatusResponse` | `500` |
| `/api/v1/bug-bounty/readiness-records` | `GET` | None (query: `program_id`, `decision_status`, `limit`) | `ReadinessCheckResponse[]` | `500` |
| `/api/v1/bug-bounty/deltas` | `GET` | None (query: `program_id`, `scope_target_id`, `limit`) | `WorkflowDeltaRead[]` | `500` |
| `/api/v1/bug-bounty/candidates` | `GET` | None (query: `program_id`, `status`, `limit`) | `AnalystQueueItemRead[]` | `500` |
| `/api/v1/bug-bounty/candidates/{queue_item_id}` | `PATCH` | `CandidateQueueUpdateRequest` | `AnalystQueueItemRead` | `400`, `404`, `422`, `500` |
| `/api/v1/bug-bounty/candidates/{queue_item_id}/report-draft` | `POST` | `GenerateReportDraftRequest` | `GenerateReportDraftResponse` | `400`, `404`, `422`, `500` |

### Phase 6 Intelligence

| Endpoint | Method | Request Body | Success Response | Error Responses |
|---|---|---|---|---|
| `/api/v1/bug-bounty/signals` | `GET` | None | `SignalIntelligenceRead[]` | `500` |
| `/api/v1/bug-bounty/opportunity-scores` | `GET` | None | `OpportunityInferenceRead[]` | `500` |
| `/api/v1/bug-bounty/adaptive-actions` | `GET` | None | `AdaptiveScheduleActionRead[]` | `500` |
| `/api/v1/bug-bounty/analyst-briefing` | `GET` | None | `AnalystBriefingResponse` | `500` |

### Phase 7 Prediction / Selection

| Endpoint | Method | Request Body | Success Response | Error Responses |
|---|---|---|---|---|
| `/api/v1/bug-bounty/phase7/run` | `POST` | `Phase7RunRequest` | `Phase7RunResponse` | `400`, `422`, `500` |
| `/api/v1/bug-bounty/phase7/predictions` | `GET` | None | `VulnerabilityPredictionRead[]` | `500` |
| `/api/v1/bug-bounty/phase7/opportunity-rankings` | `GET` | None | `OpportunitySelectionRead[]` | `500` |
| `/api/v1/bug-bounty/phase7/target-yields` | `GET` | None | `TargetYieldScoreRead[]` | `500` |
| `/api/v1/bug-bounty/phase7/duplicate-risk` | `GET` | None | `DuplicateRiskRead[]` | `500` |
| `/api/v1/bug-bounty/phase7/evidence-completeness` | `GET` | None | `EvidenceCompletenessRead[]` | `500` |
| `/api/v1/bug-bounty/phase7/recommendations` | `GET` | None | `WorkflowRecommendationRead[]` | `500` |
| `/api/v1/bug-bounty/phase7/analyst-support` | `GET` | None | `Phase7AnalystSupportResponse` | `500` |

### Phase 9 Alerts and Cases

| Endpoint | Method | Request Body | Success Response | Error Responses |
|---|---|---|---|---|
| `/api/v1/bug-bounty/alerts/sync` | `POST` | `AlertSyncRequest` | `AlertSyncResponse` | `400`, `422`, `500` |
| `/api/v1/bug-bounty/alerts` | `GET` | None (query: `program_id`, `status`, `severity`, `limit`) | `NotificationAlertRead[]` | `500` |
| `/api/v1/bug-bounty/alerts/summary` | `GET` | None (query: `program_id`) | object counts (`unresolved_alert_count`, `high_severity_alert_count`, `open_case_count`, `ready_for_report_case_count`, `stale_unowned_case_count`) | `500` |
| `/api/v1/bug-bounty/alerts/{alert_id}` | `GET` | None | `NotificationAlertRead` | `404`, `500` |
| `/api/v1/bug-bounty/alerts/{alert_id}/acknowledge` | `POST` | `AlertActionRequest` | `NotificationAlertRead` | `400`, `404`, `422`, `500` |
| `/api/v1/bug-bounty/alerts/{alert_id}/resolve` | `POST` | `AlertActionRequest` | `NotificationAlertRead` | `400`, `404`, `422`, `500` |
| `/api/v1/bug-bounty/alerts/{alert_id}/case` | `POST` | `AlertCaseCreateRequest` | `AnalystCaseRead` | `400`, `404`, `422`, `500` |
| `/api/v1/bug-bounty/cases` | `GET` | None (query: `program_id`, `status`, `priority`, `owner`, `limit`) | `AnalystCaseRead[]` | `500` |
| `/api/v1/bug-bounty/cases` | `POST` | `CaseCreateRequest` | `AnalystCaseRead` | `400`, `404`, `422`, `500` |
| `/api/v1/bug-bounty/cases/{case_id}` | `GET` | None | `AnalystCaseRead` | `404`, `500` |
| `/api/v1/bug-bounty/cases/{case_id}` | `PATCH` | `CaseUpdateRequest` | `AnalystCaseRead` | `400`, `404`, `422`, `500` |
| `/api/v1/bug-bounty/cases/{case_id}/assign` | `POST` | `CaseAssignRequest` | `AnalystCaseRead` | `400`, `404`, `422`, `500` |
| `/api/v1/bug-bounty/cases/{case_id}/notes` | `POST` | `CaseNoteRequest` | `AnalystCaseRead` | `400`, `404`, `422`, `500` |

### Phase 10 Retrospective Learning

| Endpoint | Method | Request Body | Success Response | Error Responses |
|---|---|---|---|---|
| `/api/v1/bug-bounty/retrospective/run` | `POST` | `RetrospectiveRunRequest` | `RetrospectiveRunResponse` | `400`, `422`, `500` |
| `/api/v1/bug-bounty/retrospective/summary` | `GET` | None (query: `program_id`, `window_days`) | `RetrospectiveSummaryResponse` | `500` |
| `/api/v1/bug-bounty/retrospective/workflows` | `GET` | None (query: `program_id`, `limit`) | `WorkflowPerformanceRead[]` | `500` |
| `/api/v1/bug-bounty/retrospective/targets` | `GET` | None (query: `program_id`, `scope_target_id`, `limit`) | `TargetPerformanceRead[]` | `500` |
| `/api/v1/bug-bounty/retrospective/recommendations` | `GET` | None (query: `program_id`, `outcome_status`, `limit`) | `RecommendationOutcomeRead[]` | `500` |
| `/api/v1/bug-bounty/retrospective/alerts` | `GET` | None (query: `program_id`, `outcome_status`, `limit`) | `AlertOutcomeRead[]` | `500` |

### Phase 10.5 Specialized Agent Framework

| Endpoint | Method | Request Body | Success Response | Error Responses |
|---|---|---|---|---|
| `/api/v1/bug-bounty/agents/sync` | `POST` | None | `AgentRegistrySyncResponse` | `400`, `422`, `500` |
| `/api/v1/bug-bounty/agents` | `GET` | None (query: `enabled_only`, `category`, `limit`) | `AgentRegistryRead[]` | `500` |
| `/api/v1/bug-bounty/agents/{agent_id}` | `GET` | None | `AgentRegistryRead` | `404`, `500` |
| `/api/v1/bug-bounty/agents/executions` | `GET` | None (query: `program_id`, `agent_id`, `execution_status`, `limit`) | `AgentExecutionRead[]` | `500` |
| `/api/v1/bug-bounty/agents/evaluations` | `GET` | None (query: `agent_id`, `status`, `limit`) | `AgentEvaluationRead[]` | `500` |
| `/api/v1/bug-bounty/agents/{agent_id}/run` | `POST` | `AgentRunRequest` | `AgentExecutionRead` | `400`, `404`, `422`, `500` |
| `/api/v1/bug-bounty/agents/{agent_id}/evaluate` | `POST` | `AgentEvaluateRequest` | `AgentEvaluationRead` | `400`, `404`, `422`, `500` |

### Tool Health Contract

| Endpoint | Method | Request Body | Success Response | Error Responses |
|---|---|---|---|---|
| `/api/v1/tools/health` | `GET` | None | `Response` envelope with `data: ToolHealthDashboard` | `500` |

## Legacy Approval Route Note

`apps/backend/src/routers/approvals.py` exposes legacy endpoints under `/approvals/*`.
These are not part of the canonical operator console contract and should be treated as compatibility endpoints.
