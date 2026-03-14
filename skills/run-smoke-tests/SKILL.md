# run-smoke-tests

Purpose: quickly validate repo health after tool/workflow changes.

## Procedure

1. Activate environment.
   - `source .venv/bin/activate`
2. Run focused checks.
   - `python3 scripts/verify_tool_registry_install.py`
   - `python3 scripts/run_workflow_local.py --template workflow_recon_surface_map --target example.com --dry-run`
3. Run workflow smoke path.
   - `bash scripts/smoke_test_workflow.sh example.com workflow_recon_surface_map`
4. Run test suite.
   - `python3 -m pytest -q`

## Pass Criteria

- smoke commands return zero
- output manifests/reports are generated under `output/`
- tests remain green
