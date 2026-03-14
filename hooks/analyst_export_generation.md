# Hook: analyst export generation

## Trigger

After prioritized findings and analyst export payload are generated.

## Purpose

Produce custom analyst bundles (internal markdown/json/csv) without changing core export schema.

## Input

```json
{
  "run_id": "wf-...",
  "analyst_export": {
    "summary": {},
    "prioritized_findings": []
  },
  "output_dir": "output/reports/<run_id>"
}
```

## Output

```json
{
  "artifacts": [
    "output/reports/<run_id>/analyst_export_custom.json"
  ],
  "warnings": []
}
```

## Failure Behavior

- Keep canonical analyst export intact.
- Record warning; do not fail completed workflow solely due to optional export hook.
