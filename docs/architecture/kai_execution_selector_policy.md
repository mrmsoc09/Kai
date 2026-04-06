# Kai Execution Selector Policy

## Objective

Deterministically choose the execution substrate per mission stage while preserving governance-first behavior.

## Candidate Substrates

- `LANGGRAPH_PRIMARY`
- `DEEPAGENTS_SPECIALIST`
- `PRAISON_EXTERNAL`
- `MISSIONRUNTIME_CUSTOM`

## Input Variables

| Variable | Type | Meaning |
| --- | --- | --- |
| `risk_band` | enum (`0..3`) | Safety/impact class of requested actions |
| `scope_sensitivity` | enum (`low`, `medium`, `high`) | Data/target sensitivity and tenant risk |
| `needs_resume` | bool | Requires checkpoint/resume/replay semantics |
| `workflow_complexity` | enum (`low`, `medium`, `high`) | Branching/decomposition depth |
| `requires_protocol_bridge` | bool | Needs MCP/A2A/external framework interoperability |
| `requires_specialist_decomposition` | bool | Needs subagent hierarchy or deep context engineering |
| `latency_slo_ms` | int | End-user latency budget |
| `is_stateless` | bool | No persistent thread/state needed |
| `tool_privilege_level` | enum (`read`, `write`, `intrusive`) | Tool action severity |
| `tenant_mode` | enum (`single`, `multi`) | Isolation model |
| `telemetry_required` | enum (`standard`, `strict`) | Audit/trace obligations |
| `performance_profile` | map | Benchmark-derived substrate reliability/latency profile |

## Hard Guards (Applied First)

1. If `risk_band=3` or `tool_privilege_level=intrusive`, require Kai governance approval before any substrate invocation.
2. If `tenant_mode=multi`, deny host-shell/local-filesystem execution paths.
3. If `needs_resume=true`, substrate must support checkpoint semantics through LangGraph-thread authority.
4. If `requires_protocol_bridge=true`, allow only normalized Praison bridge adapters.
5. If scope check fails, selector returns `DENY`.

## Selection Rules (Deterministic Order)

1. If `is_stateless=true` and `latency_slo_ms <= 300` and `workflow_complexity=low` and `tool_privilege_level=read`, choose `MISSIONRUNTIME_CUSTOM`.
2. Else if `requires_protocol_bridge=true`, choose `PRAISON_EXTERNAL` with LangGraph wrapper node.
3. Else if `requires_specialist_decomposition=true` and `risk_band <= 2` and approved backend profile available, choose `DEEPAGENTS_SPECIALIST`.
4. Else choose `LANGGRAPH_PRIMARY`.

Tie-breaker: prefer `LANGGRAPH_PRIMARY` when two candidates satisfy requirements.

## Performance Overrides (Deterministic)

After base selection, Kai may apply a deterministic override when a benchmark profile is provided:

1. If selected substrate `failure_rate >= 0.20` or `retry_frequency >= 0.20`, fail over to configured fallback substrate.
2. If selected substrate is `DEEPAGENTS_SPECIALIST` or `PRAISON_EXTERNAL` and `p95_latency_ms > 2 * latency_slo_ms`, fail over.
3. Every override is emitted in selector audit tags (`selector:perf_reliability_override` or `selector:perf_latency_override`) and required guards.

## Bounded Learning Guardrails

- Adaptive profiles are recommendation-only and require:
  - minimum sample threshold
  - minimum confidence threshold
  - non-stale profile age
- Weak/stale profiles are ignored and baseline deterministic policy remains authoritative.
- If an adaptive recommendation changes the selected substrate, the selector artifact must include:
  - previous selected substrate
  - new selected substrate
  - profile key
  - confidence and sample count
  - rationale

## Do-Not-Use Conditions

## Praison
- Do not use as mission transition authority.
- Do not use when endpoint auth/governance mediation is unavailable.

## DeepAgents
- Do not use in multi-tenant production with host shell/filesystem backend profiles.
- Do not use for trivial low-latency read-only requests.

## LangGraph
- Do not skip LangGraph for resumable or HITL workflows.

## MissionRuntime custom path
- Do not use for high-risk, branching, or long-running operations.

## Examples by Mission Type

| Mission type | Selector inputs | Chosen substrate | Reason |
| --- | --- | --- | --- |
| Quick passive recon lookup | low complexity, stateless, read-only, tight latency | `MISSIONRUNTIME_CUSTOM` | Lowest overhead and safe |
| Multi-stage recon/triage workflow | needs resume, branching, approvals | `LANGGRAPH_PRIMARY` | Checkpointed deterministic orchestration |
| Deep exploitability assessment | high decomposition, long context, specialist behavior | `DEEPAGENTS_SPECIALIST` | Bounded specialist capability |
| External tool ecosystem enrichment via MCP | protocol bridge needed | `PRAISON_EXTERNAL` wrapped by LangGraph | Interoperability without authority leakage |
| Report finalization | high-risk, compliance-critical | `LANGGRAPH_PRIMARY` + Kai report gate | Requires strict governance and lineage |

## Fallback Rules

1. `DEEPAGENTS_SPECIALIST` failure -> `LANGGRAPH_PRIMARY` specialist fallback node.
2. `PRAISON_EXTERNAL` failure -> internal queued/offline fallback path.
3. `MISSIONRUNTIME_CUSTOM` failure on retriable errors -> `LANGGRAPH_PRIMARY` retry lane.
4. Any telemetry outage does not change selector outcome.

## Policy Outputs

Selector must emit:
- `selected_substrate`
- `policy_justification`
- `required_guards`
- `fallback_substrate`
- `audit_tags`

No execution may start without this policy artifact attached to stage metadata.
