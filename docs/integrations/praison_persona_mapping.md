# Praison Persona / Agent Schema Mapping

## Goal
Define a canonical persona schema that can be compiled to:
- Kai runtime personas
- Praison agent definitions
- CrewAI `roles` format
- future orchestrators without reauthoring mission intent

## Canonical Persona Schema

```yaml
persona_id: recon_specialist
name: Recon Specialist
class: specialist              # governor | director | coordinator | specialist
objective: Map exposed attack surface with minimal noise
instructions: >
  Enumerate and validate externally reachable assets, preserve evidence, and avoid intrusive actions.
capabilities:
  tools_allowed: [subfinder, amass, httpx]
  tools_denied: [sqlmap, nuclei]
  protocols_allowed: [mcp]
policy:
  risk_profile: recon           # governance | orchestration | recon | analysis | reporting
  approval_policy: on_request   # always | on_request | never
  autonomy_mode: suggest        # suggest | auto_edit | full_auto
  max_iterations: 15
  max_execution_time_sec: 300
  max_rpm: 60
  retries: 2
memory:
  scope: phase                  # session | phase | workflow | mission | persistent
  persistence: true
  quality_threshold: 0.7
delegation:
  allowed: false
  delegation_scope: none        # none | phase | global
handoff:
  accepts_from: [phase_coordinator]
  can_handoff_to: [evidence_analyst]
observability:
  trace_tags: [recon, external-surface]
  emit_metrics: true
compatibility:
  framework_targets: [kai, praison, crewai]
```

## Field Mapping
| Canonical field | Kai mapping | Praison mapping | CrewAI mapping | Future-system rule |
| --- | --- | --- | --- | --- |
| `persona_id` | Agent registry key | agent `name`/id | `roles.<key>` | Stable ID, never inferred from display name |
| `class` | `agent_class` with delegation constraints | role intent + autonomy profile | role semantics only (no strict class model) | Compile to nearest class with explicit loss note |
| `objective` | `goal`/mission node intent | `goal`/instructions | `goal` | Preserve verb semantics |
| `instructions` | system prompt/instructions | `instructions` | `backstory` + task descriptions | Keep single canonical source |
| `tools_allowed`/`tools_denied` | `allowed_tools` + policy gates | tool list / MCP allowlist | tool assignment per role/task | If target lacks denylist, materialize at runtime gate |
| `risk_profile` | deterministic governance tiering | approval/guardrail strategy | no native equivalent | Inject external governance wrapper |
| `approval_policy` | HIL + governance hooks | approval callback/guardrail mode | custom callback required | Never degrade to implicit allow |
| `autonomy_mode` | runtime policy + mission node config | `suggest/auto_edit/full_auto` | no direct mode primitive | Map to "approval required" policy where absent |
| `max_iterations`/`timeout`/`rpm`/`retries` | mission/runtime limits | execution/autonomy/LLM config | partial (task-level controls) | Enforce with supervisor when unsupported |
| `memory.scope` | strict Kai memory scope hierarchy | memory config + session behavior | limited native model | External state manager if missing |
| `delegation.allowed`/`delegation_scope` | contract and authority checks | handoff/delegation config | implicit team delegation | Explicitly deny if target cannot enforce |
| `handoff` | edge routing and contract targets | handoff filters/strategies | task dependencies | Compile to directed edge constraints |
| `trace_tags` | MissionEvent metadata | observability span attributes | custom tracing middleware | Preserve tags end-to-end |

## Compatibility Notes

### Kai
- Strongest policy expressiveness (scope, governance, delegation, memory scope).
- Canonical schema can be compiled with minimal loss.

### Praison
- Good support for autonomy, async jobs, approval, guardrails, and protocol integrations.
- Requires boundary enforcement so Praison approval and Kai governance do not conflict.

### CrewAI
- Uses `roles` YAML, not `steps` workflow format.
- Native policy controls are thinner; use external governance wrappers for high-risk operations.

### AG2 / future orchestrators
- Treat as execution backends.
- Canonical schema remains source of truth; backend adapters declare supported/unsupported fields.

## Translation Rules
1. Canonical schema is authoritative.
2. Any unsupported target field must be reported during compile with severity (`warn` or `block`).
3. Any policy-losing transform (`approval_policy`, `delegation_scope`, `memory.scope`) is `block` for production builds.
4. Runtime adapters must attach a `policy_manifest` artifact showing effective controls post-translation.

## Minimal Persona Classes for Kai-Praison Interop
| Class | Required controls | Typical Praison fit |
| --- | --- | --- |
| `governor` | approval required, no unsafe auto mode, full audit | approval + guardrail orchestration only |
| `director` | bounded delegation, phase-level write scope | multi-agent planner/coordinator |
| `coordinator` | no privileged tool execution by default | workflow/handoff control |
| `specialist` | `delegation_scope=none`, narrow tools | task-focused agents (recon, triage, reporting assist) |

## Recommended Implementation
- Build a canonical persona compiler in Kai that emits target-specific manifests.
- Keep framework adapters pure: no policy decisions inside adapters.
- Run schema compatibility checks in CI for every persona change.

## Cross-Links
- Capability map: [praison_capability_map.md](/home/k1-admin/Kai/docs/research/praison_capability_map.md)
- Integration architecture: [praison_kai_integration.md](/home/k1-admin/Kai/docs/architecture/praison_kai_integration.md)
- Workflow matrix: [praison_workflow_matrix.md](/home/k1-admin/Kai/docs/research/praison_workflow_matrix.md)
- Roadmap: [praison_implementation_roadmap.md](/home/k1-admin/Kai/docs/architecture/praison_implementation_roadmap.md)
