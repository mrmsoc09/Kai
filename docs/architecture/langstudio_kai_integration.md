# LangStudio -> Kai Integration Architecture

## Architecture Decision

Integrate LangStudio as Kai's execution and observability substrate, while keeping Kai authoritative for governance, scope enforcement, tool safety, and reporting state.

## Authority Boundaries

| Concern | Authoritative in Kai | LangStudio role |
| --- | --- | --- |
| Mission lifecycle and state truth | `MissionRuntime` + graph state modules | Execute orchestrated graph steps |
| Governance and approvals | PraisonGovernor + runtime policy | Provide interruptable primitives only |
| Scope enforcement | scope guardrails and policy checks | Never authoritative |
| Tool execution safety | Kai wrappers/adapters + catalog policy | Middleware and runtime hooks |
| Audit and reporting truth | Kai events/artifacts/report gates | Trace/export surfaces only |

## Where LangStudio SHOULD Be Used

- LangGraph for stage DAG execution, checkpoints, resume/replay, and interrupt gates.
- LangChain for model abstraction, middleware policy layers, and structured tool/model interactions.
- DeepAgents for high-complexity specialist tasks that benefit from subagents and memory tooling.
- LangSmith for trace correlation, evaluation pipelines, and deployment telemetry.

## Where LangStudio SHOULD NOT Be Used

- Final allow/deny scope decisions.
- Terminal governance approvals for high-risk operations.
- Direct unsafe tool execution bypassing Kai adapters.
- Final report readiness or submission authority.
- Cross-tenant authorization truth.

## Interaction Design in Kai

## 1) LangGraph <-> MissionRuntime
- Keep graph compilation/execution owned by Kai runtime modules.
- Require deterministic mapping: `mission_id -> phase_id -> node_id -> thread_id`.
- Treat checkpoint IDs as resumability primitives, not business identifiers.

## 2) Governance System
- Governance decision precedes any node/tool action that can mutate external state.
- Interrupts from LangGraph/DeepAgents are advisory until Kai governor approves transition.
- Resume tokens and approvals are persisted in Kai first, then replayed to runtime.

## 3) Tool Execution
- All tool calls pass through Kai tool wrappers for command safety and provenance.
- LangChain middleware may filter/retry/limit, but wrapper-level validation remains mandatory.
- DeepAgents `execute`/filesystem abilities are allowed only with approved backend policy.

## 4) Reporting
- LangStudio outputs are normalized into Kai artifact schemas before report usage.
- LangSmith traces can enrich analyst context but cannot mark findings as final.

## Boundary vs Praison

| Layer | Praison | LangStudio | Kai decision |
| --- | --- | --- | --- |
| Control authority | Strong | Weak | Keep Praison authoritative |
| Runtime orchestration | Limited | Strong (LangGraph) | Use LangStudio runtime |
| Specialist autonomy | Medium | Strong (DeepAgents) | Use DeepAgents behind policy |
| Observability/eval | Limited | Strong (LangSmith) | Use LangSmith as secondary plane |
| Workflow generation UX | Strong | Medium | Use Praison for control-plane UX, not runtime truth |

## Performance Strategy

- Enforce per-mission concurrency ceilings for model and tool calls.
- Use checkpoint-backed resume instead of long synchronous holds.
- Stream incrementally for UI responsiveness, but commit state only on validated transitions.
- Use adaptive retries in middleware; keep hard timeout caps in wrappers.
- Cache provider metadata/capability lookup with short TTLs.

## Fallback Strategy

1. If LangSmith is unavailable, continue mission execution with local Kai telemetry only.
2. If DeepAgents runtime is unavailable, degrade to LangChain+LangGraph specialist node fallback.
3. If provider call fails, follow Kai provider fallback chain and preserve failure provenance.
4. If checkpoint restore fails, pause mission and require operator recovery instead of silent restart.
5. If middleware policy conflicts with Kai governance, Kai governance wins.

## Implementation Placement

- Runtime orchestration stays in `apps/backend/src/core/praison_*` runtime modules.
- Model/middleware/tool bridge stays in `apps/backend/src/core/langchain_*` modules.
- Specialist bridge stays in `apps/backend/src/core/praison_deepagents_*` modules.
- Observability bridge stays in `apps/backend/src/core/langsmith_*` modules.
- Scope and policy gates stay in `apps/backend/src/core/scope_guardrails.py` and governor/runtime policy modules.

## Cross-Links

- Capability map: [langstudio_capability_map.md](/home/k1-admin/Kai/docs/research/langstudio_capability_map.md)
- Orchestration matrix: [langstudio_orchestration_matrix.md](/home/k1-admin/Kai/docs/research/langstudio_orchestration_matrix.md)
- Observability design: [langstudio_observability_design.md](/home/k1-admin/Kai/docs/research/langstudio_observability_design.md)
- Roadmap: [langstudio_implementation_roadmap.md](/home/k1-admin/Kai/docs/architecture/langstudio_implementation_roadmap.md)
