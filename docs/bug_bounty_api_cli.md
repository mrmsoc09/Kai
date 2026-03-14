# Bug Bounty Hunting API and CLI

This document covers the continuous bug bounty endpoints and CLI commands.

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
