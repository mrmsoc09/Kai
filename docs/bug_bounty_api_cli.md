# Bug Bounty Hunting API and CLI

This document covers the continuous bug bounty endpoints and CLI commands.

## Authentication (required)

Most `/api/v1/bug-bounty/*` routes require bearer authentication.

Obtain a local dev access token:

```bash
curl -sS -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$K1_DEV_TOKEN\"}"
```

Set CLI/API token:

```bash
export K1_API_TOKEN="<access_token>"
export K1_API_URL="http://localhost:8080"
```

CLI fallback behavior:

- If `K1_API_TOKEN` is unset and `K1_DEV_TOKEN` is set, CLI will attempt `/auth/login` and use the returned access token.

## API Endpoints

Base prefix: `/api/v1/bug-bounty`

### Programs and Targets

- `GET /programs`
  - list persisted bug bounty programs
- `POST /programs/import`
  - import/update program opportunity metadata and scope assets
- `GET /programs/{program_id}/targets`
  - list monitored targets for a program
- `PATCH /targets/{scope_target_id}`
  - update monitored-target state (enable/disable, notes, scheduling hints)

### Scheduling

- `POST /schedules`
  - create recurring schedule
- `GET /schedules`
  - list schedules (`program_id`, `status` filters)
- `GET /schedules/status`
  - scheduler metrics summary (`due`, `active`, `paused`, readiness outcomes)
- `PATCH /schedules/{schedule_id}`
  - pause/resume/update schedule runtime policy
- `GET /schedules/{schedule_id}/readiness`
  - compute readiness decision (optionally persisted)
- `POST /schedules/{schedule_id}/trigger`
  - trigger one schedule immediately
- `POST /schedules/run-due`
  - run due schedules in priority order
- `POST /schedules/dispatch-due`
  - dispatch due schedules to Celery workers for parallel execution

### Operations and Analyst Surfaces

- `GET /readiness-records`
  - list readiness outcomes and blocked reasons
- `GET /deltas`
  - list run-to-run deltas
- `GET /candidates`
  - list analyst queue items with reportability fields
- `PATCH /candidates/{queue_item_id}`
  - update analyst queue state/assignment/notes
- `POST /candidates/{queue_item_id}/report-draft`
  - generate report draft artifact and canonical `SubmissionDraft`

### Phase 6 Inference and Intelligence

- `POST /inference/run`
  - aggregate cross-run signals and generate deterministic opportunity inference records
- `GET /signals`
  - list canonical signal intelligence records
- `GET /opportunity-scores`
  - list inferred opportunity scores, recommended workflows, and next-best actions
- `GET /swarm-outputs`
  - list structured swarm reasoning outputs by role
- `GET /adaptive-actions`
  - list adaptive scheduling actions (applied/blocked/skipped)
- `GET /analyst-briefing`
  - produce operator briefing payload (prioritized targets/candidates/actions)

### Phase 7 Vulnerability Prediction and Opportunity Selection

- `POST /phase7/run`
  - run deterministic prediction, ranking, recommendation, and optional adaptive effort control
- `GET /phase7/predictions`
  - list vulnerability prediction records (confidence/novelty/duplicate/reportability/evidence/opportunity)
- `GET /phase7/opportunity-rankings`
  - list ranked subjects (`PROGRAM`, `TARGET`, `CANDIDATE`, `CLUSTER`)
- `GET /phase7/target-yields`
  - list target/program yield scoring records
- `GET /phase7/duplicate-risk`
  - list duplicate-risk records and risk bands
- `GET /phase7/evidence-completeness`
  - list evidence completeness records and readiness states
- `GET /phase7/recommendations`
  - list next-best-workflow recommendations and status
- `GET /phase7/analyst-support`
  - produce analyst decision-support bundle from canonical Phase 7 outputs

### Phase 9 Notifications and Case Management

- `POST /alerts/sync`
  - synchronize deduplicated alerts from canonical queue/prediction/recommendation/delta/readiness sources
- `GET /alerts`
  - list persisted alert records with severity/status filters
- `GET /alerts/summary`
  - alert and case operational count summary
- `GET /alerts/{alert_id}`
  - retrieve alert detail
- `POST /alerts/{alert_id}/acknowledge`
  - acknowledge alert
- `POST /alerts/{alert_id}/resolve`
  - resolve alert
- `POST /alerts/{alert_id}/case`
  - create/attach analyst case for alert follow-through
- `GET /cases`
  - list analyst cases by status/priority/owner/program
- `POST /cases`
  - create analyst case
- `GET /cases/{case_id}`
  - case detail
- `PATCH /cases/{case_id}`
  - update status/priority/summary/closure
- `POST /cases/{case_id}/assign`
  - assign/reassign owner
- `POST /cases/{case_id}/notes`
  - append analyst note

### Phase 10 Retrospective and Feedback Learning

- `POST /retrospective/run`
  - persist retrospective feedback/outcome records and compute workflow/target performance snapshots
- `GET /retrospective/summary`
  - return retrospective intelligence summary (`top_programs`, `top_targets`, workflow leaders, noise/success summaries)
- `GET /retrospective/workflows`
  - list workflow performance records (`workflow_signal_value`, `workflow_reportability_rate`, `workflow_noise_rate`)
- `GET /retrospective/targets`
  - list target performance records (`target_yield_score`, reportability/duplicate rates)
- `GET /retrospective/recommendations`
  - list recommendation outcome records and success scores
- `GET /retrospective/alerts`
  - list alert outcome records and acknowledgement/noise/actionable status

### Phase 10.5 Specialized Agents

- `POST /agents/sync`
  - synchronize first-wave specialized agents into canonical registry
- `GET /agents`
  - list agent registry records (`enabled_only`, `category`, `limit`)
- `GET /agents/{agent_id}`
  - retrieve one registry record
- `GET /agents/executions`
  - list agent execution history (`program_id`, `agent_id`, `execution_status`, `limit`)
- `GET /agents/evaluations`
  - list agent evaluation history (`agent_id`, `status`, `limit`)
- `POST /agents/{agent_id}/run`
  - execute one specialized agent with explicit context and structured input payload
- `POST /agents/{agent_id}/evaluate`
  - run deterministic fixture-based benchmark for one agent

## CLI Commands

Command group: `kai-cli bug-bounty`

- `kai-cli bug-bounty program-import <path.json>`
- `kai-cli bug-bounty programs`
- `kai-cli bug-bounty targets --program-id <uuid>`
- `kai-cli bug-bounty schedule-create --program-id <uuid> --scope-target-id <uuid> --template workflow_quick_vuln_sweep`
- `kai-cli bug-bounty schedules [--program-id <uuid>] [--status ACTIVE]`
- `kai-cli bug-bounty scheduler-status [--program-id <uuid>]`
- `kai-cli bug-bounty readiness --program-id <uuid> --scope-target-id <uuid> --template workflow_quick_vuln_sweep`
- `kai-cli bug-bounty run-due [--limit 25]`
- `kai-cli bug-bounty dispatch-due [--limit 25]`
- `kai-cli bug-bounty schedule-trigger --schedule-id <uuid> [--force]`
- `kai-cli bug-bounty candidates [--program-id <uuid>] [--status needs_manual_validation]`
- `kai-cli bug-bounty candidate-update --queue-item-id <uuid> --status triaged [--assigned-to analyst-1]`
- `kai-cli bug-bounty report-draft --queue-item-id <uuid>`
- `kai-cli bug-bounty deltas [--program-id <uuid>]`
- `kai-cli bug-bounty inference-run [--program-id <uuid>] [--apply-adaptive]`
- `kai-cli bug-bounty scores [--program-id <uuid>] [--limit 50]`
- `kai-cli bug-bounty swarm [--program-id <uuid>] [--role recon_planning_agent]`
- `kai-cli bug-bounty briefing [--program-id <uuid>] [--limit 20]`
- `kai-cli bug-bounty phase7-run [--program-id <uuid>] [--apply-adaptive]`
- `kai-cli bug-bounty phase7-predictions [--program-id <uuid>] [--limit 50]`
- `kai-cli bug-bounty phase7-rankings [--program-id <uuid>] [--subject-type TARGET]`
- `kai-cli bug-bounty phase7-recommendations [--program-id <uuid>] [--status PROPOSED]`
- `kai-cli bug-bounty phase7-analyst-support [--program-id <uuid>] [--limit 20]`
- `kai-cli bug-bounty alerts-sync [--program-id <uuid>] [--cooldown-minutes 120]`
- `kai-cli bug-bounty alerts [--program-id <uuid>] [--status OPEN] [--severity HIGH]`
- `kai-cli bug-bounty alert-ack --alert-id <uuid>`
- `kai-cli bug-bounty alert-resolve --alert-id <uuid>`
- `kai-cli bug-bounty cases [--program-id <uuid>] [--status triaging] [--priority HIGH] [--owner analyst-1]`
- `kai-cli bug-bounty case-update --case-id <uuid> --status ready_for_report`
- `kai-cli bug-bounty case-assign --case-id <uuid> --owner analyst-1`
- `kai-cli bug-bounty case-note --case-id <uuid> --note "validated path traversal"`
- `kai-cli bug-bounty phase10-run [--program-id <uuid>] [--window-days 30]`
- `kai-cli bug-bounty phase10-summary [--program-id <uuid>] [--window-days 30]`
- `kai-cli bug-bounty phase10-workflows [--program-id <uuid>] [--limit 50]`
- `kai-cli bug-bounty phase10-targets [--program-id <uuid>] [--limit 50]`
- `kai-cli bug-bounty phase10-recommendations [--program-id <uuid>] [--status SUCCEEDED]`
- `kai-cli bug-bounty phase10-5-agents-sync`
- `kai-cli bug-bounty phase10-5-agents [--enabled-only] [--category strategy_recommendation]`
- `kai-cli bug-bounty phase10-5-agent-run --agent-id scope_parsing_agent --program-id <uuid> [--input-json payload.json]`
- `kai-cli bug-bounty phase10-5-agent-executions [--program-id <uuid>] [--agent-id scope_parsing_agent]`
- `kai-cli bug-bounty phase10-5-agent-evaluate --agent-id scope_parsing_agent`
- `kai-cli bug-bounty phase10-5-agent-evaluations [--agent-id scope_parsing_agent]`

## Minimal Import Payload Example

```json
{
  "source": "manual",
  "platform": "hackerone",
  "name": "Example Program",
  "program_key": "example-program",
  "status": "ACTIVE",
  "require_safe_mode": true,
  "in_scope_assets": [
    {
      "target": "*.example.com",
      "target_type": "domain",
      "monitoring_enabled": true,
      "safe_mode_required": true,
      "priority_tier": 2
    }
  ],
  "out_of_scope_assets": [
    {
      "target": "admin.example.com",
      "target_type": "domain",
      "monitoring_enabled": false,
      "safe_mode_required": true,
      "priority_tier": 5
    }
  ]
}
```

## Safety Notes

- This layer does not auto-submit findings externally.
- Readiness/policy checks run before every scheduled launch.
- Blocked launches are durable and queryable.
- Safe mode remains the default for recurring schedules.
- Alert deduplication and suppression are enabled to reduce repeated low-signal notifications.
- Case transitions are validated server-side and written to canonical audit events.
