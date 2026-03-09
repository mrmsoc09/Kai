# Orchestration Architecture (First Pass)

This document describes the first persisted orchestration/scheduling backbone built on top of the canonical campaign models.

## What Now Happens on Campaign Start

`POST /api/v1/campaigns/start` now performs a real persisted start flow:

1. Resolve or create `Program`.
2. Resolve or create `ScopeTarget` when a target is provided.
3. Create `CampaignRun`.
4. Create a campaign-start `IntentionRecord`.
5. Seed an initial `ExecutionBranch`.
6. Seed initial `PhaseJob` graph.
7. Write `AuditEvent` records for campaign/branch/phase seeding.
8. Run the scheduler immediately.

The start flow is durable and idempotency-aware when `idempotency_key` is supplied.

## Initial Branch and Phase Seeding

Default first-pass seeded phases:
- `recon_discovery`
- `target_validation`
- `lightweight_analysis`

The phase graph is persisted with dependencies:
- `target_validation` depends on `recon_discovery`
- `lightweight_analysis` depends on `target_validation`

Each seeded phase stores structured payload metadata so later prompts can extend dispatch/tool mapping without replacing the graph model.

## Scheduler Runnable Decision Logic

`BranchScheduler.schedule_campaign()` evaluates persisted state and decides per phase:

1. Campaign/branch terminal checks.
2. Branch dependency checks (`depends_on_branch_id`).
3. Phase dependency checks (`depends_on_job_id`).
4. Approval checks (`approval_required` on phase/branch/campaign).
5. Dispatch eligibility.

For each phase:
- dependency-unsatisfied phases become `BLOCKED`
- approval-gated phases become `WAITING_APPROVAL` and create/attach `ApprovalGate`
- dispatchable phases become `QUEUED`

Scheduler re-runs are safe:
- no duplicate pending approval gates for the same phase path
- no duplicate active dispatch if an active `ToolExecution` already exists for the phase

## Scheduler and Worker Dispatch

Dispatch path creates a persisted `ToolExecution` linked to:
- campaign
- branch
- phase
- intention (when available)

Dispatch modes:
- `tool` mode: enqueue existing Celery `run_tool` task (reuses existing worker/tool path)
- placeholder mode: enqueue `campaign_phase_placeholder` Celery task

Placeholder mode is explicit and durable; it does not mark work as magically completed.

## State Transitions and Auditability

Transition helpers now exist for:
- `CampaignRun`
- `ExecutionBranch`
- `PhaseJob`
- `ApprovalGate`
- `ToolExecution`

They now:
- reject invalid transitions
- set lifecycle timestamps
- emit `AuditEvent` records
- carry `intention_id` where available

## What Is Still Not Complete

This is not full autonomous platform completion. Remaining major wiring includes:
- full tool-routing per phase with production-safe parameterization
- worker callback/result ingestion to move `PhaseJob` and `ToolExecution` from `QUEUED/RUNNING` to terminal states
- approval decision APIs that automatically re-trigger branch/job unblocking
- comprehensive frontend migration to canonical campaign routes
- richer retry policies and failure escalation semantics
