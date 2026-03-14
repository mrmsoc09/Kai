# Hook: post-workflow summary generation

## Trigger

After workflow summary and report artifacts are produced.

## Purpose

Attach additional derived metrics or custom summary fields.

## Input

```json
{
  "run_id": "wf-...",
  "workflow_template": "workflow_recon_surface_map",
  "summary_path": "output/workflows/<run_id>/summary.json",
  "report_path": "output/reports/<run_id>/report.md",
  "metrics": {
    "stages_total": 6,
    "tool_executions_total": 11
  }
}
```

## Output

```json
{
  "summary_patch": {},
  "report_appendix": null
}
```

## Failure Behavior

- Workflow status remains unchanged.
- Log warning and preserve original summary/report files.
