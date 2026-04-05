# Praison -> Kai Integration Architecture

## Decision
Integrate Praison as a bounded capability layer, not as Kai's control authority.

Authoritative control remains in Kai:
- mission state and lifecycle: `MissionRuntime`
- governance and approval decisions: PraisonGovernor + Kai safety stack
- scope policy enforcement: scope guardrails
- tool dispatch truth: Kai tool registry/adapters
- report readiness and finalization gates

## Where Praison SHOULD Be Used
- Async execution surfaces for long-running non-blocking operations.
- Protocol interoperability boundaries (MCP, A2A/AG-UI exposure when required).
- Optional retrieval/memory augmentation for analyst-assist workflows.
- External framework bridge mode (CrewAI/AG2 interop) behind canonical schema translation.
- Non-authoritative operator UX surfaces (SSE/UI helper channels).

## Where Praison SHOULD NOT Be Used
- Final scope allow/deny decisions.
- Mission graph truth and checkpoint authority.
- Direct unsafe tool execution bypassing Kai wrappers.
- Final report state transitions (ready/approved/submitted).
- Tenant isolation and compliance-critical audit source of truth.

## Authority Boundary Matrix
| Concern | Kai Authority | Praison Role |
| --- | --- | --- |
| Mission graph and state | `praison_mission_runtime.py`, `praison_langgraph_builder.py` | Optional helper execution clients |
| Governance policy | `praison_governor.py`, runtime policy stack | Supplemental approval UX and policy hints |
| Scope enforcement | `scope_guardrails.py` + related gates | Never authoritative |
| Tool execution | `tool_registry_catalog.py`, `tool_adapters_bugbounty.py`, worker path | Optional upstream/downstream tool protocol bridge |
| Workflow orchestration | `bugbounty_workflow_engine.py`, `workflow_executor.py` | Async offload and recipe integration only |
| Reporting | Kai report generation/finalization APIs | Can provide content assist, never final gate |

## Interaction Design

### 1) LangGraph Interaction
- Keep LangGraph topology and transitions fully owned by Kai.
- Add a dedicated "external async task" node type that wraps Praison async jobs.
- Store only normalized outcomes in `K1GraphState` and workflow artifacts.

Design rule:
- A Praison call returns data, not control-flow authority.

### 2) MissionRuntime Interaction
- `MissionRuntime` remains the lifecycle orchestrator.
- Praison async jobs map to mission node execution records with:
  - request payload hash
  - idempotency key
  - external job id
  - status mirror and deadline

Design rule:
- Mission pause/resume/abort must work even if Praison endpoint is unavailable.

### 3) Governance System Interaction
- Governance checks run before any Praison-bound task leaves Kai.
- Approval-required operations remain Kai decisions even if Praison also supports approval.
- Re-imported Praison results must be policy-checked before state merge.

Design rule:
- Dual approval systems are allowed only if Kai approval is the terminal decision.

### 4) Tool Execution Interaction
- All execution requests continue through Kai wrappers/adapters.
- Praison MCP/tool access is treated as an external tool source, then normalized into Kai `ToolExecution` schema.
- No direct router -> Praison-tool execution path from API layer.

Design rule:
- Preserve deterministic command construction and provenance semantics in Kai wrappers.

### 5) Reporting Interaction
- Praison can assist with draft synthesis, summarization, and formatting.
- Kai keeps final evidence validation, report gate checks, and immutable report lineage.

Design rule:
- Report content can be generated externally; report status cannot.

## Recommended Integration Patterns

### Pattern A: In-Process SDK Adapter
Use for low-latency, low-blast-radius helper operations.

Pros:
- lowest overhead
- simpler observability correlation

Cons:
- shared process resources
- tighter dependency coupling

### Pattern B: Local Sidecar / HTTP Runner
Use for polyglot integration and process isolation.

Pros:
- language/runtime separation
- easier rollout control

Cons:
- network boundary overhead
- health and retry management required

### Pattern C: Event-Driven Async Jobs
Use for long-running enrichment tasks.

Pros:
- non-blocking
- natural retry/idempotency semantics

Cons:
- eventual consistency handling required
- extra reconciliation logic

Default recommendation for Kai:
- Pattern C for heavy jobs
- Pattern B for protocol bridges (MCP/A2A)
- Pattern A only for small deterministic helper calls

## Fallback Strategies
1. If Praison endpoint is unavailable, degrade node to deterministic local fallback toolchain.
2. If async job stream fails, switch from SSE to poll mode using returned retry hints.
3. If external protocol auth fails, hard-fail node and preserve mission recoverability.
4. If external result schema drifts, quarantine payload and emit parser-failure artifact.
5. If framework bridge is incompatible (roles/steps mismatch), route to canonical Kai persona translator or reject.

## Performance Considerations
- Bound external concurrency per mission and per tenant.
- Use idempotency keys for submit/retry safety.
- Prefer polling with adaptive interval when SSE fan-out cost is high.
- Cache stable metadata (tool lists, protocol descriptors) with short TTL.
- Separate latency SLOs:
  - control-path nodes (strict)
  - enrichment-path nodes (relaxed)

## Implementation Constraints for Kai
- Never bypass `tool_adapters_bugbounty` and registered tool execution path.
- Never bypass `scope_guardrails` checks pre-dispatch.
- Persist normalized results only (`WorkflowRun`, `StageRun`, `ToolExecution`, and related schemas).
- Keep all external call provenance in artifact metadata.

## Cross-Links
- Capability map: [praison_capability_map.md](/home/k1-admin/Kai/docs/research/praison_capability_map.md)
- Workflow matrix: [praison_workflow_matrix.md](/home/k1-admin/Kai/docs/research/praison_workflow_matrix.md)
- Persona mapping: [praison_persona_mapping.md](/home/k1-admin/Kai/docs/integrations/praison_persona_mapping.md)
- Roadmap: [praison_implementation_roadmap.md](/home/k1-admin/Kai/docs/architecture/praison_implementation_roadmap.md)
