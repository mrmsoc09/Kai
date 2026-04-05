# Kai Fused Implementation Plan

## Goal

Implement the unified architecture with highest ROI first, while maintaining governance-first safety.

## Phase 0: Policy And Contract Foundation (Immediate)

Deliver:
1. Execution selector engine integrated into MissionRuntime.
2. Canonical persona compiler + immutable agent contract issuance.
3. Mandatory policy artifact emitted per stage (`selected_substrate`, guards, fallback).

Dependencies:
- Existing governor, scope, and mission state modules.

Why now:
- All later work depends on deterministic substrate and contract control.

## Phase 1: Runtime Boundary Hardening (Highest ROI)

Deliver:
1. LangGraph-first stage orchestration enforcement with checkpoint/thread invariants.
2. Wrapper-only tool execution enforcement for all substrates.
3. Praison external adapter boundary (`submit/status/result/cancel`) with idempotency.
4. DeepAgents backend policy profiles (prod-safe defaults).

Dependencies:
- Phase 0 selector + contract artifacts.

Why now:
- Removes unsafe bypass paths and establishes deterministic fallback behavior.

## Phase 2: Observability/Governance Fusion

Deliver:
1. Kai->LangSmith correlation bridge completion with strict redaction.
2. Telemetry degradation logic and priority shedding.
3. Governance/audit reconciliation dashboard (internal).

Dependencies:
- Stable runtime identifiers and contract IDs from Phase 1.

Why now:
- Enables production diagnostics without sacrificing audit authority.

## Phase 3: Specialist And Interop Expansion

Deliver:
1. DeepAgents specialist templates with bounded budgets and contract presets.
2. Praison MCP/A2A bridge normalization into Kai tool schema.
3. Translation diagnostics for CrewAI and other external orchestrators.

Dependencies:
- Contract and policy-manifest enforcement.

Why now:
- Adds capability breadth after safety boundaries are proven.

## Phase 4: Optimization And Evaluation Loops

Deliver:
1. Provider capability registry + pinned compatibility matrix.
2. Online/offline evaluation loops tied to release gates.
3. Adaptive concurrency/cost controls per mission class.

Dependencies:
- Correlated telemetry and stable stage outputs.

Why now:
- Converts architecture into sustained performance and quality gains.

## Safe-Now vs Later

Safe now:
- Selector policy artifacts.
- Contract enforcement.
- LangGraph checkpoint hardening.
- Redaction-first telemetry export.

Later (after guardrails prove stable):
- Broader Praison no-code ingestion.
- Preview DeepAgents async-subagent features.
- Additional framework bridge targets.

## Blockers

- Missing unified contract schema implementation in runtime path.
- Incomplete tenant metadata propagation across all node/tool events.
- No hard fail on policy-loss translation in some adapter paths.
- Limited regression harness for redaction and fallback behavior.

## Validation And Benchmark Plan

## Validation
1. Determinism: repeated runs with same state/checkpoint produce same transition path.
2. Safety: out-of-scope and high-risk actions fail closed across all substrates.
3. Contract integrity: unauthorized tool/delegation attempts are blocked and audited.
4. Observability: redaction and correlation tests pass under outage and backpressure.
5. Reporting integrity: external outputs cannot set final report state.

## Benchmarks
- Mission completion latency by substrate choice.
- Tool execution success/failure and retry amplification rates.
- Checkpoint resume success rate and mean recovery time.
- DeepAgents specialist uplift vs LangGraph-only baseline (quality and cost).
- Telemetry overhead impact on p95 runtime latency.

## Exit Criteria

- Selector policy is authoritative and attached to every stage execution.
- No direct execution bypass around wrappers/governance.
- Kai audit trail fully reconstructs missions without LangSmith dependency.
- Multi-tenant production runs disallow unsafe backend profiles by policy.
- Fallback paths are tested and deterministic.
