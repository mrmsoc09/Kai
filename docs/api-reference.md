# API Reference: Operator UI Surfaces

All protected endpoints require `Authorization: Bearer <token>`.

## Authentication (`/auth`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/auth/token` | `POST` | Username/password login (OAuth2 form) |
| `/auth/users/me` | `GET` | Current user + role + tenant context |

## Mission Control (`/missions`, `/events`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/missions/` | `GET` | List tenant missions |
| `/missions/{id}` | `GET` | Mission runtime status |
| `/missions/{id}/graph` | `GET` | Mission graph + node state |
| `/missions/{id}/start` | `POST` | Start mission |
| `/missions/{id}/stop` | `POST` | Stop/pause mission |
| `/missions/{id}/replay` | `POST` | Replay mission |
| `/events/mission/{id}/timeline` | `GET` | Mission timeline events |

## Governance (`/approvals`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/approvals/` | `GET` | List gates by status (`PENDING` default) |
| `/approvals/{id}` | `GET` | Approval gate detail |
| `/approvals/{id}/approve` | `POST` | Approve gate (`notes` query param optional) |
| `/approvals/{id}/reject` | `POST` | Reject gate (`notes` query param optional) |
| `/approvals/{id}/cancel` | `POST` | Cancel gate (`notes` query param optional) |

## Artifacts (`/artifacts`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/artifacts/mission/{id}` | `GET` | List mission artifacts |
| `/artifacts/{id}` | `GET` | Artifact metadata |
| `/artifacts/{id}/content` | `GET` | Artifact JSON/text/URI content |

## Simulation (`/simulation`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/simulation/scenarios` | `GET` | Available scenario packs |
| `/simulation/run` | `POST` | Launch simulation mission |
| `/simulation/compare` | `POST` | Compare two simulation missions |

## Intelligence (`/intel`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/intel/memory` | `GET` | Search/filter intelligence memory |
| `/intel/memory/{id}` | `GET` | Memory detail |
| `/intel/memory/{id}/relationships` | `GET` | Graph edges for memory |
| `/intel/memory/stats` | `GET` | Memory + graph metrics |

Security notes:
- Non-admin users only see intelligence memory entries in their own `tenant_id`.
- Cross-tenant relationship edges are filtered for non-admin users.

## Opportunities (`/opportunities`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/opportunities` | `GET` | Filtered opportunity list |
| `/opportunities/ranked` | `GET` | Ranked opportunity list |
| `/opportunities/{id}` | `GET` | Opportunity detail |
| `/opportunities/actions/capabilities` | `GET` | Action availability contract (`approve/reject/execute`) |
| `/opportunities/{id}/expand` | `POST` | Generate ranked expansion candidates from validated memory signals |
| `/opportunities/{id}/approve` | `POST` | Governed approval transition |
| `/opportunities/{id}/reject` | `POST` | Governed rejection transition |
| `/opportunities/{id}/execute` | `POST` | Controlled execution that generates missions |

### Opportunity lifecycle fields

Opportunity responses now include action-state fields:

- `status` (`proposed|approved|rejected|executing|completed|failed|cancelled`)
- `approval_state` (`pending|approved|rejected`)
- `approval_reason`
- `rejection_reason`
- `execution_metadata` (targets evaluated, blocked targets, mission lineage, runtime counts)
- `candidate_targets`
- `source_type`, `source_object_id`
- `expansion_candidates` (target-level similarity/duplicate/yield factors)
- `target_batches` (risk-banded grouped execution batches)
- `approved_targets`, `rejected_targets`
- `expansion_rationale`, `expansion_score`, `expected_report_quality`
- `recommended_execution_order`
- `linked_mission_count`, `linked_report_count`
- `decision_summary`, `chain_summary`
- `confidence_score`
- `estimated_yield`, `expected_yield`
- `duplicate_risk`
- `created_at`, `updated_at`, `created_by`

## Reports (`/reports`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/reports` | `GET` | List reports with optional filters (`severity`, `min_confidence`, `target`, `mission_id`, `opportunity_id`) |
| `/reports/{id}` | `GET` | Fetch a single submission-ready report |
| `/reports/generate` | `POST` | Deterministically generate + persist report from finding/chain/artifacts |
| `/reports/{id}/export` | `GET` | Download report in `markdown` or `json` format |
| `/reports/mission/{mission_id}` | `GET` | List reports linked to a mission |

### Report object fields

- `report_id`
- `title`
- `vulnerability_type`
- `severity`
- `target`
- `summary`
- `reproduction_steps`
- `http_requests`
- `http_responses`
- `exploit_chain`
- `impact`
- `remediation`
- `references`
- `validation_evidence`
- `confidence_score`
- `quality_score`
- `duplicate_hash`
- `tenant_id`
- `mission_id`, `opportunity_id`, `finding_id`
- `artifact_uri`
- `rendered_markdown`

Security notes:
- Report list/get/export endpoints are tenant-scoped when JWT includes `tid`.
- Export filenames are sanitized server-side before `Content-Disposition` is set.

## System (`/system`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/system/health` | `GET` | Basic health |
| `/system/status` | `GET` | Runtime/worker/system metrics |

## Realtime (`/ws`)

### WebSocket

- Endpoint: `/ws?token=<jwt>`
- Client control messages:
  - `{"action":"subscribe","channel":"mission_events","mission_id":"..."}`
  - `{"action":"unsubscribe","channel":"mission_events","mission_id":"..."}`
  - `{"action":"subscribe","channel":"governance_events"}`
  - `{"action":"subscribe","channel":"artifact_events","mission_id":"..."}`
  - `{"action":"subscribe","channel":"simulation_events"}`
- Server envelope:
  - `{"type":"mission_event","data":{...normalized event...}}`

### Recent catch-up API

| Endpoint | Method | Purpose |
|---|---|---|
| `/realtime/missions/{mission_id}/recent?limit=100` | `GET` | Return normalized recent mission events for reconnect/catch-up |
| `/events/broadcast` | `POST` | Admin-only mission-scoped manual broadcast (requires mission ownership) |

### Normalized event fields

- `schema_version`
- `event_id`
- `event_type`
- `timestamp`
- `tenant_id`
- `mission_id`
- `workflow_id`
- `program_id`
- `node_id`
- `phase`
- `status`
- `summary`
- `detail`
- `artifact_id`
- `approval_id`
- `category`
