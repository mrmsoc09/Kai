# Operator Cockpit Mission-Control Refresh

## Implemented

- Navigation reorganized to a mission-centric cockpit:
  - Overview / Action Board
  - Missions
  - Mission Control
  - Findings
  - Evidence
  - Reports
  - Approvals
  - Terminal
  - Programs / Targets
  - System / Logs
- Route aliases added without removing legacy pages:
  - `/missions` -> campaign mission queue
  - `/mission-control` + `/mission-control/[missionId]`
  - `/reports` -> exports/report staging workspace
  - `/logs` -> system/logs view
- Overview converted into an action board emphasizing:
  - priority findings
  - active missions
  - evidence-ready queue
  - approval pressure
  - attack-path concentration
  - scheduler/tool failures
- Mission Control cockpit introduced as central mission workspace:
  - mission summary
  - phase progress ribbon
  - execution timeline
  - agent actions
  - tool output
  - evidence + artifact drawer
  - approvals/gates
  - mission findings
  - terminal deep link
- Approvals page upgraded to governance queue semantics with richer metadata extraction from audit payloads and intention-aware review.
- Terminal page added for provider-backed operator execution and tmux session controls UI.

## Partial / Pending

- tmux backend endpoints are not currently implemented in this repository:
  - `GET /terminal/sessions`
  - `POST /terminal/sessions`
  - `POST /terminal/sessions/{sessionId}/attach`
  - `POST /terminal/sessions/{sessionId}/detach`
  - `POST /terminal/sessions/{sessionId}/kill`
- Frontend currently handles those as contract-pending and keeps existing provider execution endpoints live (`/terminal/providers`, `/terminal/execute`, `/terminal/logs`).
- Approval intention and safety fields are derived from available audit payloads; missing backend fields are surfaced explicitly as unspecified.

## Expected Inputs / Outputs

- Mission identifier in the operator UI maps to existing campaign UUIDs.
- Approval queue input:
  - tracked campaign UUIDs
  - optional risk/status/search filters
- Terminal input:
  - provider ID
  - prompt text
  - optional model and timeout
  - optional mission context
- Outputs:
  - campaign diagnostics-backed mission cockpit views
  - governance queue decisions via `/api/v1/campaigns/approvals/{gateId}/decision`
  - terminal transcript/history via `/terminal/logs`

## Safety Assumptions

- Operator actions remain human-gated; approval actions are explicit and auditable.
- Terminal page displays a safety banner and is intended for scope-approved operations only.
- Missing intention metadata is explicitly highlighted in approvals to avoid blind approval actions.
