# Phase 5 Preflight Readiness Report

Date: 2026-03-13  
Scope: verification-first readiness check for Phase 5 bug bounty hunting engine work.

## Overall Readiness

Status: **Ready to proceed now**, with targeted guardrails to avoid duplicate subsystems.

The repository already contains canonical DB-backed models, services, API routes, and tests for most Phase 5 capabilities:

- program/opportunity ingestion
- monitored targets
- recurring schedule definitions
- pre-run readiness gating
- workflow execution persistence
- run-to-run delta detection
- candidate queueing and report draft creation

## 1. Canonical Model Inventory (What Already Exists)

Reuse these as authoritative:

- Program/opportunity + scope inventory:
  - `Program`, `ScopeTarget` in `apps/backend/src/models/campaign.py`
- Recurring jobs + readiness + deltas + analyst queue:
  - `HuntScheduleJob`, `HuntReadinessRecord`, `WorkflowDeltaRecord`, `AnalystQueueItem` in `apps/backend/src/models/bug_bounty.py`
- Workflow execution persistence:
  - `WorkflowRun`, `StageRun`, `WorkflowFinding`, `CorrelationRecord` in `apps/backend/src/models/workflow.py`
- Existing report/evidence path:
  - `SubmissionDraft`, `Artifact`, `AuditEvent`, existing findings/review pipeline in `apps/backend/src/models/campaign.py` and `apps/backend/src/models/hil.py`

Migration coverage is present (`0004`, `0005`, `0006` under `apps/backend/alembic/versions`), and model exports are wired in `apps/backend/src/models/__init__.py`.

## 2. Workflow Launch Path Readiness

Canonical launch path is present and repeatable:

- `BugBountyHuntingService.trigger_schedule()` invokes `WorkflowExecutor.execute_template()` with program + scope context.
- Workflow runs persist through canonical DB records (`workflow_runs`, `stage_runs`, `tool_executions`, `workflow_findings`, `correlation_records`) and disk artifacts (`output/...`).
- Blocked/skipped launches are durably captured via `HuntReadinessRecord`.
- Repeated invocations are supported (schedule-driven and ad-hoc trigger).

Important current behavior to account for:

- DB-backed workflow execution forces `effective_concurrency_limit = 1` in `WorkflowExecutor` for AsyncSession safety.
- Scheduler triggering is implemented as service/API/CLI invocation (`run_due_schedules`) rather than a built-in always-on beat loop in this layer.

## 3. Tool Health / Readiness Integration

Ready for pre-run gating:

- `tool_health_service.build_dashboard()` is integrated into readiness checks in `BugBountyHuntingService.evaluate_readiness()`.
- Required tool sets are derived from workflow template steps.
- Degraded/unavailable required tools block run launch with explicit `BLOCKED_BY_HEALTH`.

## 4. Scope / Policy Integration

Program-aware gating is implemented:

- Program scope is converted into `ScopePolicy` from canonical `ScopeTarget` rows (`_build_program_scope_policy`).
- Readiness gates evaluate target against canonical in/out scope and safe-mode constraints.
- Dynamic workflow-linked scope support exists in `scope_resolver.py` and async authorization gate path (`authorization_gate.py`).

Risk to avoid during Phase 5:

- Do not extend legacy `core/scope.py` behavior; it is a compatibility layer and uses alternate config path conventions.
- Keep new scope logic anchored in canonical `ScopeTarget` + `scope_guardrails` + `scope_resolver`.

## 5. Persistence Extension Readiness

Current DB schema already supports planned Phase 5 entities:

- monitored targets: `ScopeTarget` monitoring fields
- scheduled jobs: `HuntScheduleJob`
- blocked/skipped run records: `HuntReadinessRecord`
- delta records: `WorkflowDeltaRecord`
- candidate queue: `AnalystQueueItem`
- report drafts/artifacts: existing `SubmissionDraft` + `Artifact`

No new parallel persistence layer is needed for Phase 5 start.

## 6. API / CLI Readiness

API is already structured for Phase 5 operations:

- router: `apps/backend/src/routers/bug_bounty.py`
- endpoints include:
  - program import/list
  - target update/list
  - schedule create/list/update
  - readiness checks
  - trigger single schedule / run due schedules
  - deltas
  - candidate queue
  - report draft generation

CLI support exists in `apps/backend/src/cli/commands/bug_bounty.py` for core operations (program import/list, targets, schedules, run-due, deltas, candidates).

## Naming Collisions / Duplication Risks to Avoid

1. **Legacy workflow subsystem**  
   `core/workflow_store.py` + `/workflows` router are file-based legacy state machine paths.  
   Phase 5 work should stay on canonical DB-backed bug bounty paths (`/api/v1/bug-bounty`, `BugBountyHuntingService`, `WorkflowExecutor` DB mode).

2. **Multiple scope entry points**  
   `core/scope.py` compatibility helper coexists with canonical `scope_guardrails`/`scope_resolver`.  
   Do not split policy logic across both for new work.

3. **Overlapping “opportunity” concepts**  
   Existing `opportunities`/`workflow_store` logic is separate from canonical `Program.config_json["opportunity"]`.  
   Avoid dual-write behavior.

## Small Blockers Before/At Start of Phase 5

These are not stop-ship blockers, but should be handled early in Phase 5 execution work:

1. Add an explicit recurring runner integration point (Celery beat/job runner or equivalent) that calls canonical `run_due_schedules` on interval.
2. Keep scheduler concurrency semantics explicit: schedule-level max concurrency is enforced for active runs, but per-run tool concurrency is effectively serialized in DB mode.
3. Maintain strict use of canonical bug bounty routes/services; do not extend legacy `/workflows` for new Phase 5 behavior.

## Validation Evidence

Targeted readiness tests executed in this pass:

- `tests/test_bug_bounty_continuous.py`
- `tests/test_workflow_run_persistence.py`
- `tests/test_workflow_run_api.py`
- `tests/test_tool_health_dashboard.py`

Result: **30 passed**.

## Preflight Recommendation

Proceed with Phase 5 implementation now using existing canonical structures.  
Focus on extension and hardening inside:

- `BugBountyHuntingService`
- `WorkflowExecutor` / `WorkflowRunService`
- canonical models in `campaign.py`, `workflow.py`, `bug_bounty.py`
- `/api/v1/bug-bounty` router + existing CLI command group

Do not create a second scheduler, second workflow state system, or second persistence model set.
