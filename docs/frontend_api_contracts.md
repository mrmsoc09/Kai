# Frontend API Contracts

This document defines the canonical backend endpoints for the operator console.
Source of truth is `apps/backend/src/routers/campaigns.py`.

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

## Legacy Approval Route Note

`apps/backend/src/routers/approvals.py` exposes legacy endpoints under `/approvals/*`.
These are not part of the canonical operator console contract and should be treated as compatibility endpoints.
