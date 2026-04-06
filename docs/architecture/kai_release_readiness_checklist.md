# Kai Release Readiness Checklist (Governed Execution)

This checklist is the release authority for Kai's governed selector, benchmark, and adaptive-control planes.

## Required Runtime Guarantees

- Deterministic selector output for identical inputs.
- Audit artifacts capture requested substrate, actual substrate, and fallback rationale.
- Adaptive selector decisions are explainable (considered/accepted/rejected + guardrails + additional data needed).
- Kai audit remains authoritative when external telemetry is degraded or unavailable.

## Benchmarking and Retention

- `artifacts/benchmarks/latest.json` remains the current bounded working set.
- Historical benchmark records are archived to `artifacts/benchmarks/history/*.jsonl`.
- History retention is bounded by file count (default: 30 files) to prevent unbounded disk growth.
- Operator queries must use bounded result limits and optional filters.

## Operator Access Policy

- Benchmark retrieval (`/governance/benchmark-intelligence`) is available to viewer/operator/analyst/admin roles.
- Parallel probe execution from the same endpoint requires operator or admin role.
- Probe denial must return explicit policy error (`benchmark_probe_forbidden_requires_operator_or_admin`).

## DeepAgents Structural Contract

- If DeepAgents backend profile is absent, runtime MUST emit explicit divergence metadata:
  - `reason=deepagents_backend_unavailable`
  - `contract_status=deferred_structural_capability`
  - `capability_owner=kai_runtime`
  - `fallback_contract=explicit_irreversible_for_stage`
- This is an intentional deferred capability, not an implicit runtime failure.

## Release Sign-Off Tests

- `tests/test_selector_learning.py`
- `tests/test_kai_selector_and_contracts.py`
- `tests/test_execution_benchmarking.py`
- `tests/test_langgraph_mission_runtime.py`
- `tests/test_governance_readiness.py`

Release is blocked if any of the above suites fail or if selector/audit artifacts regress.
