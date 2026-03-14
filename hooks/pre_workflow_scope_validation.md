# Hook: pre-workflow scope validation

## Trigger

Before workflow planning/execution starts.

## Purpose

Apply custom policy checks in addition to baseline scope rules.

## Input

```json
{
  "run_id": "wf-...",
  "workflow_template": "workflow_recon_surface_map",
  "target": "example.com",
  "safe_mode": true,
  "scope_policy_path": "config/scope_guardrails.yaml"
}
```

## Output

```json
{
  "allow": true,
  "reason": "allowed by policy",
  "metadata_patch": {}
}
```

## Failure Behavior

- If hook returns `allow=false`, workflow must stop before any tool dispatch.
- Decision should be logged to scope/audit outputs.
