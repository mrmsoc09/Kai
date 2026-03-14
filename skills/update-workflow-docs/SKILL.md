# update-workflow-docs

Purpose: keep workflow docs aligned with implemented execution behavior.

## Required docs

- `docs/workflows.md`
- `docs/workflow_engine.md`
- `docs/scope_enforcement.md`
- `docs/output_schema.md`

## Checklist

1. Verify templates in `workflows/definitions/`.
2. Verify stage mapping in `bugbounty_workflow_engine.py`.
3. Confirm endpoint behavior in `routers/campaigns.py`.
4. Document implemented vs pending behavior explicitly.
