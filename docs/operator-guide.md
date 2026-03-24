# Operator Guide (UI + API Flows)

This guide covers how operators use the current Kai UI against real backend services.

## 1) Login and access model

1. Open the UI login page.
2. On first local bring-up, sign in as `k1-admin` with a blank password.
3. You will be forced to set an initial password (persisted to PostgreSQL).
4. Subsequent logins use username/password via backend `POST /auth/token`.
5. UI loads current identity (`GET /auth/users/me`) and applies role-aware controls.

Role behavior in UI:

- Viewer/operator: read surfaces
- Analyst/admin: mission control actions, governance decisions, simulation execution
- Admin: system metrics panel

Backend authorization is always enforced server-side.

## 1.5) Revenue dashboard workflow

Dashboard is the landing page for fast triage and monetization:

- validated findings produced from executed opportunities
- active opportunities and approved opportunities awaiting execution
- recent reports and highest-confidence reports
- opportunity-to-report conversion indicator
- direct links into Mission Control, Opportunities workbench, and Reports export surface

## 2) Mission Control workflow

Mission Control now uses real routes:

- `GET /missions/`
- `GET /missions/{id}/graph`
- `GET /events/mission/{id}/timeline`
- `GET /realtime/missions/{id}/recent`
- `POST /missions/{id}/start|stop|replay`

Operator flow:

1. Select mission from list.
2. Inspect graph node states (`pending/running/completed/failed/blocked`).
3. Review timeline grouped by date and categorized (governance/lifecycle/artifact/error/operation).
4. Run start/stop/replay if role permits.
5. Use runtime decision summary panel to inspect chosen action and rationale (with optional rejected alternatives when present).

Live behavior:

- Mission updates stream over websocket (`/ws?token=...`) with mission subscriptions.
- Graph node status and active node update as events arrive.
- Timeline appends in realtime using normalized event payloads.
- Mission polling remains enabled as fallback when websocket is degraded.

## 3) Governance approvals

Governance console is connected to:

- `GET /approvals/?status=...`
- `POST /approvals/{id}/approve|reject|cancel` (optional `notes`)

Recommended operator decision checks:

- mission linkage (`campaign_id`)
- gate reason and policy basis
- risk class
- request actor and timing
- realtime updates: new/changed approvals are refreshed when governance events arrive
- fallback polling is used when websocket is unavailable

## 4) Artifact workspace

Artifacts page is connected to:

- `GET /artifacts/mission/{mission_id}`
- `GET /artifacts/{artifact_id}/content`

Use the flow:

1. Select mission.
2. Open artifact metadata and preview (JSON/text/URI response).
3. Use “Open Mission Context” to pivot back to Mission Control.
4. Watch for live artifact notices from realtime artifact events (mission-scoped subscription).

## 5) Simulation control

Simulation page is connected to:

- `GET /simulation/scenarios`
- `POST /simulation/run`
- `POST /simulation/compare`

Simulation UI explicitly labels non-live behavior and displays returned mission ID/state.

## 6) Intelligence Center

Intelligence page is connected to:

- `GET /intel/memory`
- `GET /intel/memory/{id}`
- `GET /intel/memory/{id}/relationships`
- `GET /intel/memory/stats`

Operator can filter/search memory records and inspect relationship context for selected memory objects.

Filter controls:
- Free-text search across memory content and domain
- Memory type dropdown (populated from loaded result set)
- Validation status dropdown: `confirmed` / `partial` / `unvalidated` / `rejected`
- Scope dropdown (populated from loaded result set)
- Minimum confidence slider

Memory table shows color-coded validation status badges:
- `confirmed` → emerald
- `partial` → amber
- `rejected` → rose
- `unvalidated` → slate

Cross-page links on selected memory row:
- **related opportunities** — jumps to Opportunities filtered by vuln_type (or domain when no vuln_type tag)
- **related reports** — jumps to Reports filtered by target domain

## 7) Opportunities surface

Opportunities page is connected to:

- `GET /opportunities`
- `GET /opportunities/{id}`
- `GET /opportunities/actions/capabilities`
- `GET /opportunities/scan-queue/settings`
- `PUT /opportunities/scan-queue/settings`
- `POST /opportunities/{id}/expand`
- `POST /opportunities/{id}/approve`
- `POST /opportunities/{id}/reject`
- `POST /opportunities/{id}/execute`

Opportunity lifecycle:

1. `proposed` (default state from catalog + tenant action state)
2. `expanded` (validated source signal converted into ranked target candidates + batches)
3. `approved` or `rejected` (analyst/admin action with optional target-level review)
3. `executing` (execution launched after approval)
4. `completed` or `failed` (derived from mission outcomes)

Expansion behavior:

- Expansion uses validated findings/patterns for the selected vulnerability type and discovers in-scope concrete targets from memory + scope domains.
- Candidate targets are ranked by similarity, corroborating memory signal, duplicate risk penalty, and expected report quality.
- Targets are grouped into bounded risk-aware batches for operator review before execute.
- Approval can carry reviewed target subsets; execute uses approved targets first and falls back to candidate targets when no subset is set.

Execution behavior:

- Execution revalidates targets against scope policy and excludes invalid targets.
- Execution creates one or more mission runs (target-capped) with opportunity lineage metadata.
- Mission progress is reflected back into `execution_metadata` (`missions_launched`, `missions_completed`, `missions_failed`, findings/yield proxy).
- Linked mission/report counts are surfaced directly in the workbench for quick path compression.
- Chain context and decision summary are surfaced in the detail panel when expansion source metadata is available.
- Scan queue min/max concurrency limits are persisted server-side per authenticated user + tenant (team context), not only browser-local state.

Auditability:

- Every approve/reject/execute action is appended to audit log records with actor, reason, target selection, and mission linkage.
- Expansion actions emit realtime events (`opportunity_expansion_created`, `opportunity_expansion_ranked`, `opportunity_batch_ready`, `opportunity_expansion_approved`).
- Execution actions emit realtime events (`opportunity_approved`, `opportunity_rejected`, `opportunity_execution_started`, `opportunity_execution_completed`, `opportunity_execution_failed`).

## 7.5) Cross-page navigation (Phase 5)

The UI now supports direct pivot paths between pages:

- **Mission Control → Reports**: "Reports for this mission" link appears in the status panel when a mission is selected. Navigates to `/reports?mission_id=<id>`.
- **Mission Control → Artifacts**: "Artifacts" link appears alongside the reports link. Navigates to `/artifacts?mission=<id>`.
- **Intelligence Center → Opportunities**: "related opportunities" link on selected memory row.
- **Intelligence Center → Reports**: "related reports" link on selected memory row.
- **Dashboard → Reports**: Top-confidence report cards are now clickable links that open the specific report in the Reports workspace.

## 8) Reports workspace (monetization surface)

Reports page is connected to:

- `GET /reports`
- `GET /reports/{id}`
- `GET /reports/mission/{mission_id}`
- `GET /reports?opportunity_id=...`
- `POST /reports/generate`

Operator flow:

1. Filter reports by severity, confidence, target, mission, or opportunity context.
2. When mission or opportunity filter is active, a context banner confirms the active filter and report count.
3. Open a report and review summary, reproduction steps, exploit-chain context, impact, and remediation.
4. Use **Copy Report** for submission-ready markdown.
5. Use **Export MD** or **Export JSON** for direct download from backend export contract.
6. Pivot from opportunity execution metadata (`report_ids`) back to generated reports.

Layout: report list occupies 2/5 of the grid (xl:col-span-2), report viewer occupies 3/5 (xl:col-span-3) for maximal reading space.

Live vs simulation distinctions:

- Mission cards and mission detail panels label execution mode (`live` vs simulation modes).
- Operators should prioritize `live` results for monetization flow and keep simulation outputs for rehearsal/comparison.

Backend behavior:

- Report generation is deterministic (template + structured evidence), not freeform LLM output.
- Export endpoint supports `GET /reports/{id}/export?format=markdown|json` with attachment headers.
- Deduplication is enforced with a signature hash (endpoint + vuln type + payload signature).
- Quality scoring (`0.0–1.0`) reflects completeness, validation strength, chain context, and duplicate risk.
- Opportunity execution completion now auto-generates reports from validated findings and stores mission/opportunity lineage.
