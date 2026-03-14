# Operator Console SOC Surfaces

This document maps the 12 SOC-OPS surfaces in `apps/frontend-operator` to their backend data sources and implementation status.

Status values:

- **Fully backed**: surface is built from canonical backend endpoints without frontend-only fake state.
- **Partially derived**: surface is useful but combines canonical data with deterministic derivation.
- **Pending deeper backend support**: UI surface exists, but key backend APIs are not yet available.

| SOC Surface | Route | Primary Data Sources | Status | Notes |
|---|---|---|---|---|
| Global Security Overview | `/overview` | `GET /api/v1/diagnostics/summary`, `GET /health`, `GET /readyz`, tracked campaign status/diagnostics, findings queue | Fully backed | Alert panel includes deterministic derived alerts from canonical diagnostics/audit events. |
| Attack Surface Intelligence | `/attack-surface` | `GET /api/v1/findings/review-queue`, `GET /api/v1/findings/{finding_id}/diagnostics` | Partially derived | Asset table and technology hints are derived; no canonical asset inventory endpoint yet. |
| Reconnaissance Activity | `/recon` | tracked campaign status + diagnostics | Fully backed | Recon rows are phase-name filtered from canonical phase jobs; no synthetic execution state is invented. |
| Findings Triage Center | `/triage` | `GET /api/v1/findings/review-queue` | Fully backed | Extends queue with client-side filters only. |
| Evidence and Artifact Repository | `/evidence` | findings review queue + diagnostics counts | Partially derived | Canonical global evidence/artifact listing endpoint is not yet present. |
| Threat Intelligence Feed | `/threat-intel` | findings queue + finding diagnostics | Partially derived | External threat-intel integrations are pending; page currently uses internal canonical context only. |
| IOC Monitoring | `/ioc` | tracked campaign diagnostics + finding diagnostics + findings queue | Partially derived | IOC extraction uses deterministic regex parsing of canonical text payloads only. |
| Investigation Timeline | `/timeline` | campaign diagnostics audit events + finding diagnostics audit events | Fully backed | Timeline is directly built from canonical audit events. |
| Campaign Performance Analytics | `/analytics` | diagnostics summary + tracked campaign status | Fully backed | Charts are lightweight client-side rendering of canonical counts. |
| Automation and Playbooks | `/playbooks` | tracked campaign phase jobs | Partially derived | Catalog is real from phase graph; execution controls require backend playbook APIs. |
| Alerting and Notifications | `/alerts` | tracked campaign diagnostics + findings queue | Partially derived | Alerts are deterministic derivations from canonical statuses and audit events. |
| System Diagnostics | `/system` | diagnostics summary + health/readiness + campaign/finding diagnostics | Fully backed | Primary system-ops surface; legacy `/diagnostics` remains for compatibility. |

## Sidebar Mapping

Core Operations:

- Overview
- Campaigns
- Recon
- Findings / Triage
- Approvals
- Exports

SOC Intelligence:

- Attack Surface
- Evidence
- Threat Intel
- IOC
- Timeline
- Analytics
- Playbooks
- Alerts
- System
- Diagnostics (Legacy)

## Backend Support Gaps (Current)

1. Global campaign listing endpoint for first-class multi-campaign SOC aggregation.
2. Canonical cross-campaign artifact/evidence listing endpoint.
3. External threat-intelligence integration endpoints.
4. IOC-native backend indexing APIs.
5. Playbook execution/control APIs beyond phase graph visibility.
