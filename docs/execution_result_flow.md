# Execution Result Flow (First Pass)

This document describes the first canonical worker-result ingestion loop on top of campaign orchestration.

## How Results Enter the Canonical System

Results now enter through two paths:

1. Worker callbacks (best-effort)  
   - `run_tool` and `campaign_phase_placeholder` tasks call canonical ingestion helpers by `worker_task_id`.
   - Worker start can mark `ToolExecution`/`PhaseJob` as `RUNNING` when a matching canonical execution exists.

2. Canonical API ingestion endpoint  
   - `POST /api/v1/campaigns/executions/ingest`
   - Accepts canonical identifiers (`execution_id` or `worker_task_id`) and requested terminal/approval state.

## Canonical Entities Updated During Ingestion

For each ingested result, the backend updates durable records:

- `ToolExecution`
  - status transitions (`RUNNING`, `COMPLETED`, `FAILED`, `CANCELED`, `WAITING_APPROVAL`)
  - output refs (`stdout_ref`, `stderr_ref`, summaries), exit code, error message

- `PhaseJob`
  - terminal/waiting status updates
  - output summary/error persistence

- `ExecutionBranch` and `CampaignRun`
  - updated via scheduler re-entry and state reconciliation

- `Artifact`
  - canonical artifact records are created from explicit inputs and/or result payload/log refs
  - inline artifact URIs use explicit `inline://...` scheme when no real file path exists

- `Observation`
  - first-pass normalized observations are created (discovery/signal/validation/context/decision)
  - observations link back to `ToolExecution` and source artifact when present

- `AuditEvent`
  - transition and ingestion events are written for traceability/intention linkage

## Scheduler Re-entry After Result Ingestion

By default, ingestion re-runs the canonical scheduler for the affected campaign.

This enables:
- dependency-unlocked downstream jobs to queue
- branch status reconciliation (`RUNNING`, `WAITING_APPROVAL`, `BLOCKED`, `COMPLETED`, `FAILED`)
- campaign status reconciliation (`RUNNING`, `BLOCKED`, `COMPLETED`, `FAILED`)

## Approval-Wait Handling

If a worker result requires approval:
- `ToolExecution` transitions to `WAITING_APPROVAL`
- canonical `ApprovalGate` is attached/created for the phase path
- `PhaseJob` and owning branch transition to `WAITING_APPROVAL`
- scheduler re-entry preserves branch-local gating semantics

## Placeholder vs Real Execution

Current behavior is explicit:

- Real mapped tool execution (`adapter_name=celery.run_tool_task`) is supported.
- Unmapped phases still dispatch placeholder tasks (`adapter_name=placeholder.dispatch`).
- Placeholder completions create durable tool/artifact/observation/audit records, but they are labeled as placeholder context and are not treated as proof of full autonomous coverage.

## What Is Still Not Complete

- Full bidirectional worker lifecycle integration (robust start/progress/finish callbacks with retries and idempotent deduping).
- Comprehensive phase-to-tool mappings across all planned bug bounty phases.
- Full finding generation pipeline from normalized observations.
- Full frontend migration to canonical execution/result endpoints.
