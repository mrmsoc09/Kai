# LangStudio Implementation Roadmap

Priority order optimized for Kai risk reduction and delivery ROI.

## Phase 1 (Highest ROI, Immediate)

1. Harden LangGraph execution contracts in Kai.
2. Enforce `thread_id`/checkpoint discipline across all resumable nodes.
3. Standardize LangChain middleware baseline: retries, fallbacks, call limits, PII/moderation hooks.
4. Finalize LangSmith strict-redaction trace bridge for mission/phase/node coverage.

Expected outcome: safer runtime behavior, stronger replayability, immediate debug visibility.

## Phase 2 (Near-Term)

1. Introduce bounded DeepAgents specialist nodes for high-complexity tasks only.
2. Require backend policy profiles: sandboxed/store-backed allowed, host shell/filesystem denied by default.
3. Add tenant-safe memory namespace factories for user/assistant/global scope tiers.
4. Add evaluator pipeline for regression checks on triage/report outputs.

Expected outcome: higher-quality specialist automation without compromising safety boundaries.

## Phase 3 (Medium-Term)

1. Build orchestration selector policy (LangGraph vs DeepAgents vs Praison vs custom path).
2. Integrate provider capability registry with pinned versions and fallback chains.
3. Add performance profiles per mission class (latency, cost, token budget, concurrency).
4. Add checkpoint-aware rollback playbooks for incident recovery.

Expected outcome: predictable runtime selection and better cost/performance control.

## Deferred / Optional

1. Expand Praison no-code generation as control-plane UX, compiled into Kai-safe runtime plans.
2. Adopt preview DeepAgents async-subagent features only after GA stability.
3. Broaden cross-framework deployment paths only where operationally justified.

## Structural Blockers

- Incomplete tenant metadata propagation across some execution paths.
- Potential mismatch between middleware policy outcomes and wrapper-level enforcement if not centrally normalized.
- Provider package churn can break reproducibility without lock/version governance.
- Limited automated redaction regression tests for new artifact types.

## Validation Strategy

1. Determinism tests: same input + same checkpoint state => same transition path.
2. Safety tests: out-of-scope, high-risk, and blocked-tool scenarios fail closed.
3. Observability tests: trace correlation completeness and redaction guarantees.
4. Performance tests: mission latency/cost budgets and concurrency saturation behavior.
5. Recovery tests: kill/resume/replay across phases with no data loss.

## What To Avoid

- Granting LangStudio components authority over Kai governance outcomes.
- Allowing DeepAgents host-shell execution in multi-tenant or production paths.
- Treating LangSmith availability as a hard dependency for runtime progress.
- Shipping provider updates without compatibility and fallback verification.

## Cross-Links

- Capability map: [langstudio_capability_map.md](/home/k1-admin/Kai/docs/research/langstudio_capability_map.md)
- Integration architecture: [langstudio_kai_integration.md](/home/k1-admin/Kai/docs/architecture/langstudio_kai_integration.md)
- Orchestration matrix: [langstudio_orchestration_matrix.md](/home/k1-admin/Kai/docs/research/langstudio_orchestration_matrix.md)
- Observability design: [langstudio_observability_design.md](/home/k1-admin/Kai/docs/research/langstudio_observability_design.md)
