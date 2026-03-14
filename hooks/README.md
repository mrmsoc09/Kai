# Kai Hook Contracts

Optional extension hooks for workflow/runtime events.

Hooks are advisory unless marked `required`. A hook must never bypass core scope and safety gates.

## Hook Files

- `pre_workflow_scope_validation.md`
- `post_tool_output_normalization.md`
- `post_workflow_summary_generation.md`
- `failure_notification.md`
- `analyst_export_generation.md`

## Common Payload Fields

- `run_id`
- `workflow_template`
- `target`
- `stage` / `tool_id` (when applicable)
- `timestamp`
- `status`
- `metadata`
