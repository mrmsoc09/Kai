# Backend Gap Audit

## Executive Verdict

Kai/K1 does not currently provide a real end-to-end autonomous bug bounty backend.

What exists today is a mix of:

- real but narrow backend slices
- file-backed workflow and reporting helpers
- isolated Celery tool execution
- in-memory approval/orchestration state
- dead or unregistered scan routes
- fixture-backed or simulated autonomous scan code
- documentation that overstates the implemented state

The current repository can:

- create and persist lightweight workflow JSON files
- create and persist lightweight run JSON files
- queue individual tool tasks through Celery
- persist a limited HiL database slice for findings/evidence/approvals/reports
- write logs, reports, and artifacts to filesystem locations

The current repository cannot prove a real "begin scan" flow from frontend trigger through persisted campaign state, queued multi-phase execution, branch-aware orchestration, resumability, branch-local HiL pause/resume, real finding lifecycle, and intention-aware audit records.

## What Was Inspected

Primary entrypoints and wiring:

- `apps/backend/src/main.py`
- `apps/backend/src/app/main.py`
- `apps/backend/src/worker/celery_app.py`
- `apps/backend/src/routers/*.py`
- `apps/backend/hil_api/app.py`

Execution, workflow, and persistence paths:

- `apps/backend/src/core/full_scan_orchestrator.py`
- `apps/backend/src/core/kai_orchestrator.py`
- `apps/backend/src/core/orchestration_graph.py`
- `apps/backend/src/core/workflow_store.py`
- `apps/backend/src/core/run_store.py`
- `apps/backend/src/core/jobs.py`
- `apps/backend/src/core/tool_runner.py`
- `apps/backend/src/core/tool_execution_store.py`
- `apps/backend/src/core/authorization_gate.py`
- `apps/backend/src/core/scope.py`
- `apps/backend/src/core/scope_resolver.py`
- `apps/backend/src/core/hil_db.py`
- `apps/backend/src/core/hil_approval_system.py`

ORM/migrations:

- `apps/backend/src/models/*.py`
- `apps/backend/alembic/versions/0001_phase2_base_schema.py`
- `apps/backend/alembic/versions/0002_add_reproducibility_score.py`

Artifact, report, and audit helpers:

- `apps/backend/src/core/artifacts.py`
- `apps/backend/src/core/logs.py`
- `apps/backend/src/core/audit.py`
- `apps/backend/src/core/trace.py`
- `apps/backend/src/core/evidence_objects.py`
- `apps/backend/src/core/evidence_contract.py`
- `apps/backend/src/core/report_generator.py`
- `apps/backend/src/core/submissions.py`
- `apps/backend/src/core/packager.py`
- `apps/backend/src/core/recordings.py`
- `apps/backend/src/core/finalize.py`

Frontend trigger paths:

- `apps/frontend/src/routes/Opportunities.tsx`
- `apps/frontend/src/routes/WorkflowDashboard.tsx`
- `apps/frontend/src/lib/api.ts`

Representative tests/docs:

- `tests/test_dorks_hil.py`
- `tests/test_finding_creation_lifecycle_async.py`
- `tests/test_defensive_dag_semantics.py`
- `tests/test_hil_concurrency.py`
- `tests/test_reports_submit_hil.py`
- `docs/AUTONOMOUS_BBP_SCANNING_COMPLETE.md`
- `docs/HIL_APPROVAL_WORKFLOW.md`
- `docs/workflows.md`

## Current Backend Structure

### Canonical API App

The canonical FastAPI app is `apps/backend/src/main.py`.

This app includes many routers, but the actual backend state model is inconsistent:

- some routers are file-backed
- some routers are DB-backed
- some routers are in-memory
- some routers expose orchestration concepts with no persistence
- some scan routers exist on disk but are not registered at startup

`apps/backend/src/app/main.py` is only a compatibility proxy to `apps.backend.src.main:app`.

`apps/backend/hil_api/app.py` is a legacy compatibility app that re-exposes a subset of the consolidated HiL routers.

### Persistence Layers Actually Present

There are three different persistence styles in active use:

1. PostgreSQL via SQLAlchemy/Alembic
2. filesystem JSON/JSONL state under `artifacts/`
3. process-local in-memory dictionaries/lists

This is the core backend consistency problem.

### Database-Backed Slice

The database-backed slice is real but small. Current ORM coverage is limited to:

- `Finding`
- `Evidence`
- `HILApproval`
- `Report`
- `AuditMerkleRoot`
- `ProgramScope`
- `ExecutionContextRecord`

These support a narrow HiL finding workflow, not a full campaign execution system.

There are no DB entities for:

- campaign runs
- phase jobs
- branch nodes
- tool executions
- observations
- generalized artifacts
- submission drafts
- audit events
- intention records
- resumable orchestration state

### File-Backed Slice

The file-backed slice is broad and heavily used:

- `workflow_store.py` stores workflows in `artifacts/workflows/<wf_id>/workflow.json`
- `run_store.py` stores run records in `artifacts/dork_runs/<run_id>/run.json`
- `jobs.py` appends queued jobs to `artifacts/jobs.jsonl`
- `logs.py` writes run decision traces and summaries under `artifacts/logs/...`
- `reports.py`/`persistence.py`/`packager.py` write report packages and submission artifacts under `artifacts/`

This file-backed layer is functional for demos and lightweight state tracking, but it is not a production orchestration substrate.

### In-Memory Slice

Several important subsystems are process-local only:

- `full_scan_orchestrator.py` stores `active_scans` in memory
- `hil_approval_system.py` stores pending approvals/history in memory
- `tool_execution_store.py` stores approval-pending tool runs in memory
- `orchestration_graph.py` stores a single global orchestration session in memory
- `agent_zero.py` workflow handling is also runtime-global/in-memory

These states do not survive restarts and cannot support resumable backend execution.

## Current Scan Execution Path

### Frontend Path That Actually Fires Today

The frontend "start hunt" path is:

1. `apps/frontend/src/routes/Opportunities.tsx`
2. `createWorkflow()` in `apps/frontend/src/lib/api.ts`
3. `POST /workflows`
4. `apps/backend/src/routers/workflows.py`
5. `apps/backend/src/core/workflow_store.py`

What this actually does:

- creates a workflow JSON file
- assigns an initial state (`SCOPING` or `SELECTED`)
- returns workflow metadata to the UI

What it does not do:

- queue a scan
- create a persisted campaign run
- create phase jobs
- start a worker
- select tools
- execute tools
- create execution artifacts
- persist observations/findings from tools

### Closest Thing To "Begin Scan" In The Workflow Path

When a workflow transitions to `SCANNING`, `workflow_store.transition_workflow()`:

- creates a `run_id`
- writes a minimal run record to `artifacts/dork_runs/<run_id>/run.json`
- writes a decision log entry

This is not scan execution. It is a state transition plus run-record initialization.

No queue dispatch follows that transition.
No worker is notified.
No orchestrator resumes from that state.
No adapter is called.

### Dead/Unwired Scan Start Route

`apps/backend/src/routers/scans.py` defines `POST /scans/start`.

That route:

- requires `X-Accept-Scope`
- builds a `run_id`
- appends a JSONL job via `core/jobs.py`
- logs `scan_enqueued`

But this router is not registered in `apps/backend/src/main.py`.

Even if it were registered, the queue path is still incomplete because `core/jobs.py` only appends to `artifacts/jobs.jsonl`. There is no worker consumer for that file queue.

### Dead/Unwired Autonomous Scan Route

`apps/backend/src/routers/autonomous_scan.py` defines `/api/v1/autonomous/scan/initiate` and `/api/v1/autonomous/scan/execute`.

That router is also not registered in `apps/backend/src/main.py`.

Its backing orchestrator, `core/full_scan_orchestrator.py`, is not real backend execution:

- selected programs are fixture-backed
- program details are fixture-backed
- recon phase is simulated with `asyncio.sleep`
- vuln scan phase is simulated with `asyncio.sleep`
- analysis is heuristic transformation of fake findings
- scan state is kept only in `self.active_scans`
- no database records are created
- no queue/worker orchestration is used
- no real tool adapter chain is invoked for the scan phases

### Bottom-Line Scan Path Assessment

There is no fully wired "begin scan" path in the current codebase.

The existing scan-related surfaces are fragmented:

- UI workflow creation is real but only creates file-backed workflow state
- `/scans/start` is dead and file-queue-only
- `/api/v1/autonomous/scan/*` is dead and simulated
- Celery-backed tool execution exists but is not connected to the hunt/workflow/campaign path

## Current Worker/Background Execution Path

### What Exists

`apps/backend/src/worker/celery_app.py` provides a real Celery app and a `run_tool_task` task.

`apps/backend/src/routers/tasks.py` and `apps/backend/src/core/tool_runner.py` can enqueue individual tool executions to Celery.

This path includes:

- tool registry lookup
- toolpack policy checks
- authorization gate checks
- OPSEC policy acquisition/release
- hook-based audit logging
- best-effort artifact JSON write

### What Is Missing

This worker path is not a scan orchestration system.

Missing pieces:

- no `CampaignRun` or `PhaseJob` entity
- no dependency graph between jobs
- no scheduler for multi-phase execution
- no callback path that updates workflow/campaign state from Celery completions
- no persisted `ToolExecution` row tied to a scan branch
- no branch-local pause/resume
- no automatic finding extraction into the canonical DB-backed finding system
- no artifact lineage linking task output to campaign phase, branch, and finding

The Celery path is a standalone tool queue, not a real hunt runtime.

## Current Database Model Coverage

### Proven Coverage

The PostgreSQL/Alembic layer currently supports:

- findings
- evidence attached to findings
- HiL approvals for findings
- report hashes / merkle roots
- scope policies per program
- idempotency/execution context records

This is useful, but it is only the reporting/review tail of a backend, not the execution spine.

### Critical Missing Persistence Models

Missing models required to make the backend real:

- `Program`
- `ScopeTarget`
- `CampaignRun`
- `PhaseJob`
- `ExecutionBranch`
- `ApprovalGate`
- `ToolExecution`
- `Observation`
- `Artifact`
- `ScanNote`
- `SubmissionDraft`
- `AuditEvent`
- `IntentionRecord`
- possibly `JobDependency` or `ExecutionEdge`

There is also no canonical record joining:

- who started a hunt
- what target/program/scope was selected
- what branches exist
- what jobs ran
- what tools ran
- what artifacts were produced
- what findings were derived
- what approvals paused which branches

## Missing Orchestration Layers

The codebase contains orchestration-themed modules, but none provide durable production orchestration for scans.

### `core/orchestration_graph.py`

What it is:

- a defensive phase state machine
- a useful conceptual skeleton

What it is not:

- persisted
- resumable
- multi-session safe
- branch-aware
- worker-driven

It stores a single global session and is suitable only as an in-memory prototype.

### `core/full_scan_orchestrator.py`

What it is:

- a narrative scan flow
- a fixture-backed demonstration of phase ordering

What it is not:

- a real orchestrator
- a worker-integrated runtime
- a persisted campaign engine

### `core/kai_orchestrator.py`

What it is:

- a compliance-style execution pipeline for a single tool command
- includes scope, signed-intent, audit, subprocess, and transparency concepts

What it is not:

- integrated into the actual scan/workflow runtime
- persisted as campaign/branch/job state
- used by the frontend hunt path

### `core/workflow_store.py`

What it is:

- file-backed hunt state machine
- useful UI-visible progress tracker

What it is not:

- a real runtime scheduler
- a dependency engine
- a queue-backed orchestrator

## Missing Persistence Models

The current schema cannot answer basic backend truth questions such as:

- which campaign is currently running
- which phase is blocked
- which branch is paused pending approval
- which tool execution created which observation
- which artifact belongs to which tool run and branch
- why a tool execution was authorized
- whether an action was initiated by user request, automated policy, retry, or escalation

These gaps are structural, not cosmetic.

## Missing Worker/Runtime Pieces

Required runtime pieces that do not exist in the current implementation:

- campaign/job scheduler
- worker tasks for phase execution
- persisted retry handling for phase jobs
- persisted phase/job status transitions
- result handlers that normalize tool outputs into observations/findings
- artifact metadata persistence with hashes and lineage
- job recovery/resume after process restart
- cancellation semantics
- dead-letter/retry diagnostics

`core/jobs.py` is especially weak here. It is a JSONL append-only pseudo-queue with no consumer.

## Missing Approval-Gate Logic

### What Exists

- `routers/approvals.py` provides a simple approval acknowledgment for intrusive tool runs
- `routers/hil_approval.py` provides CRUD-style approval APIs for in-memory approval objects
- `models/hil.py` plus `routers/hil_workflow.py` provide DB-backed finding approval/submission flow
- `workflow_store.py` includes a credential collection checkpoint

### What Is Missing

- no branch-local pause/resume model
- no persisted approval gates attached to campaign branches/jobs
- no dependency-aware branch blocking
- no approval state transition that unblocks downstream jobs
- no campaign-wide policy engine deciding when to raise an approval gate
- no linkage between scan execution path and approval APIs

### Specific Structural Problem

There are multiple approval stores:

- `routers/hil_approval.py` owns its own module-global `HiLApprovalSystem`
- `core/hil_approval_system.py` also exposes a separate global singleton
- `full_scan_orchestrator.py` instantiates its own private `HiLApprovalSystem`

That means approval requests created by one path are not guaranteed to be visible to the API path a human would use to review them.

This is a real correctness bug, not just a design smell.

## Missing Artifact/Logging Pipeline

Artifacts are written in several incompatible ways:

- `core/artifacts.py` writes flat JSON files
- `core/evidence_objects.py` writes canonical evidence objects under `artifacts/<run_id>/<tool_id>/`
- `report_generator.py` writes markdown reports to `var/lib/kai/reports/bbp`
- `packager.py` packages reports and recordings from other artifact roots
- `run_store.py` embeds findings inside file-backed run JSON
- `models.hil.Evidence` stores DB rows pointing to URIs and hashes

What is missing is a single artifact model and lifecycle:

- artifact creation event
- file path/object key
- hash
- mime type
- producing tool execution
- producing phase job
- producing branch
- producing run/campaign
- relation to observation/finding/report

Current logging is similarly fragmented:

- decision traces in `core/logs.py`
- hook audit JSONL in `core/hook_registry.py`
- HTTP audit middleware in `core/audit.py`
- trace/reasoning helpers in `core/trace.py`
- auth ledger in `core/kai_security_guardrails.py`

There is no unified `AuditEvent` stream or table.

## Missing Or Weak Audit Trail Elements

Auditability exists only as a collection of partial mechanisms.

Weaknesses:

- no single source of truth
- no common event schema
- no consistent entity IDs across workflow/run/tool/finding/report layers
- no branch/job-level provenance
- no normalized actor identity beyond scattered `user_id` fields
- no durable intention metadata
- no consistent "why this action was taken" record linked to execution artifacts

The repository has many files that mention auditability, but the runtime truth is still fragmented file logging.

## Current Tool Execution Model

### Real Elements

There are real tool adapters and real subprocess-backed adapter implementations for tools like:

- `subfinder`
- `amass`
- `nuclei`
- `trufflehog`

There is also a real Celery wrapper for tool execution.

### Missing Integration

These tools are not assembled into a real scan campaign pipeline.

Problems:

- tool execution is mostly ad hoc
- no canonical `ToolExecution` persistence model
- no branch/phase linkage
- no automatic observation normalization into DB-backed findings
- approvals are inconsistent between tool router and task router
- `routers/tools.py` stores approval-pending executions only in memory

The tool subsystem is more real than the campaign subsystem, but it is still not wired into a real autonomous backend.

## Current Security Boundary Enforcement

There are meaningful security controls in the repo:

- auth roles in `core/auth.py`
- RBAC in `core/hil_security.py`
- scope patterns in `core/scope.py`
- workflow-aware scope resolution in `core/scope_resolver.py`
- auth certificates and blocked-operation ledger in `core/kai_security_guardrails.py`
- tool authorization in `core/authorization_gate.py`

These are useful foundations.

But enforcement is inconsistent across entrypoints:

- some paths require only a header (`/scans/start`)
- some paths rely on workflow scope
- some paths rely on auth certificates
- some paths are dead/unwired
- some test-mode relaxations can bypass gates

There is no single orchestration layer that guarantees all phase/tool executions pass through the same policy contract.

## Current Support For Parallelism And Non-Blocking Branch Continuation

The backend does not currently implement real branch-aware orchestration.

Evidence:

- `core/orchestration_graph.py` is linear with limited alternate transitions, not persisted branches
- `full_scan_orchestrator.py` executes phases sequentially
- `workflow_store.py` tracks a single workflow status, not branch graphs
- `dorks.py` includes `branches` fields in the run JSON, but these are descriptive metadata, not execution branches
- no persisted dependency graph exists for jobs or branches
- no scheduler can continue independent branches while a risky branch waits for approval

The repository contains branch-like concepts in comments/docs, but not in the backend execution model.

## Exact Files That Appear Incomplete, Simulated, Dead, Or Misleading

Dead or unwired:

- `apps/backend/src/routers/autonomous_scan.py`
- `apps/backend/src/routers/scans.py`

Simulated or fixture-backed:

- `apps/backend/src/core/full_scan_orchestrator.py`
- `apps/backend/src/core/stakeholder_communicator.py` (deprecated, explicitly does nothing)
- `apps/backend/src/core/orchestration_graph.py` (prototype/in-memory)

In-memory where persistence is required:

- `apps/backend/src/core/hil_approval_system.py`
- `apps/backend/src/core/tool_execution_store.py`
- `apps/backend/src/routers/hil_approval.py`
- `apps/backend/src/routers/agent_zero.py`

File-backed placeholders where durable orchestration is required:

- `apps/backend/src/core/workflow_store.py`
- `apps/backend/src/core/run_store.py`
- `apps/backend/src/core/jobs.py`

Real but disconnected from campaign execution:

- `apps/backend/src/worker/celery_app.py`
- `apps/backend/src/core/tool_runner.py`
- `apps/backend/src/routers/tasks.py`
- `apps/backend/src/core/kai_orchestrator.py`

Misleading or overstated documentation:

- `docs/AUTONOMOUS_BBP_SCANNING_COMPLETE.md`
- `docs/HIL_APPROVAL_WORKFLOW.md`

Potentially misleading implementation splits:

- `apps/backend/hil_api/app.py`
- `apps/backend/src/app/main.py`

## Exact Files That Likely Need To Be Created Or Modified

Modify first:

- `apps/backend/src/main.py`
- `apps/backend/src/routers/workflows.py`
- `apps/backend/src/core/workflow_store.py`
- `apps/backend/src/core/tool_runner.py`
- `apps/backend/src/worker/celery_app.py`
- `apps/backend/src/core/authorization_gate.py`
- `apps/backend/src/core/hil_approval_system.py`
- `apps/backend/src/routers/hil_approval.py`
- `apps/backend/src/core/evidence_objects.py`
- `apps/backend/src/core/artifacts.py`
- `apps/backend/src/core/logs.py`
- `apps/backend/src/core/trace.py`

Create as the new canonical backend spine:

- `apps/backend/src/models/campaign.py`
- `apps/backend/src/models/intention.py`
- `apps/backend/src/schemas/campaigns.py`
- `apps/backend/src/schemas/intention.py`
- `apps/backend/src/routers/campaigns.py`
- `apps/backend/src/core/campaign_service.py`
- `apps/backend/src/core/branch_scheduler.py`
- `apps/backend/src/core/approval_gate_service.py`
- `apps/backend/src/core/tool_execution_service.py`
- `apps/backend/src/core/audit_events.py`
- `apps/backend/src/core/observation_service.py`
- `apps/backend/src/core/artifact_service.py`
- `apps/backend/src/worker/campaign_tasks.py`
- `apps/backend/alembic/versions/<new>_campaign_execution_schema.py`

Legacy routes to deprecate or remove after migration:

- `apps/backend/src/routers/autonomous_scan.py`
- `apps/backend/src/routers/scans.py`

## "Begin Scan" Status

Judgment: partial, fragmented, and misleading.

More precisely:

- the frontend can begin a hunt workflow
- the backend can persist lightweight workflow and run records
- the backend cannot prove real queued multi-phase scan execution from that path
- the advertised autonomous scan path is simulated and not even mounted

If forced to use one label only:

`begin scan` is partial overall, and the "autonomous scan" implementation is simulated/dead.

## Intention Tracking Gap Analysis

The repository does not currently implement intention as a first-class backend concept.

What exists today:

- `reasoning` strings on some requests
- "signed intent" in `kai_orchestrator.py` for Tier 3 permission slips
- scattered "why" summaries in file-based logs
- model/router reasoning fields for analysis and ranking

What is missing:

- no `IntentionRecord` entity
- no stable intention ID attached to actions
- no required declaration of actor, goal, policy basis, risk posture change, or approval requirement
- no propagation of intention metadata from API request -> workflow/campaign -> phase job -> tool execution -> artifact -> finding -> approval -> submission
- no audit schema where intention is queryable after the fact

Where intention should exist in the future architecture:

1. Campaign creation
   Record who initiated the campaign, why the campaign exists, what scope it targets, and what success criteria apply.

2. Phase-job creation
   Record why a phase job is being scheduled now, what prerequisite satisfied it, and what policy/risk posture applies.

3. Tool execution dispatch
   Record why a tool is being run, what observation or hypothesis it is testing, whether it is operator-initiated, planner-initiated, retry-initiated, or escalation-initiated, and whether approval is required.

4. Approval-gate creation
   Record why approval is required, what downstream branches depend on that approval, and what risk posture would change if approved.

5. Finding creation and submission
   Record whether the finding is produced from direct evidence, heuristic inference, duplicate escalation, exploit-chain reasoning, or manual operator review.

6. Audit events
   Every meaningful event should carry an `intention_id` plus enough contextual fields to reconstruct why the backend acted.

Without this, Kai cannot meet the stated repository requirement that intention influence orchestration decisions, approval gates, audit logs, tool execution policy, and reporting context.
