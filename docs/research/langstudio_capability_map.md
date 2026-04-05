# LangStudio Capability Map

Scope: LangChain, LangGraph, LangSmith, DeepAgents, and provider integrations.
Research basis: controlled-batch review of LangStudio docs index (April 5, 2026).

## Stack-Level Map

| Subsystem | What it is best at | Real behavior in practice | Constraints and limits | Kai fit |
| --- | --- | --- | --- | --- |
| LangChain | Fast agent assembly, model/tool abstraction, middleware | `create_agent` gives a productive default loop with standard model/tool interfaces and runtime context injection | Advanced control still depends on LangGraph; human-in-the-loop requires checkpointing; middleware policy must be configured explicitly | Best for node-local reasoning, tool selection, and policy middleware in Kai nodes |
| LangGraph | Stateful orchestration runtime | Explicit state graph + checkpointing + interrupts + resumability with thread-scoped execution | Graph must be compiled; persistent behavior requires checkpointer + `thread_id`; weak namespace design causes state bleed | Primary runtime for mission orchestration and resumable phase execution |
| LangSmith | Tracing, evaluation, deployment control plane | Strong run/thread/checkpoint observability with offline/online eval loops and deployment APIs | Not authoritative for Kai governance; deployment features are plan/infrastructure dependent; legacy observability Helm path is deprecated | Secondary telemetry/eval plane and optional deployment substrate |
| DeepAgents | High-autonomy specialist work with subagents and filesystem/sandbox patterns | Built on LangGraph; supports memory, subagent streaming, HITL, and backend routing for storage/execution | Async subagents are preview; insecure backends (local shell/filesystem) are unsafe in multi-tenant prod; requires strict namespace/auth discipline | Specialist deep-work runtime behind Kai governance gates |
| Providers | Broad model/tool ecosystem access | Separate provider packages, frequent package evolution, mixed parity between Python and JS | Version churn, deprecations, and credential differences; provider-specific semantics leak through | Use via Kai provider abstraction, not directly in business logic |

## Subsystem Reality Notes

## LangChain
- Strengths: reusable middleware (fallbacks, retries, limits, PII handling, moderation), runtime context injection, quick agent construction.
- Constraint: agent quality and safety are mostly policy/middleware outcomes, not defaults.
- Edge case: if model profile/token limits are not configured, summarization and token-triggered behavior can drift.
- Composability: pairs well with LangGraph state machines; weak as standalone mission runtime for Kai.

## LangGraph
- Strengths: durable execution, resumability, interrupts for HITL, subgraph orchestration, explicit state transitions.
- Constraint: durable semantics require both a checkpointer and stable `thread_id` usage.
- Edge case: reusing incorrect `thread_id` values can resume the wrong conversation/workflow state.
- Composability: ideal backbone for Kai stage graphs and replayable mission execution.

## LangSmith
- Strengths: unified observability/evaluation/deployment surfaces, online and offline evaluation loops, Agent Server APIs for runs/threads/checkpoints.
- Constraint: it should observe and host, not decide Kai policy or scope outcomes.
- Edge case: if stream settings are wrong (`stream_subgraphs` false), deep subagent detail is missing from telemetry.
- Composability: strong with LangGraph runtime metadata and Kai event correlation.

## DeepAgents
- Strengths: structured deep work, subagent decomposition, memory files, sandbox-enabled execution patterns, production guidance for tenancy/auth.
- Constraint: backend selection is security-critical; local shell and direct filesystem modes are high-risk outside controlled environments.
- Edge case: shared memory namespaces can become prompt-injection vectors across users/assistants.
- Composability: use as bounded specialist worker under Kai contracts and governance.

## Providers
- Strengths: large ecosystem breadth and rapid access to model capabilities.
- Constraint: package fragmentation and deprecations are normal; portability is not automatic.
- Edge case: cloud/provider-specific auth and feature mismatches cause environment-dependent behavior.
- Composability: treat provider SDKs as replaceable adapters under Kai policy and telemetry wrappers.

## Cross-Subsystem Constraints That Matter For Kai

1. Durable control requires LangGraph checkpoint + `thread_id` hygiene.
2. Any HITL pattern requires interruption state persistence.
3. Multi-tenant memory requires explicit namespace factories and auth-aware filtering.
4. Deep execution must default to sandboxed or virtualized backends, not host shell/filesystem.
5. LangSmith should be treated as a non-authoritative observability/eval plane.
6. Provider integrations must be pinned and tested per environment due frequent API/package churn.

## Practical Composability Patterns

- LangChain (reasoning/middleware) + LangGraph (state/runtime) as default Kai execution composition.
- DeepAgents invoked only for bounded specialist tasks with contract, budget, and safety controls.
- LangSmith run correlation attached at mission/phase/node/tool boundaries for audit + eval loops.
- Providers selected through Kai abstraction with deterministic fallback order and capability flags.

## Capability Boundaries (Do Not Blur)

- LangGraph owns execution state progression, not governance policy.
- LangSmith owns observability and evaluation surfaces, not authorization decisions.
- DeepAgents owns specialist execution behaviors, not mission authority.
- Providers own model APIs, not application-level safety invariants.

## Kai Decision Summary

- Build Kai around LangGraph-first orchestration.
- Use LangChain as middleware/model adapter layer, not mission authority.
- Use DeepAgents as opt-in specialist runtime where autonomy pays off.
- Use LangSmith for telemetry/evaluation/deployment support with strict data redaction and correlation.
- Keep provider dependencies isolated behind Kai interfaces and fallback policies.
