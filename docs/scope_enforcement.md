# Scope Enforcement

## Principle

No automated workflow should execute tools against targets outside explicit authorized scope.

## Policy Source

Scope policy file:

- `config/scope_guardrails.yaml`

Fields:

- `allowlist` (domain/host patterns; supports `*.` wildcards and regex `/.../`)
- `denylist`
- `cidr_allowlist`
- `safe_mode_default`
- `strict_allowlist`

## Enforcement Points

1. Workflow planning:
   - `apps/backend/src/core/scope_guardrails.py`
   - `enforce_target_in_scope(...)`
   - `enforce_safe_mode_for_tool(...)`
   - scope decisions are written to `output/logs/scope_decisions.jsonl`

2. Runtime authorization gate:
   - `apps/backend/src/core/authorization_gate.py`
   - worker path (`run_tool_task`) rejects unauthorized execution

## Safe Mode

Template workflow requests default to safe mode and block intrusive/manual-only tools unless the operator explicitly disables safe mode.

## Branch-local approvals

Approval-required phases still follow canonical branch-local gating in scheduler/orchestration; unrelated branches may continue when policy allows.
