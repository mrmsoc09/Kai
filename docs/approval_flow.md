# Approval Flow (Canonical Campaign Scheduler)

This document describes how durable approval gating now works in the first-pass campaign scheduler.

## When Approval Gates Are Created

During scheduling, a phase is treated as approval-gated when any of these are true:
- `PhaseJob.approval_required`
- `ExecutionBranch.approval_required`
- `CampaignRun.approval_required`

If approval is required and no phase-linked gate exists, scheduler creates:
- `ApprovalGate(campaign_id, branch_id, phase_job_id, intention_id, gate_reason, requested_by, status=PENDING)`

Creation is durable and emits an `AuditEvent`.

## Branch-Local Blocking Behavior

For gated phases:
- the specific `PhaseJob` is moved to `WAITING_APPROVAL`
- the owning `ExecutionBranch` is moved to `WAITING_APPROVAL`

Other branches are not globally frozen by this gate.
Independent branches with satisfied dependencies remain dispatchable.

Campaign status becomes `BLOCKED` only when there is no active runnable/queued work and work is waiting on approval/dependency constraints.

## How Approval Decisions Unblock Work (Current Intent)

The scheduler already supports gate-state interpretation:
- `APPROVED` allows phase dispatch eligibility on next scheduling pass
- `PENDING` / `DEFERRED` keeps phase in `WAITING_APPROVAL`
- `REJECTED` / `EXPIRED` / `CANCELED` blocks the gated phase path

Current expectation:
1. gate decision is persisted on `ApprovalGate`
2. scheduler is re-run
3. scheduler reevaluates and queues newly-eligible phases

## What Remains to Be Wired

Still pending in later prompts:
- dedicated approval decision endpoints for campaign-phase gates (if not already provided by higher-level adapters)
- automatic scheduler trigger on gate decision commit
- richer partial-unblock semantics across deeper branch trees
- operator UX and timeline views fully backed by canonical gate data

This step establishes durable approval records and branch-local scheduler behavior; it does not complete the full approval UI/ops workflow.
