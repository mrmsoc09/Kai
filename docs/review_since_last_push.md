# Pre-Push Review and Remediation (Since Last Pushed Baseline)

Date: 2026-03-13  
Baseline: `origin/main` (`968cad6a076b89d731abfb49218379ddbb92aee6`)

## Review Scope

This pass covered repository changes since baseline using:

- `git diff --name-status origin/main`
- `git ls-files --others --exclude-standard`
- focused inspection of security/correctness risk areas:
  - scope/auth gates
  - scheduler/worker dispatch
  - bug bounty API/CLI mutation surfaces
  - pytest bootstrap path

## Critical/High Findings Addressed

1. **P1 scope default safety regression**
   - File: `config/scope_guardrails.yaml`
   - Fix: switched default to deny-by-default (`strict_allowlist: true`).
   - Coverage: `tests/test_scope_guardrails.py::test_repo_default_scope_policy_is_deny_by_default`.

2. **P1 pytest bootstrap regression**
   - File: `tests/conftest.py`
   - Fix: moved repo path bootstrap before `tests.asgi_test_client` import.
   - Validation: running pytest from `/tmp` against repo tests now succeeds.

3. **P2 sync auth scope mismatch**
   - File: `apps/backend/src/core/authorization_gate.py`
   - Fix: sync `scope_validator()` now uses workflow-aware resolver when `workflow_id` is provided.
   - Coverage: `tests/test_authorization_gate_sync_scope.py`.

4. **P2 duplicate dispatch risk**
   - File: `apps/backend/src/core/bug_bounty_hunting_service.py`
   - Fix: `dispatch_due_schedules()` now reserves `next_scheduled_run_at` before enqueue to prevent repeated immediate dispatch.
   - Coverage: `tests/test_bug_bounty_dispatch_safety.py`.

5. **P3 broker failure diagnostics (also resolved)**
   - File: `apps/backend/src/core/bug_bounty_hunting_service.py`
   - Fix: per-schedule Celery enqueue is guarded; failures persist `DISPATCH_FAILED` status/reason and return failed dispatch responses.

## Validation Results

- Targeted regression suite:
  - `.venv/bin/python -m pytest -q tests/test_scope_guardrails.py tests/test_scope_resolver.py tests/test_authorization_gate_sync_scope.py tests/test_bug_bounty_dispatch_safety.py tests/test_bug_bounty_continuous.py tests/test_api_security_and_routing.py`
  - Result: `37 passed`

- Full suite:
  - `.venv/bin/python -m pytest -q`
  - Result: `291 passed, 1 skipped`

- Bootstrap portability check:
  - `cd /tmp && /home/k1-admin/Kai/.venv/bin/pytest -q /home/k1-admin/Kai/tests/test_bug_bounty_continuous.py -k phase6 --maxfail=1`
  - Result: `1 passed, 4 deselected`

## Push Recommendation

**Recommendation: ready to push.**

Reasoning:

- all critical/high release blockers identified in pre-push review were fixed;
- regression coverage was added for each fixed issue class;
- full pytest and out-of-repo-cwd bootstrap validation passed.
