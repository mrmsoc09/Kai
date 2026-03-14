# Tools

## Overview

Kai now uses a centralized tool catalog and registry-backed wrapper model for bug bounty execution.

Source of truth:

- Catalog definitions: `tools/registry/tool_registry.yaml`
- Catalog loader: `apps/backend/src/core/tool_registry_catalog.py`
- Wrapper registrations: `apps/backend/src/core/tool_adapters_bugbounty.py`
- Legacy wrappers retained: `apps/backend/src/core/tool_adapters_osint.py`, `apps/backend/src/core/tool_adapters_recon.py`, `apps/backend/src/core/tool_adapters_scan.py`, `apps/backend/src/core/tool_adapters_validate.py`

## Catalog Fields

Each tool entry includes:

- `name`, `category`
- `execution_mode` (`native`, `docker`, `optional`)
- `binary_path` and optional `container_image`
- `install_verification_cmd`
- `input_schema`, `output_schema`
- `timeout_seconds`, `retry_policy`
- `safety_classification`
- `tags`, `dependencies`
- `api_keys_required`
- `enabled_by_default`

## Wrapper Behavior

Catalog-backed wrappers provide:

- normalized input validation
- safe subprocess invocation with arg lists (no shell interpolation)
- timeout and retry handling
- exit-code capture
- stdout/stderr capture
- optional Docker fallback when catalog entry is `execution_mode: docker|optional` with `container_image`
- deterministic output parsing modes (`lines`, `jsonl`, `json_or_lines`, `nmap_xml`)
- evidence generation (`create_evidence_object`)

Additional internal tools:

- `k1_correlation`
- `k1_priority_ranking`

These produce deterministic correlation/ranking outputs without external side effects.

## API Surface

Tools API exposes catalog details:

- `GET /api/v1/tools/catalog/list`
- `GET /api/v1/tools/catalog/item/{tool_name}`
- `GET /api/v1/tools/health`

## Tool Health Dashboard

Kai exposes a catalog-backed health report for workflow readiness. The report is generated from:

- catalog metadata (`tools/registry/tool_registry.yaml`)
- install verification commands (`install_verification_cmd`)
- environment credential checks (`api_keys_required`)
- wrapper registration/smoke-test checks
- recent execution telemetry + canonical `ToolExecution` history (when DB is available)

Each tool record includes:

- `tool_name`, `category`, `enabled_status`
- `execution_mode`
- `binary_or_image_presence`
- `install_verification_status`
- `required_environment_variables_present`, `credential_status`
- `wrapper_smoke_test_status`
- `safe_mode_compatibility`
- `last_execution_status`, `last_failure_reason`, `last_execution_at`
- `overall_health`

Summary counters include:

- `total_tools`
- `healthy_tools`
- `tools_missing_binary`
- `tools_missing_credentials`
- `tools_with_failed_verification`

### API usage

```bash
curl "http://localhost:8080/api/v1/tools/health"
curl "http://localhost:8080/api/v1/tools/health?run_smoke_tests=true&write_report=true"
```

When `write_report=true`, Kai writes:

- `output/reports/tool_health_report.json`

### CLI usage

```bash
python -m apps.backend.src.cli.main tools health
python -m apps.backend.src.cli.main tools health --json-output
python -m apps.backend.src.cli.main tools health --smoke-tests --write-report
```

`wrapper_smoke_test_status` semantics:

- `ok`: wrapper parser and lightweight invocation checks passed
- `failed`: wrapper smoke check failed and should be investigated
- `not_registered`: no wrapper is currently registered for this catalog tool
- `skipped`: smoke checks intentionally skipped to avoid heavy external scanning

### Required vs optional tools

- Required tools are those with `enabled_by_default: true`; missing install/runtime on these tools degrades readiness.
- Optional tools (`enabled_by_default: false`) are still reported, but missing runtime does not indicate a hard readiness blocker by itself.
- `execution_mode: api|hook` tools report runtime as `not_required` and depend primarily on credentials and wrapper registration.

### Credential requirements

- Tool credential requirements are declared in catalog `api_keys_required`.
- Health checks inspect process environment variables only; missing keys are reported in `missing_keys`.
- No credentials are logged in reports, only key names and presence/absence.

## Notes

- Existing adapter IDs are preserved where already in use (`httpx_probe`, `nuclei_scan`, `amass_enum`, etc.).
- New wrappers are only added when a tool ID is missing in the current registry.
- This avoids breaking existing routes, workers, and toolpack behavior.

---

## Adding a New Tool

### 1. Add a catalog entry

Edit `tools/registry/tool_registry.yaml` and append a new entry:

```yaml
- name: mytool
  category: recon_asset_discovery          # or: vulnerability_scanning, fuzzing_content_discovery, etc.
  execution_mode: native                   # native | docker | optional
  binary_path: mytool                      # binary name as it appears in PATH
  install_verification_cmd: ["mytool", "--version"]
  input_schema: {"target": "domain"}
  output_schema: {"items": "list[str]"}
  timeout_seconds: 180
  retry_policy: {max_attempts: 1, backoff_seconds: 0}
  safety_classification: passive           # passive | active | intrusive | manual_only
  tags: ["recon"]
  dependencies: []
  api_keys_required: []
  enabled_by_default: true
```

`safety_classification` determines autonomy tier:
- `passive` → TIER_0 (fully autonomous)
- `active` → TIER_1 (notify)
- `intrusive` / `manual_only` → TIER_2 (requires approval, blocked in safe_mode)

### 2. Add parse mode (if needed)

If the tool produces non-standard output, add an entry in `TOOL_PARSE_MODE` in `tool_adapters_bugbounty.py`:

```python
"mytool": "lines",   # or: jsonl | json_or_lines | nmap_xml
```

### 3. Add build args (if needed)

If the tool requires specific CLI argument ordering, add a case in `_build_command`:

```python
elif name == "mytool":
    args.extend([target, "--output-format", "json"])
```

### 4. Register (automatic)

`register_bugbounty_tools()` is called at startup and will automatically register a `CatalogBackedCLITool` wrapper for any catalog entry not already in the global registry.

### 5. Verify installation

```bash
python3 scripts/verify_tool_registry_install.py
```

### 6. Add to a workflow template (optional)

In `bugbounty_workflow_engine.py`, add a `WorkflowStep` to an existing template or create a new `WorkflowTemplate` entry in `WORKFLOW_TEMPLATES`.
