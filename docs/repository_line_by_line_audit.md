# Repository Line-by-Line Audit (Forensic Pass)

Date: 2026-03-13  
Auditor: Codex (forensic review mode)  
Scope: Source, tests, docs, scripts, guidance files (`AGENTS.md`, `skills/`, `hooks/`, `memory/`, `prompts/`)

## Executive Summary

This repository has a materially functional canonical backend spine (campaign orchestration, scheduler, result ingestion, correlation, review, export staging) and a healthy test baseline (`272 passed, 1 skipped`), but it still carries high-risk security and correctness gaps at router and bootstrap boundaries.

Most severe issues are not in core transition logic; they are in:

- inconsistent auth enforcement on sensitive routes
- route matching bugs in the tools API
- startup coupling to Vault token configuration
- parallel legacy systems that can drift from canonical behavior

The platform is close to a strong backend core, but not ready for exposed real-world operation until immediate auth, routing, and bootstrap issues are corrected.

## Audit Scope and Method

### In-scope inventory

- total tracked files reviewed for scope classification: `1162`
- backend source files: `308`
- tests files: `87`
- docs files: `22`

Excluded:

- generated/build/cache/venv/vendor artifacts (`node_modules`, `.next`, `__pycache__`, etc.)

### Method

1. Repository inventory and path-level scoping.
2. Line-by-line review of critical code paths:
   - routers
   - auth/scope/guardrails
   - campaign/workflow execution
   - tool registry/wrappers/health
   - persistence models/migrations
   - bootstrap/install scripts
   - canonical docs and contributor guidance
3. Static pattern scans for risky primitives and placeholder/simulated paths.
4. Runtime validation where feasible.

Validation run:

- `python3 -m pytest -q` (system python): `272 passed, 1 skipped in 30.85s`

## Strongest Parts (Implemented and Working)

- Canonical campaign/workflow persistence models and enums are present and wired (`campaign.py`, `workflow.py`, Alembic 0003/0004/0005).
- Scheduler idempotency and dependency-aware logic is materially implemented (`branch_scheduler.py`).
- Result ingestion includes replay and duplicate guards (`execution_result_service.py`).
- Deterministic finding correlation/review/export staging exists and is tested.
- Tool health service and CLI/API reporting are implemented with meaningful telemetry and validation fields.

## Highest-Risk Weaknesses

1. Sensitive canonical routes are exposed without auth dependencies.
2. Tools router has path-order collision causing static routes to be captured by `/{tool_id}`.
3. Tools approve/reject endpoints convert expected HTTP errors into 500s.
4. Startup can fail hard on missing `VAULT_TOKEN` due eager global `KeyManager()` import path.
5. Scope enforcement has parallel systems (`scope_guardrails.py` vs `scope.py`/`scope_resolver.py`) with different semantics.

---

## Detailed Findings by Category

## Security Findings

### S1. Canonical campaign/findings/diagnostics routes are unauthenticated

- Evidence:
  - `apps/backend/src/routers/campaigns.py:72-75` (`APIRouter` declarations without auth dependencies)
  - Mutation endpoints under:
    - `.../campaigns.py:160-190` (`/api/v1/campaigns/start`)
    - `.../campaigns.py:198-411` (`/start-workflow`, `/execute-workflow`)
    - `.../campaigns.py:558-567` (`/executions/ingest`)
    - `.../campaigns.py:570-621` (`/approvals/{gate_id}/decision`)
    - `.../campaigns.py:649-750` (finding review/prepare/export)
- Risk:
  - Unauthorized orchestration, state mutation, export staging, and diagnostics access.
- Recommendation:
  - Add route-level auth (`Depends(get_current_user)` + role-gated `require_roles(...)`) for all mutation endpoints; explicitly define read-only access policy.

### S2. Tools API is unauthenticated and identity context is caller-supplied query params

- Evidence:
  - `apps/backend/src/routers/tools.py:41` router has no auth dependency.
  - `.../tools.py:267-276` accepts `user_id`, `program_id`, `certificate_id` from query.
- Risk:
  - Weak trust boundary; identity and authorization context can be spoofed at request layer.
- Recommendation:
  - Require authenticated principal from token; derive `user_id` server-side; move cert/program to validated records.

### S3. Key-management API routes are unauthenticated

- Evidence:
  - `apps/backend/src/routers/key_management.py:12` router has no auth dependency.
  - Sensitive operations start at `...:114` (`/api/keys/admin/import`) and continue across file.
- Risk:
  - External key import/rotation operations callable without role checks.
- Recommendation:
  - Enforce admin-only auth dependency at router level; add audit events for key actions.

### S4. Legacy findings endpoints include unauthenticated mutation paths

- Evidence:
  - `apps/backend/src/routers/findings.py:46` router has no global auth dependency.
  - `...:133-180` `/findings/set_status` unauthenticated.
  - `...:182-201` `/findings/ingest/tool-result` unauthenticated.
- Risk:
  - Direct mutation of run/finding status without identity checks.
- Recommendation:
  - Gate all mutation endpoints with role checks; isolate legacy compatibility endpoints.

### S5. Path traversal guard uses unsafe string prefix checks in two paths

- Evidence:
  - `apps/backend/src/routers/docs.py:29` (`str(file).startswith(str(DOCS_DIR.resolve()))`)
  - `apps/backend/src/core/tool_adapters_bugbounty.py:526` (`str(path).startswith(str(allowed_root))`)
- Risk:
  - Prefix-based checks can be bypassed with sibling prefixes (e.g., `docs_bad`).
- Recommendation:
  - Replace with `Path.relative_to(...)` checks and explicit exception handling.

### S6. Dev/test auth gate bypass is environment-toggle based

- Evidence:
  - `apps/backend/src/core/authorization_gate.py:145-153`
- Risk:
  - Mis-set env flags can bypass scope/auth certificates.
- Recommendation:
  - Keep feature, but hard-fail if enabled outside `ENVIRONMENT in {test,development}` and emit startup warnings.

## Correctness Findings

### C1. Tools router static endpoints are shadowed by dynamic route

- Evidence:
  - Route order: `apps/backend/src/routers/tools.py`
    - dynamic `/{tool_id}` at `:187`
    - static `/categories` at `:217`, `/stats` at `:234`, `/catalog/list` at `:245`
  - Route match proof: `/api/v1/tools/categories` resolves to `/{tool_id}`.
- Risk:
  - Documented endpoints return wrong handler behavior.
- Recommendation:
  - Move static routes above dynamic routes.

### C2. Tools approve/reject handlers mask expected HTTP conflicts as 500

- Evidence:
  - `apps/backend/src/routers/tools.py:420-444`, `461-483`
  - `HTTPException(...)` raised in body is caught by broad `except Exception` and rethrown as 500.
- Risk:
  - Contract-breaking error semantics; poor operator diagnostics.
- Recommendation:
  - Add `except HTTPException: raise` before generic exception handling.

### C3. Legacy approvals router calls nonexistent registry API

- Evidence:
  - `apps/backend/src/routers/approvals.py:27` uses `reg.list()`.
  - Registry exposes `list_all()` (`apps/backend/src/core/tools.py:290`).
- Risk:
  - Runtime failure on `/approvals/tools`.
- Recommendation:
  - Replace with `list_all()` iteration.

### C4. Role dependency misuse in `/keys/import`

- Evidence:
  - `apps/backend/src/routers/keys.py:7` uses `require_roles(["admin"])`.
  - `require_roles` expects varargs (`core/auth.py:189`), not list.
- Risk:
  - Route effectively rejects all valid users (or behaves unexpectedly).
- Recommendation:
  - Use `require_roles("admin")`.

### C5. Workflow docs and runtime template source diverge

- Evidence:
  - Docs claim YAML template definitions (`docs/workflows.md:11-17`).
  - Runtime templates are hardcoded in `apps/backend/src/core/bugbounty_workflow_engine.py:41-112`.
- Risk:
  - Operator and developer expectations mismatch.
- Recommendation:
  - Either load YAML as authoritative source or update docs to state code-defined templates only.

### C6. `concurrency_limit` in local workflow executor is no-op

- Evidence:
  - `apps/backend/src/core/workflow_executor.py:523` sets and discards value.
- Risk:
  - API/CLI contract implies concurrency control that does not exist.
- Recommendation:
  - Implement bounded parallel stage execution or mark as unsupported and remove parameter.

### C7. Duplicate correlation graph conversion call

- Evidence:
  - `apps/backend/src/core/workflow_executor.py:788-795` calls `correlation_records_from_graph(...)` twice.
- Risk:
  - Minor inefficiency and readability debt.
- Recommendation:
  - Compute once and reuse.

## Maintainability Findings

### M1. Parallel workflow/scope systems increase drift risk

- Evidence:
  - Canonical scope policy: `core/scope_guardrails.py`
  - Legacy scope policy: `core/scope.py`
  - Dynamic resolver references file-based workflow store: `core/scope_resolver.py:56-99`
  - File-based workflow engine still active: `core/workflow_store.py`
- Risk:
  - Enforcement differences and undocumented precedence.
- Recommendation:
  - Consolidate to one scope authority for canonical routes; deprecate legacy file-based scope path.

### M2. Legacy monolith router (`findings.py`) mixes unrelated concerns

- Evidence:
  - `apps/backend/src/routers/findings.py` (>1,000 lines), includes detection, patching, remediation simulation, run-store mutations.
- Risk:
  - High coupling, hard testing, security policy inconsistency.
- Recommendation:
  - Split by bounded context (review, remediation, evidence, detection); gate legacy endpoints.

### M3. Duplicate contributor docs with overlapping setup guidance

- Evidence:
  - `docs/developer_guide.md`
  - `docs/development_guide.md`
- Risk:
  - Contributor confusion and drift.
- Recommendation:
  - Keep one canonical developer guide and archive/remove duplicate.

## Operational Health Findings

### O1. Startup hard-fails on missing Vault token due eager global key manager init

- Evidence:
  - `apps/backend/src/core/key_manager.py:175` (`key_manager = KeyManager()`)
  - imported by `apps/backend/src/routers/keys.py:2`
  - `KeyManager` raises when token unavailable (`key_manager.py:55-58`)
  - This occurs during app import, before request handling.
- Risk:
  - Backend boot failure in environments where Vault is optional.
- Recommendation:
  - Lazy-init key manager in route handlers or dependency function; fail only when key import endpoint is used.

### O2. Optional router imports silently swallow errors

- Evidence:
  - `apps/backend/src/main.py:375-390` catches broad exception and `pass`.
- Risk:
  - Broken optional subsystems become invisible at startup.
- Recommendation:
  - Log warning with module name and exception details; include in readiness diagnostics.

### O3. Unsafe default DB credentials in code fallback

- Evidence:
  - `apps/backend/src/core/hil_db.py:10` default URL includes `k1:k1pass`.
- Risk:
  - Misconfigured deployments may run with weak known credentials.
- Recommendation:
  - Remove credentialed fallback; require explicit `DATABASE_URL`.

### O4. Bootstrap scripts are not reproducible and likely brittle

- Evidence:
  - `install/bootstrap_ubuntu_22_04.sh:33-43` installs `@latest` Go binaries.
  - `scripts/bootstrap.sh:34` installs Python packages that are not standard pip equivalents for some tools.
- Risk:
  - Non-deterministic builds; frequent install breakage.
- Recommendation:
  - Pin versions and split “best effort optional” installs from required baseline verification.

### O5. CLI default API URL conflicts with documented backend port

- Evidence:
  - CLI default: `apps/backend/src/cli/main.py:46` (`http://localhost:8000`)
  - README backend startup uses `8080` (`README.md:77`)
- Risk:
  - First-run CLI failures for new contributors.
- Recommendation:
  - Align default ports or centralize via shared config.

## Documentation Drift Findings

### D1. README frontend path is stale for current operator console structure

- Evidence:
  - `README.md:31,50` references `apps/frontend/`
  - repo contains both `apps/frontend/` and `apps/frontend-operator/` (current operator surface).
- Recommendation:
  - Clarify which frontend is canonical operator console.

### D2. Security model overstates route-level enforcement consistency

- Evidence:
  - `docs/security_model.md:12-23` describes role checks generally.
  - Multiple sensitive routers are still open (`campaigns.py`, `tools.py`, `key_management.py`).
- Recommendation:
  - Update docs to reflect actual exposure and remediation plan.

---

## Quick Wins (Non-breaking, High Impact)

1. Add auth dependencies to canonical `/api/v1/campaigns`, `/api/v1/findings`, `/api/v1/diagnostics`, and `/api/v1/tools`.
2. Reorder tools routes so static paths are declared before `/{tool_id}`.
3. Preserve `HTTPException` in tools approve/reject handlers.
4. Replace `startswith` path guards with `relative_to`.
5. Lazy-load `KeyManager` to prevent import-time crashes.

## Medium-Term Refactors

1. Consolidate scope enforcement to one canonical policy engine.
2. Decompose legacy `findings.py` and retire file-based `workflow_store` from active paths.
3. Make workflow templates single-sourced (code or YAML, not both).
4. Implement actual concurrency behavior or remove exposed no-op controls.

## Long-Term Architecture Recommendations

1. Enforce a single canonical mutation surface (`/api/v1/...`) and isolate legacy routes behind explicit compatibility toggles.
2. Move all approval and execution request state to durable DB-backed records (replace in-memory tool execution store).
3. Add comprehensive authz regression tests across all mutation endpoints.
4. Add startup diagnostics endpoint section that reports disabled/failed optional modules explicitly.

---

## Remediation Priority Grouping

### Fix Immediately

- S1, S2, S3, S4, S5, C1, C2, O1

### Fix Before Real-World Use

- C3, C4, M1, O2, O3, O4, D2

### Fix Before Production

- C5, C6, M2, O5, D1

### Refactor Later

- C7, M3, legacy route surface consolidation

### Documentation Only

- Clarify template source-of-truth and frontend canonical path.

---

## Test Coverage Gaps

Missing or weak tests for:

- authz on canonical `/api/v1/campaigns` and `/api/v1/findings` mutation routes
- tools route precedence (`/categories`, `/stats`, `/catalog/list`)
- HTTPException passthrough correctness in tools approve/reject flows
- path traversal protections for docs/hook collection readers
- startup behavior when Vault is intentionally absent

## Direct Code Changes During Audit

None.  
This pass was forensic/documentation focused as requested.

## Final Readiness Judgment

- Core canonical workflow engine: **functionally strong for internal controlled use**.
- Security and interface hardening: **not yet sufficient for exposed real-world operation**.
- Immediate path to improve: authz normalization + tools routing fixes + startup decoupling from Vault.
