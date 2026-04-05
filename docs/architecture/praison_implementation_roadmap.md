# Praison Integration Implementation Roadmap

## Objective
Ship Praison integration where it increases Kai throughput and interoperability, without weakening governance, scope safety, or reporting integrity.

## Prioritization Logic
Prioritize features that:
- reduce operator wait time
- improve protocol interoperability
- preserve Kai authority boundaries
- require minimal schema churn in current workflow artifacts

## Phase Plan

### Phase 0: Guarded Foundation (Highest ROI)
Target outcome:
- Safe integration scaffolding with no authority leakage.

Deliverables:
1. External execution adapter contract (`submit/status/result/cancel`) with idempotency support.
2. Policy-boundary middleware requiring Kai governance + scope checks pre-dispatch.
3. Normalized external result envelope mapping into existing `ToolExecution` and artifact schemas.

Why first:
- Enables later capabilities without rework.
- Prevents unsafe direct-call patterns.

### Phase 1: Async Job Offload
Target outcome:
- Non-blocking long-running task path for enrichment-heavy stages.

Deliverables:
1. Mission node type for external async jobs.
2. SSE + polling dual-mode progress tracking.
3. Reconciliation worker that updates mission stage state deterministically.

Why second:
- Immediate cycle-time gain on high-latency workloads.

### Phase 2: MCP Federation
Target outcome:
- Controlled access to external tool ecosystems with strong policy mediation.

Deliverables:
1. MCP connector with auth scopes and cursor-safe pagination handling.
2. Schema normalization into Kai tool model.
3. Deny-by-default tool exposure policy and per-tool approval overlays.

Why third:
- High leverage for tool breadth with bounded risk if mediator is strict.

### Phase 3: Persona Compiler and Framework Bridge
Target outcome:
- Canonical persona portability across Kai/Praison/CrewAI.

Deliverables:
1. Canonical persona schema compiler.
2. Target adapters for Praison and CrewAI (`roles` format) with compatibility diagnostics.
3. CI check to block policy-loss transforms.

Why fourth:
- Prevents config drift and duplicated persona logic.

### Phase 4: Retrieval/Memory Augmentation (Selective)
Target outcome:
- Better analyst assist quality without contaminating mission truth.

Deliverables:
1. Quality-thresholded retrieval helper service.
2. Optional graph memory sandbox for relationship-heavy analysis.
3. Evidence confidence scoring before merge into report candidate paths.

Why fifth:
- Valuable but riskier due quality variance and token cost.

## Highest-ROI Backlog (Ordered)
1. External async adapter + idempotent submit/retry contract.
2. Governance/scope boundary middleware for all external calls.
3. Async progress reconciliation in `WorkflowExecutor`/Mission runtime path.
4. MCP bridge with strict schema normalization.
5. Canonical persona compiler and compatibility linter.
6. Retrieval quality gate for analyst-assist only.

## Medium-Term Improvements
- Multi-provider routing policy for external execution backends.
- Per-tenant concurrency shaping and adaptive queue budgeting.
- Protocol bridge observability dashboard (latency, failure taxonomy, approval rates).
- Partial replay support for externalized job histories.

## Deferred Items
- Full replacement of internal orchestration with external framework runtimes.
- External systems as primary report state authority.
- Automatic full-auto autonomy in production without mission-level hard stops.

## Structural Blockers
- Need a stable external job state model mapped to Kai stage states.
- Need canonical persona schema ownership and compile-time enforcement.
- Need external auth/key management policy for protocol endpoints.
- Need deterministic parser/error taxonomy for third-party payload drift.

## Validation Strategy

### Functional Validation
- Unit tests for adapter request/response mapping, retries, and idempotency.
- Integration tests for submit->status->result->cancel lifecycle.
- Contract tests for schema normalization into `ToolExecution` and stage artifacts.

### Safety Validation
- Mandatory pre-dispatch checks: scope and governance.
- Negative tests for out-of-scope target rejection and denied tool classes.
- Auth failure and token-expiry test paths for MCP/protocol adapters.

### Reliability Validation
- Timeout, retry, and fallback behavior tests under partial outage.
- SSE interruption tests with polling recovery.
- Duplicate submission tests across idempotency scopes.

### Reporting Integrity Validation
- Ensure externally generated content cannot set final report status.
- Validate provenance metadata and immutable lineage hashing.

## Exit Criteria per Phase
- Phase 0: No external call can bypass Kai governance/scope checks.
- Phase 1: At least one production workflow uses async offload with deterministic recovery.
- Phase 2: MCP tools available through normalized, policy-enforced wrappers only.
- Phase 3: Persona compiler blocks unsupported policy-losing translations.
- Phase 4: Retrieval augmentation improves analyst metrics without increasing false-positive report submissions.

## Cross-Links
- Capability map: [praison_capability_map.md](/home/k1-admin/Kai/docs/research/praison_capability_map.md)
- Integration architecture: [praison_kai_integration.md](/home/k1-admin/Kai/docs/architecture/praison_kai_integration.md)
- Workflow matrix: [praison_workflow_matrix.md](/home/k1-admin/Kai/docs/research/praison_workflow_matrix.md)
- Persona mapping: [praison_persona_mapping.md](/home/k1-admin/Kai/docs/integrations/praison_persona_mapping.md)
