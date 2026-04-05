# Kai Unified Agentic Architecture

## Purpose

Define one implementation-grade architecture that fuses Praison and LangStudio research into Kai's governance-first runtime model.

## Pre-Synthesis Findings (Required Extraction)

## 1) Overlapping capabilities
- Praison and LangGraph both can orchestrate multi-step flows.
- Praison and LangSmith both expose async/status/stream control surfaces.
- Praison and DeepAgents both support multi-agent delegation patterns.
- LangChain and Praison both can provide tool/middleware-level control hooks.
- Praison and LangStudio both expose protocol interoperability paths (MCP, A2A-like boundaries).

## 2) Conflicting recommendations
- Praison workflows can become orchestration-authoritative if not constrained; LangGraph guidance favors graph/checkpoint authority.
- Praison approval callbacks can conflict with Kai terminal governance decisions.
- DeepAgents local shell/filesystem modes are useful for dev but conflict with Kai multi-tenant safety defaults.
- LangSmith deployment/control-plane features can be misread as runtime authority; Kai requires observability to remain non-authoritative.

## 3) Complementary strengths
- Praison: interoperability and async externalization.
- LangGraph: deterministic stateful execution and resumability.
- LangChain: model/tool abstraction and middleware policy insertion.
- DeepAgents: specialist deep-work autonomy with bounded decomposition.
- LangSmith: tracing/evaluation/deployment telemetry.
- Kai: governance, scope, audit, reporting authority.

## 4) Hard constraints
- Kai governance and scope guardrails are non-bypassable.
- Mission truth must be checkpoint-backed and resumable.
- Tool execution must flow through Kai wrappers/adapters with provenance.
- Audit trail in Kai must remain authoritative under telemetry outages.
- Multi-tenant execution cannot permit host-shell or unconstrained shared memory.

## 5) Unresolved design choices resolved here
- Primary orchestration owner: LangGraph under MissionRuntime.
- Role of Praison: bounded external capability layer only.
- Specialist runtime owner: DeepAgents under contract and policy.
- Telemetry authority: Kai primary, LangSmith secondary.
- Selector policy owner: MissionRuntime policy engine with deterministic rules.

## Final Authority Boundaries

| Layer | Primary owner | Secondary/assistive | Must never own |
| --- | --- | --- | --- |
| Mission lifecycle and state truth | Kai MissionRuntime + LangGraph state/checkpoint layer | Praison async adapters, DeepAgents nodes | External runtimes deciding mission terminal state |
| Orchestration transitions | LangGraph graph specs compiled by Kai | Praison provides data/jobs only | Praison as transition authority |
| Specialist deep work | DeepAgents (bounded) | LangChain-only specialist fallback | Unbounded autonomous loops with no Kai limits |
| Model/tool mediation | LangChain + Kai wrappers | Provider SDKs, Praison MCP bridge | Direct router-to-provider or router-to-shell bypass |
| Governance | Kai governor + runtime policy + scope guardrails | Praison approval UX as advisory | External approval as terminal decision |
| Audit | Kai EventBus + artifacts | LangSmith export | LangSmith becoming compliance source of truth |
| Reporting | Kai report pipeline + evidence gates | External draft assist (Praison/LLM) | External frameworks marking report final status |

## What Each System Should Own

- Kai MissionRuntime/custom runtime:
  - Mission lifecycle, phase state machine, execution substrate selection, pause/resume/abort, final state transitions.
- LangGraph:
  - Typed state transitions, checkpointing, interrupts, replayable execution path.
- LangChain:
  - Node-local reasoning, model abstraction, middleware policy (retry/fallback/limits/PII/moderation), runtime context injection.
- DeepAgents:
  - Bounded specialist tasks requiring decomposition/subagents/context-engineering patterns.
- Praison:
  - Async offload surfaces, protocol federation bridges, framework translation boundaries.
- LangSmith:
  - Trace/eval/deployment telemetry surfaces and experiment loops.

## What Each System Must Never Own

- Praison:
  - Mission graph truth, governance terminal decisions, scope enforcement, report finalization.
- LangGraph:
  - Governance policy authority, cross-tenant auth decisions.
- DeepAgents:
  - Unrestricted host execution in production, mission state authority.
- LangSmith:
  - Audit authority, policy decisions, report status transitions.
- Providers:
  - Any application-level safety invariant or compliance rule.

## Orchestration Ownership Model

1. MissionRuntime receives mission intent and computes execution substrate per node/stage.
2. LangGraph remains default orchestrator for stateful and resumable flows.
3. DeepAgents is invoked as a node strategy for high-complexity specialist work.
4. Praison paths are invoked as external jobs or protocol bridges, returning normalized results only.
5. State transitions commit only through Kai-controlled merge semantics.

## Runtime Selection Strategy (Top-level)

- Default: LangGraph.
- Escalate to DeepAgents when complexity/decomposition threshold and value justify it.
- Use Praison only for async externalization/protocol interop/no-code bridge paths.
- Use custom lightweight runtime only for strict stateless low-latency requests.

## Fallback and Degradation Model

- If DeepAgents fails/unavailable: fallback to constrained LangChain specialist node.
- If Praison endpoint fails: fallback to local deterministic or queued internal path.
- If LangSmith fails: continue execution with Kai-only telemetry.
- If provider fails: use policy-defined fallback chain with preserved provenance.
- If checkpoint resume fails: hold mission and require operator intervention; no silent reset.

## Governance Alignment

- Pre-dispatch policy checks are mandatory for all substrate calls.
- Approval-required actions remain blocked until Kai governor decision.
- External approval/callbacks are advisory signals, not final authorization.
- Reimported external outputs re-pass scope/policy validation before merge.

## Audit and Observability Layering

- Kai EventBus + artifacts = canonical audit source.
- LangSmith = asynchronous mirror for trace/eval/diagnostic acceleration.
- Export path is redaction-gated and correlation-id complete.
- Telemetry loss cannot alter execution correctness.

## Reporting and Data-Flow Boundaries

- External systems may generate candidate narrative or analysis artifacts.
- Only Kai evidence verification and report gate logic can mark findings as report-ready/final.
- Report lineage, provenance hashes, and approval decisions remain inside Kai persistence.

## Performance vs Safety Tradeoffs

- LangGraph-first increases determinism and recovery reliability; slight control-plane overhead is accepted.
- DeepAgents yields higher capability on complex tasks; bounded by stricter budgets/contracts to cap risk.
- Praison async offload improves throughput; eventual consistency handled via explicit reconciliation.
- LangSmith improves debug velocity; strict redaction and sampling required to keep security posture.

## Architectural Directive

Kai is the authority layer. LangGraph is the execution backbone. LangChain is the intelligence/middleware layer. DeepAgents is a bounded specialist executor. Praison is a bounded interoperability/offload layer. LangSmith is a secondary telemetry plane.
