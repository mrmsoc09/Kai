# KAI Unified Execution Plan

Merged from:
- `docs/MASTER_EXECUTION_LIST.md`
- `docs/GAP_CLOSURE_TODO.md`
- `docs/TODO.md`
- `docs/K1_COMPREHENSIVE_TODO_LIST.md`
- root `_inv_*.txt` scaffolds
- inline code TODO/FIXME/HACK markers

Status legend: `todo`, `in_progress`, `done`, `blocked`.

## Completed Foundation

| ID | Status | Source | Scope | Task | Definition of Done | Risk | Verify |
|---|---|---|---|---|---|---|---|
| KAI-001 | done | `docs/MASTER_EXECUTION_LIST.md:M-001..M-003` | `ops/`, `claims/`, `benchmarks/`, `scripts/` | Toolpacks/claims/benchmarks foundations | Canonical files and deterministic benchmark path exist | LOW | `python3 scripts/validate_claims.py`; `python3 scripts/run_benchmarks.py --verify-claims` |
| KAI-002 | done | `docs/MASTER_EXECUTION_LIST.md:M-004..M-014` | `apps/backend/src/core`, `routers`, `tests` | Auth ledger, evidence parity, OPSEC policy, submission state/SLA/comms, payout ledger | End-to-end defensive workflow controls implemented | MED | compile checks + targeted unit tests |

## Remaining Core Backlog

| ID | Status | Source | Scope | Task | Definition of Done | Risk | Verify |
|---|---|---|---|---|---|---|---|
| KAI-003 | done | `docs/MASTER_EXECUTION_LIST.md:M-015` + `docs/GAP_CLOSURE_TODO.md:T-015` | `apps/backend/src/core/*opportunity*`, `tests` | Opportunity scoring v1 (EV + duplicate risk + effort) | Ranked plan entries with explainable score factors | MED | `python3 -m py_compile ...`; scorer tests |
| KAI-004 | done | `M-016` + `docs/TODO.md` duplicate checks | `routers/reports.py`, `core/finalize.py`, `core/duplicates.py`, `tests` | Pre-submit duplicate-risk hard gate with override path | Submission blocked for high-risk duplicates unless explicit override | MED | gate tests |
| KAI-005 | done | `M-017` | `core/report_validator.py`, `routers/reports.py`, `tests` | Report quality gate + evidence-to-claim trace matrix | Submission blocked below quality threshold | MED | validator tests |
| KAI-006 | done | `M-018` | `core/graph.py`, `core/vector_store.py`, retriever module, `tests` | Hybrid retriever (vector + graph provenance ranking) | Retrieval includes provenance-ranked context and scoring rationale | MED | retrieval tests/benchmarks |
| KAI-007 | done | `M-019` + defensive policy docs | DAG/orchestration modules + tests | Defensive-only DAG semantics | No exploitation semantics; defensive phases only | HIGH | orchestration negative tests |
| KAI-008 | done | `M-020` | reflective/learning modules + tests | Bounded reflective learning loop tied to outcomes | bounded updates, reversible changes, reason logs | HIGH | simulation tests |
| KAI-009 | done | `M-021` + `docs/TODO.md` Vault items | secret manager, integrations, startup checks | Vault migration closure for unmanaged secrets | all prod secret reads via manager, fail-closed startup | HIGH | startup checks + static grep |
| KAI-010 | done | `M-022` | `ops/update_weekly.sh`, CI workflows, tests | Weekly update compatibility gate | update job fails on adapter incompatibility | MED | CI script tests |
| KAI-011 | done | `M-023` | readiness endpoint + tests | Governance readiness endpoint | policy/claims/benchmarks state surfaced | LOW | API tests |
| KAI-012 | done | `M-024` + `docs/TODO.md` dashboard metrics | backend KPI API + frontend views | KPI dashboard (acceptance/duplicates/throughput/net payout) | KPI API and UI export available | MED | UI/API tests |
| KAI-013 | done | `M-025` | skill routing modules + tests | AI skill router with signed context contracts | skill invocations require signed run/program/cert context | HIGH | unit tests |
| KAI-014 | done | `M-026` | orchestration hook registry + tests | Deterministic pre/post/approval/retry/safety hooks | auditable ordered hook chain | MED | integration tests |
| KAI-015 | done | `M-027` | policy engine + llm integration + tests | Confidence policy engine (stop/escalate fallback) | low-confidence decisions auto-escalate/HIL | HIGH | policy tests |
| KAI-016 | done | `M-028` | telemetry + metrics modules + tests | Model decision observability | cost/latency/quality/confidence emitted per decision point | MED | telemetry tests |
| KAI-017 | done | `M-029` | CI checks + negative tests | Non-bypassability CI checks for scope/auth + adapter-only execution | CI fails on bypass paths | HIGH | negative tests |
| KAI-018 | done | `M-030` | `claims/claims.yaml`, KPI/benchmarks | Accepted-rate and payout-efficiency claims | thresholds tracked and fail on regressions | MED | benchmark + KPI checks |

## Supplemental TODO Sources (mapped)

| ID | Status | Source | Scope | Task | Definition of Done | Risk | Verify |
|---|---|---|---|---|---|---|---|
| KAI-019 | done | `docs/TODO.md` | docker compose + TheHive integration paths | Containerized E2E validation on docker-capable host | full compose smoke with logs | MED | docker compose smoke script |
| KAI-020 | done | `docs/TODO.md`, `K1_COMPREHENSIVE_TODO_LIST.md` | frontend dashboards + settings | Remaining frontend SOC HUD/planner wiring and E2E UI smoke | UI features wired to real APIs | LOW | frontend test/build commands |
| KAI-021 | done | inline TODO markers (`full_scan_orchestrator`, `routers/tools`, integrations) | backend modules with TODO/FIXME | Resolve high-impact inline TODOs affecting correctness/safety | remove/replace TODO with implemented behavior or explicit tracked issue | MED | targeted unit tests + grep |

## Verification Baseline
- `python3 scripts/validate_claims.py`
- `python3 scripts/run_benchmarks.py --verify-claims`
- `python3 -m py_compile <changed files>`
- `python3 -m pytest ...` (when `pytest` is available in environment)
