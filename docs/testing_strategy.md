# Testing Strategy

## Goals

- Verify canonical campaign execution behavior from persistence through review/export staging.
- Keep tests deterministic and isolated from external services.
- Detect regressions in transition logic, replay safety, and diagnostics visibility.

## Test Layers

## 1. Canonical workflow tests

Primary coverage includes:

- model relationships and transition rules
- campaign start/seeding/scheduling
- result ingestion and scheduler re-entry
- approval decision integration
- finding correlation and evidence linking
- review actions and draft transitions
- provider payload preview/export staging
- idempotency and diagnostics behavior

Representative files:

- `tests/test_campaign_execution_models.py`
- `tests/test_campaign_transition_rules.py`
- `tests/test_campaign_orchestration.py`
- `tests/test_campaign_result_ingestion.py`
- `tests/test_finding_correlation.py`
- `tests/test_finding_review.py`
- `tests/test_submission_export_adapters.py`
- `tests/test_idempotency_and_diagnostics.py`
- `tests/test_tool_registry_catalog.py`
- `tests/test_tool_adapters_bugbounty.py`
- `tests/test_bugbounty_workflow_engine.py`

## 2. Route and policy checks

- health/diagnostic endpoints
- report and mailer routes
- secret-management policy gates (`scripts/check_unmanaged_secrets.py`)

## Execution Commands

Full suite:

```bash
python3 -m pytest -q
```

Targeted groups:

```bash
python3 -m pytest -q tests/test_campaign*
python3 -m pytest -q tests/test_reports*
python3 -m pytest -q tests/test_hil*
python3 -m pytest -q tests/test_tool_registry_catalog.py tests/test_tool_adapters_bugbounty.py tests/test_bugbounty_workflow_engine.py
```

Secret gate:

```bash
python3 scripts/check_unmanaged_secrets.py
```

CI-aligned quality command:

```bash
bash scripts/check_backend_quality.sh
```

## Harness Notes

- `tests/conftest.py` sets test defaults including `K1_TEST_MODE=true` and isolated artifact root.
- A probe-gated fallback for `anyio.to_thread.run_sync` is present only for environments where thread handoff is non-functional; original behavior is restored after session.
- ASGI-based test client is used to avoid environment-specific deadlocks in thread-portal `TestClient`.

## Non-Goals in Current Test Layer

- No external bug bounty provider submission tests.
- No real outbound scanning in tests.
- No requirement for live third-party credentials.
