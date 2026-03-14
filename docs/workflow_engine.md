# Workflow Engine

## Overview
The workflow engine is the canonical campaign scheduler and result loop built on `CampaignRun`, `ExecutionBranch`, and `PhaseJob`.

## Campaign Start

Entry point: `POST /api/v1/campaigns/start`

Implemented start behavior:

1. Create or replay `CampaignRun` (idempotency key supported).
2. Create campaign-start `IntentionRecord`.
3. Create initial branch.
4. Seed initial phase graph:
   - `recon_discovery`
   - `target_validation`
   - `lightweight_analysis`
5. Emit campaign-start audit events.
6. Invoke scheduler.

Template entry points:

- `GET /api/v1/campaigns/workflow-templates`
- `POST /api/v1/campaigns/start-workflow`
- `POST /api/v1/campaigns/execute-workflow`

Template runs convert workflow definitions into persisted phase graphs with dispatch metadata (`dispatch.tool_id`, `dispatch.params`).
`start-workflow` supports dry-run planning and safe-mode guardrails.
`execute-workflow` runs the same template semantics in a local executor that emits normalized artifacts and resumable manifests.

## Scheduling Rules

Implemented in `BranchScheduler`:

- Evaluates branch dependencies and phase dependencies.
- Moves runnable phases to `QUEUED`.
- Creates approval gates for approval-required work.
- Moves approval-gated phases to `WAITING_APPROVAL`.
- Blocks only dependent branches/phases when approval or dependency conditions are unmet.
- Avoids duplicate dispatch when queued/running execution already exists.
- Re-entry safe: scheduler can run repeatedly from persisted state.

## Dispatch Model

- Dispatch adapter creates `ToolExecution` for each runnable phase.
- Real tool execution uses Celery `run_tool_task` when mapped.
- Unmapped phases create explicit placeholder executions (not treated as full tool coverage).
- Catalog-backed wrappers are registered through `tool_adapters_bugbounty.py` and resolved via the global tool registry.

## Result Ingestion Loop

Entry point: `POST /api/v1/campaigns/executions/ingest`

Handled outcomes:

- `RUNNING`
- `COMPLETED`
- `FAILED`
- `CANCELED`
- `WAITING_APPROVAL`

Effects:

- Transition `ToolExecution`.
- Transition parent `PhaseJob`.
- Reconcile branch/campaign states.
- Persist artifacts and observations.
- Emit audit events.
- Trigger scheduler re-entry (optional per request).

## Phase / Branch / Campaign Semantics

Current first-pass semantics:

- Phase follows tool execution status.
- Branch completes when all branch phases are success-terminal (`COMPLETED`/`SKIPPED`).
- Branch fails when required phases fail/cancel.
- Campaign completes when all active branches complete successfully.
- Campaign fails when all branches are terminal and any failed/canceled.
- Campaign blocks when no runnable work exists due to gates/dependencies.

## Approval Flow

- Approval gates are durable (`ApprovalGate`).
- Decisions (`APPROVED`, `REJECTED`, `DEFERRED`, `CANCELED`) are persisted.
- Scheduler is re-run after decisions.
- Unblocking remains branch-local and dependency-aware.
