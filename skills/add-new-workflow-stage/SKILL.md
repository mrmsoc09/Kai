---
name: add-new-workflow-stage
description: Skill for add-new-workflow-stage
---

# add-new-workflow-stage

Purpose: add a workflow stage while preserving canonical stage ordering and safety semantics.

## Procedure

1. Define stage intent.
   - expected inputs
   - expected outputs
   - safety class (passive/active/intrusive/manual)
2. Add/position stage in `apps/backend/src/core/bugbounty_workflow_engine.py` (`STAGES`).
3. Update relevant template definitions in `workflows/definitions/*.yaml`.
4. Ensure each stage step maps to a registered tool id.
5. Verify scope/safe-mode behavior.
   - intrusive/manual steps must be approval-aware
6. Add tests.
   - template planning output
   - stage dependency ordering
   - dry-run and execute behavior
7. Update docs.
   - `docs/workflows.md`
   - `docs/workflow_engine.md`
