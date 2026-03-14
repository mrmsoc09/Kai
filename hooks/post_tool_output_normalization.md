# Hook: post-tool output normalization

## Trigger

After wrapper output is parsed and normalized records are generated.

## Purpose

Allow enrichment or custom mapping before records are persisted.

## Input

```json
{
  "run_id": "wf-...",
  "stage": "vuln_scan",
  "tool_id": "nuclei_scan",
  "raw_result": {},
  "normalized_records": {
    "vuln_candidates": [],
    "url_records": []
  }
}
```

## Output

```json
{
  "normalized_patch": {},
  "warnings": []
}
```

## Failure Behavior

- Hook failure should not drop base normalized records.
- System should continue with core normalized output and emit warning log.
