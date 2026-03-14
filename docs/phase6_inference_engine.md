# Phase 6: Autonomous Recon Intelligence and Inference Engine

This document describes the canonical Phase 6 extension for Kai.

## Scope

Phase 6 extends the existing bug bounty persistence and scheduling stack without introducing parallel subsystems.

Extended canonical components:

- `hunt_schedule_jobs` / `hunt_readiness_records` (existing recurring execution)
- `workflow_runs` / `workflow_findings` / `correlation_records` (existing workflow persistence)
- new Phase 6 intelligence records:
  - `signal_intelligence_records`
  - `opportunity_inference_records`
  - `swarm_reasoning_records`
  - `adaptive_schedule_action_records`

## Signal Intelligence Model

Signals are aggregated deterministically from canonical records:

- workflow deltas (`workflow_delta_records`)
- workflow findings (`workflow_findings`)
- correlation records (`correlation_records`)

Each signal stores:

- source and source record linkage
- signal type and key
- confidence and severity hints
- evidence/correlation references
- fingerprint for idempotent dedupe

## Inference Engine

The inference engine runs as a deterministic scoring cycle:

1. aggregate new signals
2. group signals by `(program_id, scope_target_id)`
3. score opportunity and priority
4. derive recommended workflow and next-best action
5. persist `opportunity_inference_records`
6. persist structured swarm outputs
7. optionally apply adaptive scheduling

No non-deterministic LLM reasoning is used in this path.

## Swarm Reasoning Roles

Phase 6 persists structured outputs for:

- `opportunity_intake_agent`
- `recon_planning_agent`
- `signal_correlation_agent`
- `anomaly_detection_agent`
- `reportability_scoring_agent`
- `duplicate_risk_agent`
- `analyst_briefing_agent`

Outputs are JSON payloads in `swarm_reasoning_records.output_json`.

## Adaptive Scheduling

When enabled, inference may apply bounded scheduler updates:

- adjust schedule priority tier for the recommended workflow
- bring next run forward for high-opportunity targets
- persist action outcome (`APPLIED` / `BLOCKED` / `SKIPPED`)

Adaptive behavior does not bypass:

- canonical scope checks
- readiness gating
- safe mode requirements
- schedule status constraints

## Distributed Worker Dispatch

Phase 6 adds worker dispatch support for due schedules:

- endpoint: `POST /api/v1/bug-bounty/schedules/dispatch-due`
- task: `bug_bounty_schedule_run` (Celery)
- worker role labeling derived from workflow template

The worker task executes canonical `trigger_schedule()` with durable state updates.

## Analyst Guidance Output

`GET /api/v1/bug-bounty/analyst-briefing` returns:

- prioritized targets from inferred opportunity scores
- prioritized candidate findings from analyst queue
- recent adaptive actions and statuses

This output is intended for operator review and follow-up decisions.
