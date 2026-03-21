# UI Foundation (Kai Operator Interface)

## Current integration status

The `ui/` frontend is now wired to real backend contracts for core operator flows. Mock-backed services were removed from runtime paths.

### Real backend pages

- Dashboard (revenue workflow landing)
- Mission Control
- Intelligence Center
- Artifacts
- Governance
- Simulation
- Opportunities (governed approve/reject/execute flow)
- Reports (submission-ready monetization workspace)
- Login/Auth

### Preparatory seams still in UI

- Distributed durability for realtime event fanout/replay remains future work.

## Backend contract mapping

The UI service layer in `ui/src/api/services.ts` maps directly to backend routes:

- Auth: `POST /auth/token`, `GET /auth/users/me`
- Missions: `GET /missions/`, `GET /missions/{id}`, `POST /missions/{id}/start|stop|replay`, `GET /missions/{id}/graph`
- Timeline: `GET /events/mission/{id}/timeline`
- Governance: `GET /approvals/`, `GET /approvals/{id}`, `POST /approvals/{id}/approve|reject|cancel`
- Artifacts: `GET /artifacts/mission/{id}`, `GET /artifacts/{id}`, `GET /artifacts/{id}/content`
- Simulation: `GET /simulation/scenarios`, `POST /simulation/run`, `POST /simulation/compare`
- Intelligence: `GET /intel/memory`, `GET /intel/memory/{id}`, `GET /intel/memory/{id}/relationships`, `GET /intel/memory/stats`
- Opportunities: `GET /opportunities`, `GET /opportunities/ranked`, `GET /opportunities/{id}`, `GET /opportunities/actions/capabilities`
- Opportunity actions: `POST /opportunities/{id}/expand`, `POST /opportunities/{id}/approve`, `POST /opportunities/{id}/reject`, `POST /opportunities/{id}/execute`
- Reports: `GET /reports`, `GET /reports/{id}`, `GET /reports/mission/{id}`, `POST /reports/generate`, `GET /reports/{id}/export`
- System: `GET /system/status`
- Realtime: `GET /realtime/missions/{id}/recent`

## Auth and role-aware behavior

- Login uses backend credential flow (`/auth/token`) rather than token paste.
- JWT is stored in local storage and attached automatically by Axios.
- Current user (`/auth/users/me`) is cached for role-aware rendering.
- UI action controls are role-gated:
  - Mission start/stop/replay: analyst/admin
  - Governance decisions: analyst/admin
  - Simulation execution: analyst/admin
  - System metrics: admin
- Role gating is additive only; backend remains source of truth for authorization.

## Realtime behavior

- WebSocket client connects to backend `/ws?token=...`.
- UI sends explicit subscribe/unsubscribe control messages for channels and mission IDs.
- Mission Control subscribes to mission-specific stream and applies typed reducer updates to:
  - mission list state
  - mission graph node status/active node/progress
  - mission timeline append
- Governance subscribes to governance event channel and refreshes approvals on matching events.
- Artifacts subscribes to artifact channel scoped by selected mission and refreshes artifact list on matching events.
- Mission Control hydrates from `GET /realtime/missions/{id}/recent` on mission selection/reconnect to reduce lost updates.
- Polling remains as fallback:
  - Mission Control: reduced interval when socket is healthy, faster fallback when disconnected.
  - Governance/Artifacts: interval fallback when realtime is unavailable.
- Opportunities: websocket-triggered refresh on `opportunity_*` events; no heavy periodic full refresh loop.

## Phase 5 UX improvements (MVP compression)

### ActionModal component (`ui/src/components/ActionModal.tsx`)
Inline confirmation/reason modal replacing `window.prompt`/`window.confirm`:
- Used by Opportunities page for approve/reject/execute actions
- Props: `isOpen`, `title`, `message`, `requiresReason`, `reasonPlaceholder`, `confirmLabel`, `confirmClass`, `onConfirm(reason)`, `onCancel`
- Keyboard: Escape=cancel, Enter=confirm (when no reason required), click-outside=cancel
- `requiresReason=true` renders a textarea (reject action)

### WebSocket status indicator (AppLayout header)
Color-coded pill badge replaces plain text:
- `connected` → emerald (bg-emerald-500/15, dot bg-emerald-400)
- `connecting` / `idle` → amber (bg-amber-500/15, dot bg-amber-400)
- `disconnected` / `error` → rose (bg-rose-500/15, dot bg-rose-400)

### Opportunities page row status colors
Table rows are tinted by opportunity status:
- `approved` → emerald tint
- `executing` → cyan tint
- `completed` → slate tint
- `rejected` → rose tint + reduced opacity

### Intelligence Center validation status filter
Validation status filter is now a `<select>` dropdown (confirmed/partial/unvalidated/rejected) instead of a free-text input. Memory table includes a color-coded Status column with badges.

### Reports filter context banner
When mission_id or opportunity_id filter is active, a context banner above the list confirms what is filtered and how many reports are shown.

### Cross-page navigation links added
- Mission Control status panel: links to related Reports and Artifacts when mission selected
- Intelligence Center: links to related Opportunities and Reports from selected memory row
- Dashboard: top-confidence report cards link directly to report detail in Reports workspace

## Operator workflow compression (MVP)

UI now supports a direct operator path:

1. Dashboard identifies high-value opportunities and report conversion health.
2. Opportunities workbench expands/ranks targets, shows chain and decision context, and supports target-level approval.
3. Execution state links directly to mission and generated report context.
4. Reports workspace supports mission/opportunity filtering, final review, and direct markdown/json export.
5. Intelligence Center supports “what do we know about X” style search and jumps directly to related opportunities/reports.

## Realtime event contract (frontend-consumable)

Mission event envelope:

- `type`: `"mission_event"`
- `data`: normalized event object

Normalized event fields:

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
- `category` (`lifecycle|node|governance|artifact|simulation|operation`)

## Security posture in UI

- Simulation runs are explicitly labeled as non-live control flow.
- Governance risk and mission linkage are surfaced before decision actions.
- Artifact preview defaults to JSON/text rendering with metadata context and mission navigation.
- No hidden “unsafe” action paths are exposed client-side.
- Reports surface confidence and quality scores before copy/export to reduce low-value submissions.
- Reports workspace supports authenticated markdown/json download through backend export endpoint.
