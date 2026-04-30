# Tool Catalog Curation (2026-04-27)

## What Was Implemented
- Curated `tools/registry/tool_registry.yaml` from 139 tools down to 93 tools.
- The curated set exactly matches the requested bug bounty tool list.
- Updated workflow templates in `apps/backend/src/core/bugbounty_workflow_engine.py` so template steps only reference tools that remain in the catalog.
- Preserved credential-aware workflow behavior by keeping an API-key-gated step (`openapi-introspection`) in `workflow_web_attack_surface`.

## Artifact Snapshot (Pre-Curation)
A full pre-change snapshot (registry + related workflow/adapter/catalog files) was archived at:

- `artifacts/tool_catalog_snapshots/20260427_193807_pre_curation/`

Snapshot contents include:
- `tool_registry.yaml` (pre-change)
- `config_tool_registry.yaml`
- `tool_registry_wave7_entries.yaml`
- `tool_registry_catalog.py`
- `tool_adapters_bugbounty.py`
- `bugbounty_workflow_engine.py`
- `workflow_executor.py`
- `scope_guardrails.py`
- related registry/workflow tests
- `tool_names_before.txt` (139 entries)
- `manifest.env`
- `checksums.sha256`

## Current State
- Active registry file: `tools/registry/tool_registry.yaml`
- Current tool count: 93
- Requested-list coverage: complete (no missing and no extra entries)
- Curated tool name export: `artifacts/tool_catalog_snapshots/20260427_curated_tool_names.txt`

## Partial / Pending
- Many curated entries are intentionally `manual_only` with `execution_mode: optional` and `wrapper_pending` dependencies. They are cataloged for governance and planning, but not all have autonomous wrappers.
- Legacy `config/registry/tool_registry.yaml` remains a narrower/legacy mapping and was not converted into a full mirror of the curated catalog.

## Operational Safety Assumptions
- `safe_mode=True` blocks `intrusive` and `manual_only` tools through scope guardrails.
- Manual-only tools remain disabled by default unless explicitly enabled and integrated.
- Workflow execution still requires target scope checks before phase generation and dispatch.
