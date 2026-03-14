# Hook: failure notification

## Trigger

When a stage/tool/workflow transitions to failed state.

## Purpose

Route failure diagnostics to operator channels (log sink, webhook, queue).

## Input

```json
{
  "run_id": "wf-...",
  "stage": "live_host_validation",
  "tool_id": "httpx_probe",
  "status": "FAILED",
  "error": "binary not found",
  "severity": "warning"
}
```

## Output

```json
{
  "notified": true,
  "channel": "internal_log",
  "notification_id": "evt-..."
}
```

## Failure Behavior

- Notification failures must never mask the original execution failure.
- System logs fallback failure-notification error and continues.
