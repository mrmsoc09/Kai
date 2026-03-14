# Backend System

## Scope
This document describes the implemented backend behavior for campaign orchestration, persistence, and reporting support.

## Core Domain Model

Canonical execution entities:

- `Program`
- `ScopeTarget`
- `CampaignRun`
- `ExecutionBranch`
- `PhaseJob`
- `ApprovalGate`
- `ToolExecution`
- `Artifact`
- `Observation`
- `AuditEvent`
- `IntentionRecord`
- `ScanNote`
- `SubmissionDraft`

Existing reporting/review entities reused by the pipeline:

- `Finding`
- `Evidence`
- `Report`
- `HILApproval`

## Status Model

Implemented status enums include:

- Campaign: `CREATED`, `READY`, `RUNNING`, `PAUSED`, `BLOCKED`, `COMPLETED`, `FAILED`, `CANCELED`
- Branch: `PENDING`, `READY`, `RUNNING`, `WAITING_APPROVAL`, `BLOCKED`, `COMPLETED`, `FAILED`, `CANCELED`
- Phase job: `CREATED`, `QUEUED`, `RUNNING`, `WAITING_APPROVAL`, `BLOCKED`, `COMPLETED`, `FAILED`, `SKIPPED`, `CANCELED`
- Approval gate: `PENDING`, `APPROVED`, `REJECTED`, `DEFERRED`, `EXPIRED`, `CANCELED`
- Tool execution: `CREATED`, `QUEUED`, `RUNNING`, `WAITING_APPROVAL`, `COMPLETED`, `FAILED`, `CANCELED`

Transition guards are enforced in service layer code (`campaign_service`, `approval_gate_service`, `tool_execution_service`).

## Orchestration Services

Implemented services:

- `CampaignStartService`: campaign creation, idempotent start, initial branch + phase graph seeding, campaign-start intention.
- `BranchScheduler`: dependency-aware dispatch, approval-aware gating, branch-local blocking semantics.
- `ExecutionResultIngestionService`: terminal/result updates, side-effect creation, scheduler re-entry, replay safety handling.
- `ApprovalGateService`: create/decide/cancel gates with transition checks.
- `FindingCorrelationService`: deterministic observation-to-finding mapping with duplicate handling.
- `FindingReviewService`: human review transitions and draft state updates.
- `SubmissionPackageService`: package assembly for approved findings.
- `SubmissionExportService`: provider payload preview/staging (HackerOne, Bugcrowd, Intigriti).
- `MetricsService`: diagnostics summary counters.
- `tool_registry_catalog`: centralized tool metadata loading from `tools/registry/tool_registry.yaml`.
- `bugbounty_workflow_engine`: template-to-phase planning with scope/safe-mode checks.

## Worker Integration

- Celery app: `apps/backend/src/worker/celery_app.py`
- Campaign placeholder task path: `apps/backend/src/worker/campaign_tasks.py`
- Dispatch creates durable `ToolExecution` rows before worker execution.
- Result ingestion supports replay-safe updates by execution/task identity and payload fingerprint checks.
- Template workflow endpoint (`/api/v1/campaigns/start-workflow`) seeds phase jobs with dispatch mappings into the same worker path.

## Persistence and Audit

- Major state changes emit `AuditEvent`.
- Intention linkage is propagated where available across campaign, branch, phase, execution, and review flows.
- Diagnostics endpoints expose campaign/finding linkage and recent audit activity.

## Known Incompleteness

- Full autonomous tool coverage is not complete; placeholders still exist.
- Distributed locking is not implemented; concurrency safety is service-guard based.
- External provider submission APIs are not implemented in the current export layer.
