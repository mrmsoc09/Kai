# Phase 9 Alerting and Case Management

## Scope

Phase 9 extends the canonical bug bounty backend with:

- persisted notification alerts
- alert deduplication/suppression
- analyst case lifecycle records
- assignment and note workflows
- API + CLI surfaces
- frontend operator pages for alerts and cases

No parallel scheduler, workflow engine, or queue model was introduced.

## Canonical Persistence

Added canonical entities in `apps/backend/src/models/bug_bounty.py`:

- `NotificationAlertRecord`
- `AnalystCaseRecord`

Migration:

- `apps/backend/alembic/versions/0009_phase9_alerting_case_management.py`

## Alert Model

`NotificationAlertRecord` stores:

- type, severity, urgency
- canonical linkage (`program_id`, `scope_target_id`, `analyst_queue_item_id`, prediction/recommendation refs)
- summary + reasoning summary
- fingerprint for suppression/dedupe
- status (`OPEN`, `ACKNOWLEDGED`, `SUPPRESSED`, `RESOLVED`)
- occurrence counters and first/last-seen timestamps

## Case Model

`AnalystCaseRecord` stores:

- linkage to alert/finding/prediction/recommendation/draft context
- title, summary, reasoning summary
- priority and status
- owner and actor fields
- transition timestamps
- closure reason
- evidence refs + triage notes JSON
- assignment/transition history in `details_json`

Validated case statuses:

- `new`
- `acknowledged`
- `triaging`
- `needs_manual_validation`
- `ready_for_report`
- `dismissed`
- `duplicate`
- `escalated`
- `submitted`
- `closed`

## Alert Generation and Suppression

Service: `apps/backend/src/core/phase9_alert_case_service.py`

`sync_alerts()` collects alert seeds from canonical records:

- high-reportability candidate queue items
- duplicate-risk high records
- evidence completeness gaps
- blocked/deferred recommendations
- severe recent deltas
- blocked readiness records
- blocked adaptive actions
- high-confidence predictions

Deduplication behavior:

- fingerprint + program scope resolution
- open/acknowledged alerts increment `occurrence_count`
- recently resolved repeats are marked `SUPPRESSED` within cooldown window
- otherwise a new `OPEN` alert is created

## Case Lifecycle Behavior

Case transitions are validated by `CASE_ALLOWED_TRANSITIONS` in `Phase9AlertCaseService`.

If a case reaches terminal/report-ready states (`ready_for_report`, `submitted`, `closed`, `dismissed`, `duplicate`), linked alerts are resolved.

Assignment and note operations append structured history entries.

## API Surface

Router: `apps/backend/src/routers/bug_bounty.py`

Added endpoints:

- `POST /api/v1/bug-bounty/alerts/sync`
- `GET /api/v1/bug-bounty/alerts`
- `GET /api/v1/bug-bounty/alerts/summary`
- `GET /api/v1/bug-bounty/alerts/{alert_id}`
- `POST /api/v1/bug-bounty/alerts/{alert_id}/acknowledge`
- `POST /api/v1/bug-bounty/alerts/{alert_id}/resolve`
- `POST /api/v1/bug-bounty/alerts/{alert_id}/case`
- `GET /api/v1/bug-bounty/cases`
- `POST /api/v1/bug-bounty/cases`
- `GET /api/v1/bug-bounty/cases/{case_id}`
- `PATCH /api/v1/bug-bounty/cases/{case_id}`
- `POST /api/v1/bug-bounty/cases/{case_id}/assign`
- `POST /api/v1/bug-bounty/cases/{case_id}/notes`

## CLI Surface

`apps/backend/src/cli/commands/bug_bounty.py` now includes:

- `alerts-sync`
- `alerts`
- `alert-ack`
- `alert-resolve`
- `cases`
- `case-update`
- `case-assign`
- `case-note`

## Frontend Surfaces

`apps/frontend-operator` additions:

- `/alerts`
- `/cases`
- `/cases/[caseId]`

New hooks/components:

- `useAlertCenter`, `useCaseQueue`, `useCaseDetail`
- `AlertTable`, `CaseQueueTable`, `CaseDetailPanel`

Overview dashboard now includes unresolved-alert/open-case summary counts.

## Safety and Limits

- No auto-submission to external providers.
- No auto-exploitation.
- Alert creation is bounded by dedupe/suppression logic to reduce noise.
- Case actions stay operator-driven and auditable.
