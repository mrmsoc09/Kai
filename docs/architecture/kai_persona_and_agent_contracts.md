# Kai Persona And Agent Contracts

## Objective

Define one canonical persona and agent contract model that compiles safely to Kai, Praison, CrewAI, and LangStudio-compatible flows.

## Canonical Persona Schema (Authoritative)

```yaml
persona_id: string
name: string
class: governor | director | coordinator | specialist
objective: string
instructions: string
capabilities:
  tools_allowed: [string]
  tools_denied: [string]
  protocols_allowed: [mcp | a2a | ag_ui]
policy:
  risk_profile: governance | orchestration | recon | analysis | reporting
  approval_policy: always | on_request | never
  autonomy_mode: suggest | auto_edit | full_auto
  max_iterations: int
  max_execution_time_sec: int
  max_rpm: int
  retries: int
memory:
  scope: session | phase | workflow | mission | persistent
  persistence: bool
  quality_threshold: float
delegation:
  allowed: bool
  delegation_scope: none | phase | global
handoff:
  accepts_from: [string]
  can_handoff_to: [string]
observability:
  trace_tags: [string]
  emit_metrics: bool
compatibility:
  framework_targets: [kai | praison | crewai | langstudio]
```

## Agent Contract Boundaries

Every runtime agent invocation must carry an immutable contract:

- `contract_id`
- `persona_id`
- `allowed_tools`
- `denied_tools`
- `risk_band`
- `memory_scope`
- `delegation_scope`
- `approval_requirements`
- `time/token/budget limits`
- `fallback_policy`

Contract state machine:
- `PENDING -> ACTIVE -> COMPLETED | REVOKED | VIOLATED | EXPIRED`

## Ownership Rules

- Kai owns contract issuance, validation, and enforcement.
- Praison/DeepAgents execute within contract constraints; they do not mutate contract authority.
- CrewAI and external frameworks consume translated contracts only.

## Mapping Across Systems

| Canonical field | Kai | Praison | CrewAI | LangStudio-compatible |
| --- | --- | --- | --- | --- |
| `persona_id` | registry key | agent id/name | role key | assistant/graph metadata |
| `class` | `agent_class` | role intent | role semantics | runtime tags |
| `approval_policy` | governor/HITL rules | approval callback mode | wrapper-enforced only | interrupt + policy wrapper |
| `autonomy_mode` | runtime policy | native modes | external wrapper required | middleware + interrupt rules |
| `memory.scope` | scoped store/checkpoint | memory/session settings | limited native support | namespace factory + store |
| `delegation_scope` | contract authority checks | handoff/delegation config | task graph conventions | subgraph/subagent boundaries |
| `tools_allowed/denied` | wrapper enforcement | tool allowlists | role tool config | middleware + wrapper gate |

## Policy Preservation Requirements

1. Policy-losing transforms are `BLOCK` for production.
2. If target lacks denylist enforcement, Kai wrapper must enforce denylist at runtime.
3. If target lacks approval semantics, Kai approval gate remains mandatory pre-dispatch.
4. If target lacks memory scope isolation, compile fails for multi-tenant missions.
5. Every compilation emits a `policy_manifest` of effective controls.

## Translation-Loss Warnings (Must Emit)

- `LOSS_APPROVAL_SEMANTICS`
- `LOSS_DELEGATION_SCOPE`
- `LOSS_MEMORY_ISOLATION`
- `LOSS_TOOL_DENYLIST`
- `LOSS_AUDIT_ATTRIBUTION`

Any `LOSS_*` in `critical` category blocks deployment.

## Class-Specific Minimums

| Persona class | Required controls |
| --- | --- |
| `governor` | no intrusive tools, always approval, full audit |
| `director` | bounded delegation, no direct intrusive execution |
| `coordinator` | routing/handoff authority only, narrow tool set |
| `specialist` | strict tool/profile limits, delegation disabled by default |

## Directive

Canonical schema is the single source of truth. Framework adapters are compile targets, never policy authorities.
