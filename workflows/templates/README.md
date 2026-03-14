# Workflow Templates

This directory stores declarative workflow templates for campaign seeding.

- `workflows/definitions/*.yaml` contains runnable workflow sequences.
- `workflows/stages/stage_catalog.yaml` defines canonical stage names.

Runtime mapping into persisted campaign phases is handled by:

- `apps/backend/src/core/bugbounty_workflow_engine.py`
