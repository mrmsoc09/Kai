# Continuous Authorized Bug Bounty Hunting

This document describes the canonical continuous hunting layer added on top of Kai's existing campaign/workflow persistence and execution engine.

## Scope

The implementation extends existing canonical components:

- `Program` and `ScopeTarget` for bug bounty program and scope inventory
- `WorkflowExecutor` + `WorkflowRun`/`StageRun`/`ToolExecution` for execution
- `WorkflowFinding` and `CorrelationRecord` for normalized workflow outputs
- `SubmissionDraft`, `Artifact`, and `AuditEvent` for analyst/report pipeline

No parallel workflow engine or separate persistence subsystem was introduced.

Phase 6 adds deterministic inference/intelligence records and adaptive scheduling actions on the same canonical foundation.

## Data Model Additions

New canonical tables:

- `hunt_schedule_jobs`
  - recurring schedule definitions per `(program, scope target, workflow template)`
  - supports interval/cron-like scheduling, pause/resume, cooldown, backoff, failure thresholds
- `hunt_readiness_records`
  - durable readiness decisions per attempted launch
  - includes blocked reasons and metadata context
- `workflow_delta_records`
  - run-to-run delta records for discovered assets/services/URLs/endpoints/parameters/secrets/candidates
- `analyst_queue_items`
  - candidate queue for likely reportable findings with deterministic scoring and queue state

`scope_targets` was extended with monitored-target lifecycle fields:

- `monitoring_enabled`
- `monitoring_priority_tier`
- `monitoring_status`
- `monitoring_source`
- `monitoring_notes`
- `safe_mode_required`
- `last_checked_at`, `last_success_at`, `last_failure_at`
- `next_scheduled_run_at`

Migration: `0006_bug_bounty_continuous_hunting.py`

## Program Opportunity Ingestion

Programs are imported through canonical `Program` records. Opportunity metadata is stored under `Program.config_json["opportunity"]`:

- source/platform metadata
- program URL and policy text
- restrictions/guidelines
- safe-mode requirement
- reward metadata
- sync timestamps

Imported scope assets are upserted as canonical `ScopeTarget` rows:

- in-scope assets become active monitored targets (unless explicitly disabled)
- out-of-scope assets are persisted with `is_in_scope=false` and monitoring disabled

## Readiness and Policy Gating

Every scheduled launch evaluates deterministic readiness before execution:

- target/program references valid
- schedule is active
- target monitoring enabled
- target is in canonical scope
- cooldown and next-run timing satisfied
- schedule concurrency limit not exceeded
- workflow template permitted by program policy
- safe-mode requirements satisfied
- canonical scope decision passes for current target
- required tool health is acceptable for template tools
- required credentials for template tools are present in canonical secret manager/env

Readiness status values:

- `READY`
- `BLOCKED_BY_SCOPE`
- `BLOCKED_BY_PROGRAM_POLICY`
- `BLOCKED_BY_HEALTH`
- `BLOCKED_BY_CONFIG`
- `BLOCKED_BY_COOLDOWN`
- `BLOCKED_BY_DISABLED_TARGET`
- `BLOCKED_BY_SAFETY_POLICY`

All decisions are persisted in `hunt_readiness_records` and audited.

## Recurring Execution

Due schedules launch through `WorkflowExecutor` using explicit canonical context:

- linked `program_id`
- linked `scope_target_id`
- scheduler trigger source (`SCHEDULER:<schedule_id>`)
- safe mode and dry-run controls from schedule

The existing workflow execution path persists:

- campaign context
- workflow/stage/tool execution records
- normalized artifacts on disk under `output/`

No alternate runner path bypasses canonical persistence.

## Delta Detection

After a scheduled run, normalized output JSONL snapshots are compared against the previous run for the same `(scope target, template)`:

- discovered assets
- live services
- URLs
- endpoints
- parameters
- secrets
- vulnerability candidates

New/removed items are persisted to `workflow_delta_records`.

## Candidate Queue and Reportability

`WorkflowFinding` rows are converted into `analyst_queue_items` with deterministic scoring:

- confidence
- severity weight
- novelty estimate from prior occurrences
- reportability score
- duplicate-risk hint
- policy-fit status

Queue states include:

- `new`
- `acknowledged`
- `triaged`
- `needs_manual_validation`
- `ready_for_report`
- `dismissed`
- `duplicate_suspected`
- `submitted_externally`

Queue items are operator-updatable through canonical API/CLI status transitions and assignment fields.

## Report Draft Generation

A queue item can produce:

- markdown report draft artifact under `output/reports/bug_bounty/`
- canonical `SubmissionDraft` row
- canonical `Artifact` row (`REPORT_DRAFT`)
- audit event linkage

External provider submission remains out of scope for this layer and is not auto-triggered.

## Scheduler Observability

Canonical scheduler status exposes:

- total/active/paused/disabled/error schedule counts
- due schedule count
- ready vs blocked readiness decisions over the last 24h

This summary is available via API and CLI for operator monitoring without introducing a parallel scheduler.

## Safety Defaults

- no run without program linkage and scope target
- no run without readiness pass
- safe mode enforced by default
- policy can block workflows per program
- blocked runs are recorded explicitly
- repeated failures can pause schedules automatically
