# Frontend Readiness

## Current Backend Status

Backend test baseline:

- `python3 -m pytest -q` -> `177 passed, 1 skipped, 0 failed`

Canonical workflow tests for campaign orchestration, ingestion, finding correlation, review, export staging, and diagnostics are passing.

## Stable Backend Surfaces for UI Integration

- Campaign start and status:
  - `POST /api/v1/campaigns/start`
  - `GET /api/v1/campaigns/{campaign_id}`
  - `POST /api/v1/campaigns/{campaign_id}/schedule`
- Approval decisions:
  - `POST /api/v1/campaigns/approvals/{gate_id}/decision`
- Finding review queue and actions:
  - `GET /api/v1/findings/review-queue`
  - `POST /api/v1/findings/{finding_id}/review`
  - `POST /api/v1/findings/{finding_id}/prepare-submission`
- Provider preview/export staging:
  - `GET /api/v1/findings/{finding_id}/export/{provider}/preview`
  - `POST /api/v1/findings/{finding_id}/export/{provider}`
- Diagnostics:
  - `GET /api/v1/diagnostics/summary`
  - `GET /api/v1/campaigns/{campaign_id}/diagnostics`
  - `GET /api/v1/findings/{finding_id}/diagnostics`

## Known Integration Caveats

- Not all legacy frontend paths are migrated to canonical campaign endpoints.
- Some phases still dispatch placeholder executions where direct tool mappings are not yet implemented.
- Export flow stages payloads only; no provider-side submission call is available.

## Recommendation

Frontend operator-console work can proceed against canonical endpoints above, with explicit UI messaging for:

- approval-gated waiting states
- placeholder execution paths
- export readiness failures (`422`) and missing-field feedback
