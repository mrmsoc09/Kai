# Developer Guide

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional Ubuntu bootstrap:

```bash
sudo install/bootstrap_ubuntu_22_04.sh
```

## Core Commands

```bash
make test
make verify-tools
make workflow-templates
make smoke-workflow
```

## First Complete Workflow (Local)

Run a full local workflow without API server:

```bash
python3 scripts/run_workflow_local.py \
  --template workflow_recon_surface_map \
  --target example.com \
  --safe-mode
```

Outputs are written under:

- `output/raw/<run_id>/`
- `output/normalized/<run_id>/`
- `output/reports/<run_id>/`
- `output/workflows/<run_id>/`
- `output/logs/`

## API-based Workflow Entry Points

- `GET /api/v1/campaigns/workflow-templates`
- `POST /api/v1/campaigns/start-workflow` (campaign-seeded, scheduler/worker path)
- `POST /api/v1/campaigns/execute-workflow` (local executor path, resumable artifacts)

## Extending Tools

1. Add metadata entry in `tools/registry/tool_registry.yaml`.
2. If generic CLI parsing is enough, rely on `CatalogBackedCLITool`.
3. For custom parsing, extend `apps/backend/src/core/tool_adapters_bugbounty.py`.
4. Add tests under `tests/`.

## Scope and Safety

- Scope rules: `config/scope_guardrails.yaml`
- Enforcer: `apps/backend/src/core/scope_guardrails.py`
- Safe mode defaults to blocking intrusive/manual-only tools.
