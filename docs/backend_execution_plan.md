# Backend Execution Plan

## Planning Goal

The near-term goal is not "make Kai look orchestrated".

The goal is:

- one canonical scan-start API
- one canonical persistence model
- one real queue-backed execution path
- one real approval-gate model
- one real artifact/observation/finding lineage
- one real audit/intention model

This plan assumes `apps/backend/src/main.py` remains the canonical API app, PostgreSQL remains the source of truth, Redis/Celery remains the worker path, and existing file-backed helpers are gradually wrapped or retired rather than treated as final runtime architecture.

## Current Constraint Summary

The main blocker is not missing UI.

The main blocker is lack of a canonical execution spine tying together:

- workflow creation
- persisted run state
- worker dispatch
- phase/job progression
- tool execution
- approval gating
- findings/artifacts
- audit history
- intention metadata

Until that exists, every other orchestration feature will remain partial.

## Recommended Implementation Order

### 1. Pick And Enforce The Canonical Scan-Start Surface

Build first:

- one canonical API for campaign creation and start
- one canonical service layer behind it
- one canonical campaign persistence model

Recommendation:

- keep `/workflows` readable for UI compatibility
- introduce `/campaigns` as the new execution surface
- make workflow creation delegate into campaign creation instead of remaining file-only
- explicitly deprecate `routers/autonomous_scan.py` and `routers/scans.py`

Why first:

- there is currently no trustworthy "begin scan" boundary
- everything else depends on knowing where execution officially begins

### 2. Introduce Core Execution Domain Models In PostgreSQL

Create DB-backed models for:

- `Program`
- `ScopeTarget`
- `CampaignRun`
- `ExecutionBranch`
- `PhaseJob`
- `ApprovalGate`
- `ToolExecution`
- `Observation`
- `Artifact`
- `Finding`
- `ScanNote`
- `SubmissionDraft`
- `AuditEvent`
- `IntentionRecord`

Minimal required fields:

- stable IDs
- status/state
- parent/foreign-key relationships
- timestamps
- actor identity
- branch/dependency linkage
- retry counters
- intention reference

Why second:

- resumability, branch-local gating, and auditability all require durable records

### 3. Add Intention As A First-Class Record Before Full Orchestration

Do not postpone intention until later.

Add `IntentionRecord` before broad runtime implementation so every new action path can attach to it from day one.

Recommended `IntentionRecord` fields:

- `id`
- `initiator_type` (`user`, `operator`, `planner`, `policy`, `retry`, `system`)
- `initiator_id`
- `goal`
- `reason`
- `target_kind`
- `target_id`
- `campaign_run_id`
- `branch_id`
- `risk_posture_before`
- `risk_posture_after`
- `policy_basis`
- `requires_hil`
- `scope_basis`
- `metadata`

Where to require intention immediately:

- campaign creation
- branch creation
- phase-job scheduling
- tool dispatch
- approval-gate creation
- finding promotion
- submission-draft creation

### 4. Build The Queue-Backed Campaign Runtime

Create a real service boundary:

- API writes `CampaignRun`, root `ExecutionBranch`, first `PhaseJob`, `IntentionRecord`, and `AuditEvent`
- worker consumes a `PhaseJob`
- phase runner updates job status in DB
- phase runner emits next jobs/branches based on outcomes

Recommendation:

- use Celery for initial implementation because it already exists
- create dedicated task entrypoints such as:
  - `campaign_phase_execute`
  - `tool_execution_dispatch`
  - `approval_resume_branch`
  - `submission_package_build`

Do not use filesystem JSONL queues for core runtime.

### 5. Normalize Tool Execution Around `ToolExecution`

All tool runs should flow through a single service that:

- validates scope/policy
- resolves the applicable intention
- creates a `ToolExecution` row
- writes structured execution logs
- captures artifacts
- produces normalized observations
- optionally promotes observations into findings

Keep existing adapters, but stop allowing tool execution state to live only in:

- Celery result backend
- in-memory approval stores
- ad hoc JSON files

### 6. Implement Observation And Artifact Lineage

Add a canonical flow:

1. tool run completes
2. raw output becomes artifact records
3. parser emits observations
4. policy/routing promotes some observations into findings
5. reports reference findings plus artifact IDs

Artifacts must include:

- storage location
- SHA256
- mime type
- producing tool execution
- producing phase job
- associated branch and campaign

Observations should be the first durable normalized output from tools. Findings should be promoted, reviewable entities, not the only place tool results appear.

### 7. Replace In-Memory Approval Stores With Persisted Approval Gates

Build `ApprovalGate` as a DB-backed entity with:

- `id`
- `campaign_run_id`
- `branch_id`
- `phase_job_id`
- `tool_execution_id` if relevant
- `gate_type`
- `status`
- `reason`
- `required_by_policy`
- `blocking_scope`
- `opened_by_intention_id`
- `resolved_by_user_id`
- `resolved_at`

Then:

- replace private `HiLApprovalSystem()` instances
- make approval APIs operate on persisted gates
- make approval resolution enqueue resume work for only affected dependent branches

### 8. Add Branch Scheduler Semantics

The scheduler should operate on a dependency graph, not a single workflow status.

Recommended rules:

- each `ExecutionBranch` belongs to a `CampaignRun`
- each `PhaseJob` belongs to one branch
- jobs may depend on one or more upstream jobs
- approval gates attach to one branch/job
- only downstream dependents of a blocked node are paused
- unrelated branches continue if policy allows

This is the core requirement for branch-local HiL.

### 9. Migrate Legacy File-Backed Surfaces To Read Models Or Compatibility Layers

After the DB/runtime spine exists:

- keep file-backed exports only as derived artifacts or compatibility read models
- stop using `workflow_store.py`, `run_store.py`, and `jobs.py` as execution truth
- continue exposing legacy endpoints temporarily, but back them with DB state

### 10. Retire Or Mark Simulated/Dead Scan Paths

Once the canonical runtime exists:

- remove or hard-deprecate `routers/autonomous_scan.py`
- remove or hard-deprecate `routers/scans.py`
- rewrite overstated docs to match the real runtime

## Which Pieces Should Be Built First To Make "Begin Scan" Real

The minimum viable real scan path is:

1. `POST /campaigns`
   Creates `CampaignRun`, root `ExecutionBranch`, first `PhaseJob`, `IntentionRecord`, `AuditEvent`.

2. worker task picks up first `PhaseJob`
   Moves job from `pending` to `running`.

3. phase runner dispatches first real tool through `ToolExecution`
   At minimum, passive recon.

4. tool result persists artifacts and observations
   No in-memory-only result paths.

5. phase completion updates DB state and enqueues next phase jobs
   Status progression becomes durable.

6. risky tool/phase creates `ApprovalGate`
   Only dependent branches block.

Until those six pieces exist, "begin scan" is still not real.

## Recommended Domain Entities For Intention-Aware Execution

### Core Entities

- `Program`
  Public program metadata and policy-facing identity.

- `ScopeTarget`
  Canonical scoped assets/domains/endpoints per program.

- `CampaignRun`
  Root execution record for a user-initiated or policy-initiated hunt.

- `ExecutionBranch`
  Branch-local execution lane for a hypothesis, target slice, or phase split.

- `PhaseJob`
  Discrete unit of work within a branch.

- `ToolExecution`
  One adapter/runtime execution with policy, approval, and output metadata.

- `Observation`
  Normalized result emitted by a tool execution before finding promotion.

- `Artifact`
  File/object metadata and lineage.

- `Finding`
  Reviewable vulnerability candidate with evidence links.

- `ApprovalGate`
  Human review pause attached to one branch/job/tool execution.

- `SubmissionDraft`
  Persisted submission/report package awaiting approval or dispatch.

- `AuditEvent`
  Immutable normalized event stream.

- `IntentionRecord`
  First-class declaration of why the system acted.

### Relationship Sketch

- `CampaignRun` has many `ExecutionBranch`
- `ExecutionBranch` has many `PhaseJob`
- `PhaseJob` has many `ToolExecution`
- `ToolExecution` has many `Artifact`
- `ToolExecution` has many `Observation`
- `Observation` may promote to `Finding`
- `ApprovalGate` belongs to one branch and usually one job
- `AuditEvent` links to any of the above
- `IntentionRecord` links to the initiating entity and is referenced by downstream actions

## Recommended Strategy For Resumable Branch-Based Orchestration

### State Model

Each `PhaseJob` should have durable statuses such as:

- `pending`
- `queued`
- `running`
- `waiting_for_approval`
- `blocked`
- `completed`
- `failed`
- `cancelled`

Each `ExecutionBranch` should have durable statuses such as:

- `ready`
- `running`
- `paused`
- `blocked`
- `completed`
- `failed`
- `cancelled`

### Resume Strategy

On worker/API startup:

- recover `queued` and `running` jobs using heartbeat/lease rules
- reset stale jobs to `pending_retry` or `failed`
- leave `waiting_for_approval` jobs untouched
- recompute branch status from child jobs

Resume should be based on persisted data only, not in-memory caches.

### Dependency Strategy

Use explicit dependency rows or edges:

- parent branch -> child branch
- upstream phase job -> downstream phase job

Scheduler rule:

- a job becomes runnable only when all required dependencies are completed and no active approval gate blocks its branch

## Recommended Strategy For HiL Pauses That Block Only Dependent Branches

### Rule

When a risky job needs approval:

- create `ApprovalGate`
- mark the current branch `paused`
- mark only descendant jobs/branches that depend on this branch as blocked
- do not pause siblings or unrelated branches

### Implementation Shape

1. risky condition detected during planning or execution
2. create `ApprovalGate` with `branch_id`, `phase_job_id`, and `intention_id`
3. scheduler excludes only blocked descendants from runnable set
4. approval API resolves gate
5. worker task reactivates the paused branch
6. scheduler recomputes runnable downstream jobs

### Example

- Branch A: passive recon on wildcard assets
- Branch B: credentialed API recon
- Branch C: intrusive validation of a possible finding

If Branch C requires approval:

- Branch C pauses
- its dependents pause
- Branch A and Branch B continue if policy allows

This is the repository requirement. The current workflow model cannot express it.

## Recommended Intention Introduction Points

Intention should not be added as a free-form note field. It needs a required lifecycle.

Immediate write points:

- campaign start request
- automatic branch split
- phase-job creation
- retry scheduling
- escalation to approval
- tool execution dispatch
- finding promotion
- submission drafting

Immediate read/use points:

- policy engine
- approval-gate reason text
- audit event rendering
- operator review UI
- report/submission context

## Backward Compatibility Strategy

Preserve current public behavior where practical, but move truth behind it.

Recommended compatibility approach:

- keep `/workflows` as a read/write facade during migration
- keep `/runs` as a derived read model
- keep `/api/v1/tasks` for standalone tool execution
- translate legacy file-backed workflow fields from DB state until UI is migrated
- mark dead routes with explicit deprecation responses instead of leaving them silently unmounted

## Risks, Unknowns, And Assumptions

### Risks

- multiple partially overlapping subsystems may cause migration confusion if not explicitly deprecated
- file-backed and DB-backed states can diverge during transition
- current docs may bias contributors toward simulated code paths unless corrected
- there are already two approval-singleton patterns and multiple orchestration concepts in-tree

### Unknowns

- how much of the current frontend depends on exact workflow JSON shape
- whether Redis/Celery is considered mandatory in all dev environments
- whether any external consumers rely on the unwired scan routes
- whether `kai_orchestrator.py` must be preserved as a separate compliance execution API

### Assumptions

- PostgreSQL remains the source of truth
- Redis/Celery remains the worker runtime
- existing tool adapters remain reusable
- branch-local HiL is a hard requirement, not optional
- intention tracking must be queryable and durable, not log-only

## Recommended Intention-Aware Orchestration Design

Use a DB-backed orchestration core with this shape:

1. API request creates `CampaignRun` and `IntentionRecord`.
2. planner creates one or more `ExecutionBranch` plus initial `PhaseJob` rows.
3. scheduler enqueues runnable jobs to Celery.
4. each worker creates a `ToolExecution` or phase result record tied to the originating `IntentionRecord`.
5. tool outputs become `Artifact` plus `Observation`.
6. observation routing promotes eligible observations into `Finding`.
7. risky jobs open `ApprovalGate` rows tied to a branch and intention.
8. approval resolution resumes only affected branches.
9. every meaningful transition emits a normalized `AuditEvent`.
10. reports and submissions are derived from persisted findings/artifacts, not from ephemeral model output.

This design is the shortest path from the current fragmented backend to a real autonomous bug bounty execution system that satisfies:

- resumability
- branch-aware orchestration
- branch-local HiL gating
- real tool execution
- durable auditability
- explicit intention tracking
