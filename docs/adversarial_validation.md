# Adversarial Validation Report

Date: 2026-03-11  
Scope: Canonical campaign execution, approval gating, scheduler replay, and provider export staging.

## Test Commands

- `/usr/bin/python3 -m pytest -q tests/test_campaign_result_ingestion.py tests/test_campaign_orchestration.py tests/test_submission_export_adapters.py tests/test_idempotency_and_diagnostics.py`
- `/usr/bin/python3 -m pytest -q`

## Edge Cases Tested

### 1. Idempotency Replay

- Replay identical execution-ingestion payloads for the same `ToolExecution`.
- Assert no duplicate artifacts.
- Assert no duplicate observations.
- Assert no duplicate finding creation path is re-triggered on replay.
- Assert deterministic replay audit event (`phase_job.result.replay_ignored`).

### 2. Approval Gate Transition Abuse

- Double approval decision on same gate (`PENDING -> APPROVED`, then `APPROVED -> APPROVED`).
- Approval after rejection (`PENDING -> REJECTED`, then attempt `REJECTED -> APPROVED`).
- Decision after completion (`PENDING -> APPROVED`, then attempt `APPROVED -> REJECTED`).
- Assert invalid transitions raise deterministically and produce conflict audit events.

### 3. Export Staging Under Invalid Readiness

- Export with finding not approved.
- Export with incomplete draft/package state.
- Export with missing evidence.
- Assert `ready=false`, validation failures are explicit, and metadata is still staged consistently.
- Assert route-level behavior returns `422` for not-ready export results.

### 4. Scheduler Replay Safety

- Re-run scheduler on the same campaign graph.
- Assert no duplicate approval-gate creation.
- Assert no duplicate dispatch when existing gate/active execution state already controls flow.

## Failures Discovered

No runtime/state-machine defects were reproduced in this pass.  
Core adversarial scenarios were already handled by existing logic.

## Fixes Applied

No production service logic changes were required.

Hardening improvements in this pass were test-focused:

- Added adversarial replay test explicitly asserting no duplicate finding creation path is re-entered.
- Added approval transition conflict tests for post-terminal gate decisions.
- Added export staging tests for incomplete draft and missing evidence cases.
- Added route-level export test asserting `422` for not-ready staging response.

## Remaining Risk Areas

1. Concurrency controls are still service-layer/transactional best effort; no explicit DB row-version locking is present.
2. Replay conflict handling is deterministic for covered paths, but high-volume out-of-order worker callbacks remain a risk area for future stress tests.
3. Legacy non-canonical routers still coexist with canonical `/api/v1` routes and may have different semantics; frontend should bind to canonical contracts only.

## Current Robustness Assessment

- Canonical backend workflows remained stable under adversarial replay/transition checks.
- Full suite status after this pass: `183 passed, 1 skipped`.
- System is resilient for the tested first-pass adversarial scenarios, with remaining risks primarily around deeper concurrent-load conditions.
