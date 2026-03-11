# Diagnostics Endpoints (First Pass)

This document describes the operator-facing diagnostics and health routes added during backend hardening.

## Health and Readiness

### `GET /health`

Lightweight health snapshot:

- API process status
- internal service startup flags
- best-effort worker subsystem probe

### `GET /healthz`

Best-effort readiness probe (returns `503` when degraded):

- dependency probes (`postgres`, `redis`, `neo4j`)
- worker probe (`celery` ping + worker count)
- `K1_REQUIRE_WORKER` support for enforcing worker availability in readiness

### `GET /livez`

Process liveness endpoint (`{"status":"ok"}`).

### `GET /readyz`

Alias to readiness behavior used by `/healthz`.

## Metrics and Diagnostics

### `GET /api/v1/diagnostics/summary`

Returns structured status counts from canonical persistence:

- campaigns by status
- branches by status
- phase jobs by status
- approval gates by status
- tool executions by status
- findings by status
- submission drafts by status

## Campaign Diagnostics

### `GET /api/v1/campaigns/{campaign_id}/diagnostics`

Returns campaign-level debugging summary:

- campaign status and error/block metadata
- counts of branches/phases/tools/gates/artifacts/observations/drafts
- status breakdown per entity class
- phase linkage summary (`depends_on`, `worker_task_id`)
- recent campaign audit events

## Finding Diagnostics

### `GET /api/v1/findings/{finding_id}/diagnostics`

Returns finding-level debugging summary:

- finding metadata/status/scope context
- linked evidence/observation/artifact counts
- submission draft state
- recent finding audit events

## Operator Usage Guidance

- Use `diagnostics/summary` for fleet-level triage.
- Use campaign diagnostics first when a run appears stalled/blocked.
- Use finding diagnostics when review/submission state appears inconsistent.
- Use readiness endpoints in deployment checks; do not treat `/livez` as dependency readiness.

## Current Limitations

- Worker probe is best-effort and broker-dependent.
- Diagnostics are read-only summaries, not remediation controls.
- No external time-series or alerting integration in this step.
