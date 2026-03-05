# Kai Gap Closure Plan

This document is the execution-ready backlog for closing architecture, safety,
workflow, and commercialization gaps required for Kai to support claims.

## Phase 0: Foundations and Safety Hardening
- Restore canonical `ops/toolpacks.yaml` and validate startup policy loading.
- Implement persistent authorization certificate + decision ledger.
- Enforce canonical Evidence Object schema parity across all producers/consumers.
- Add claims registry and deterministic benchmark harness.

Exit criteria:
- Startup gates pass in CI (`toolpacks`, `secrets`, `dependencies`).
- Claims validation and benchmark verification are green.

## Phase 1: Core Execution Integrity
- Complete adapter contract tests for critical tools.
- Enforce OPSEC policy engine (rate/concurrency/budget by method).
- Add hash revalidation during report assembly.

Exit criteria:
- All critical adapters pass fixtures and normalization tests.
- No unauthorized tool execution path exists without gate checks.

## Phase 2: Evidence + Intelligence Maturity
- Build opportunity score v1: payout expectancy, duplicate risk, effort.
- Add pre-submit duplicate risk gate.
- Add report quality gates with evidence-to-claim traceability.

Exit criteria:
- Duplicate/reject trend improving over 4-week baseline.

## Phase 3: Workflow Completion
- Submission state machine with SLA timers.
- Unified comms inbox linked to findings/reports.
- Payout ledger (`expected`, `actual`, `fees`, `net`) and monthly reconciliation.

Exit criteria:
- 95%+ submissions tracked end-to-end.
- 100% accepted findings link to payout records.

## Phase 4: Optimization and Scale
- Hybrid retriever (vector + graph provenance ranking).
- Bounded reflective learning loop tied to reject/duplicate outcomes.
- KPI dashboards for acceptance, throughput, cost, net payout.

Exit criteria:
- Claims pass consistently in CI over 4 consecutive releases.

## Priority IDs
Use IDs `T-001`..`T-024` from the master gap register for sprint planning.
