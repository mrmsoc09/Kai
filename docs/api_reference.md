# API Reference

This reference documents the canonical backend routes currently used by campaign orchestration, review, diagnostics, and export staging.

## Health and Diagnostics

### `GET /health`
Basic liveness with service and worker snapshot.

### `GET /healthz`
Readiness-style dependency summary (`postgres`, `redis`, `neo4j`, worker visibility).

### `GET /api/v1/diagnostics/summary`
Status counters for campaigns, branches, phase jobs, approvals, executions, findings, and drafts.

### `GET /api/v1/campaigns/{campaign_id}/diagnostics`
Campaign-level state graph summary (counts, status breakdowns, phase links, recent audit events).

### `GET /api/v1/findings/{finding_id}/diagnostics`
Finding-level summary (evidence/observation/artifact counts, drafts, recent audit events).

## Campaign Orchestration

### `POST /api/v1/campaigns/start`
Creates or replays a campaign start request and seeds initial branch/phase graph.

### `GET /api/v1/campaigns/workflow-templates`
Lists template-based bug bounty workflow definitions.

### `POST /api/v1/campaigns/start-workflow`
Builds a workflow template into campaign phases (or dry-run plan) and schedules execution.

### `POST /api/v1/campaigns/execute-workflow`
Executes a workflow template locally end-to-end with normalized output artifacts and resumable manifest.

### `POST /api/v1/campaigns/{campaign_id}/schedule`
Runs scheduler against persisted state.

### `GET /api/v1/campaigns/{campaign_id}`
Returns campaign, branch, and phase status snapshot.

### `POST /api/v1/campaigns/executions/ingest`
Ingests worker/tool execution result and triggers state reconciliation.

### `POST /api/v1/campaigns/approvals/{gate_id}/decision`
Records approval gate decision and optionally re-runs scheduler.

### `POST /api/v1/campaigns/{campaign_id}/correlate`
Runs deterministic observation-to-finding correlation for campaign observations.

## Finding Review and Packaging

### `GET /api/v1/findings/review-queue`
Returns review-eligible findings with readiness metadata.

### `POST /api/v1/findings/{finding_id}/review`
Applies review action (`APPROVE`, `REJECT`, `NEEDS_MORE_EVIDENCE`, `DUPLICATE`, `SUPPRESS`).

### `POST /api/v1/findings/{finding_id}/prepare-submission`
Generates or refreshes submission package JSON for an eligible finding.

## Provider Export (Preview/Stage Only)

### `GET /api/v1/findings/{finding_id}/export/{provider}/preview`
Builds provider payload and returns readiness/missing-field output.  
Supported providers: `hackerone`, `bugcrowd`, `intigriti`.

### `POST /api/v1/findings/{finding_id}/export/{provider}`
Stages provider payload metadata into draft details.  
Returns `422` when readiness validation fails.

## Request/Response Schemas

Canonical schema definitions are under:

- `apps/backend/src/schemas/campaigns.py`
- `apps/backend/src/schemas/intention.py`

## Tool Catalog

### `GET /api/v1/tools/catalog/list`
Lists central tool catalog entries (optionally filtered to enabled defaults).

### `GET /api/v1/tools/catalog/item/{tool_name}`
Returns full catalog metadata for a single tool definition.

### `GET /api/v1/tools/health`
Returns structured health records for all catalog tools (or filtered set) including install status,
credential readiness, wrapper smoke status, safe-mode compatibility, and recent execution state.

Query params:

- `enabled_only` (bool)
- `run_smoke_tests` (bool)
- `telemetry_window` (int, default `20`)
- `install_timeout` (int, default `8`)
- `include_execution_history` (bool, default `false`) — optional DB enrichment for last execution fields
- `write_report` (bool) — when true, writes `output/reports/tool_health_report.json`

## Notes

- Route set includes legacy endpoints not listed here; this document intentionally covers the canonical campaign/finding/export surface.
- Provider routes do not submit to external platforms in current implementation.
