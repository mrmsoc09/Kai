---
name: debug-tool-failure
description: Skill for debug-tool-failure
---

# debug-tool-failure

Purpose: diagnose failing tool execution in worker/campaign paths.

## Steps

1. Check tool exists and is enabled:
   - `GET /api/v1/tools/{tool_id}`
   - `GET /api/v1/tools/catalog/item/{tool_name}`
2. Verify binary/API availability:
   - `python3 scripts/verify_tool_registry_install.py`
3. Inspect canonical execution records:
   - `ToolExecution` status, `exit_code`, `error_message`
   - linked `Artifact` and `Observation`
4. Inspect audit events for replay/transition conflicts.

## Common causes

- tool binary missing
- scope/authorization gate rejection
- toolpack policy disabled adapter
- unsafe action blocked by safe mode
