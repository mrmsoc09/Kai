# Operator Console Surface Map

This maps operator UI surfaces to the current canonical backend APIs.

## 1. Campaign Dashboard

Purpose:
- Start campaigns.
- Show top-level campaign progress and status.
- Show aggregate health/metrics snapshot.

Primary endpoints:
- `POST /api/v1/campaigns/start`
- `GET /api/v1/campaigns/{campaign_id}`
- `GET /api/v1/diagnostics/summary`

Core data contracts:
- `CampaignStartResponse`
- `CampaignStatusResponse`
- `DiagnosticsSummaryResponse`

## 2. Phase Execution Monitor

Purpose:
- Track branch/job progression and scheduler effects.
- Inspect campaign-level execution diagnostics.

Primary endpoints:
- `POST /api/v1/campaigns/{campaign_id}/schedule`
- `GET /api/v1/campaigns/{campaign_id}/diagnostics`
- `POST /api/v1/campaigns/executions/ingest` (worker/system path)

Core data contracts:
- `CampaignScheduleSummary`
- `CampaignDiagnosticsResponse`
- `ExecutionResultIngestResponse`

## 3. Approval Queue

Purpose:
- Review and decide branch/job approval gates.
- Unblock only eligible dependent work by scheduler re-entry.

Primary endpoints:
- `POST /api/v1/campaigns/approvals/{gate_id}/decision`
- `GET /api/v1/campaigns/{campaign_id}/diagnostics` (gate visibility)

Core data contracts:
- `CampaignApprovalDecisionResponse`
- `CampaignDiagnosticsResponse`

## 4. Findings Review

Purpose:
- Work review queue.
- Apply deterministic review actions.
- Prepare approved findings for export packaging.

Primary endpoints:
- `GET /api/v1/findings/review-queue`
- `POST /api/v1/findings/{finding_id}/review`
- `POST /api/v1/findings/{finding_id}/prepare-submission`
- `GET /api/v1/findings/{finding_id}/diagnostics`

Core data contracts:
- `FindingReviewQueueResponse`
- `FindingReviewResponse`
- `PrepareSubmissionResponse`
- `FindingDiagnosticsResponse`

## 5. Submission Export

Purpose:
- Generate provider-specific payload previews.
- Stage export metadata to draft records.
- Keep human review mandatory (no auto-submit).

Primary endpoints:
- `GET /api/v1/findings/{finding_id}/export/{provider}/preview`
- `POST /api/v1/findings/{finding_id}/export/{provider}`

Core data contract:
- `SubmissionExportResponse`

Provider support:
- `hackerone`
- `bugcrowd`
- `intigriti`

## UI Integration Notes

- Poll diagnostics and campaign status endpoints for live updates (or move to SSE/WebSocket later).
- Treat `422` as recoverable workflow/state feedback, not as transport failure.
- For export, support bodyless POST calls; defaults are applied server-side.
- Use returned IDs/status values directly from response models; avoid frontend-invented state machines.
