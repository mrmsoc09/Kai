# Phase Completion Semantics (First Pass)

This document defines the current canonical status semantics for phase/branch/campaign progression after worker result ingestion.

## ToolExecution Outcomes

Canonical ingestion supports:

- `COMPLETED`
- `FAILED`
- `CANCELED`
- `WAITING_APPROVAL`
- `RUNNING` (worker start/progress update)

Each transition writes timestamps/audit records and preserves `intention_id` when available.

## PhaseJob Outcomes

Phase state is derived from ingested execution outcome:

- tool `COMPLETED` -> phase `COMPLETED`
- tool `FAILED` -> phase `FAILED`
- tool `CANCELED` -> phase `CANCELED`
- tool `WAITING_APPROVAL` -> phase `WAITING_APPROVAL`

Phase output summary/error fields are updated durably.

## Approval Outcomes

Campaign-phase approval decisions are now handled through canonical route:

- `POST /api/v1/campaigns/approvals/{gate_id}/decision`
- supports `APPROVED`, `REJECTED`, `DEFERRED`, `CANCELED`
- persists `decided_by`, `decided_at`, operator notes/payload
- emits audit events
- re-runs scheduler so newly eligible work can continue

## Branch Completion / Failure Rules

Scheduler branch reconciliation currently applies:

- Branch `COMPLETED` when all branch phases are in success terminal set (`COMPLETED`/`SKIPPED`)
- Branch `FAILED` when any branch phase is `FAILED` or `CANCELED`
- Branch `WAITING_APPROVAL` when any phase is waiting approval
- Branch `RUNNING` when phases are queued/running
- Branch `BLOCKED` when phases are blocked by dependencies/approval denial

## Campaign Completion / Failure Rules

Scheduler campaign reconciliation currently applies:

- Campaign `COMPLETED` when all branches are `COMPLETED` and phase set is success-terminal
- Campaign `FAILED` when all branches are terminal and one or more ended in failure/canceled states
- Campaign `RUNNING` when active or ready work exists
- Campaign `BLOCKED` when no runnable work exists and work is waiting on approval/dependency constraints

These rules are conservative and avoid masking partial failure as success.

## Remaining Gaps in Full Lifecycle

- No full retry orchestration policy yet for failed phases (beyond persisted retry metadata).
- No complete result deduplication/late-callback handling for all worker race conditions.
- No full branch-level optional-phase policy (all failed/canceled phases currently treated as branch failure unless future policy says otherwise).
- No complete end-to-end finding/submission generation semantics in this step.
