# Workflows

## Overview

Kai supports template-based bug bounty campaign seeding on top of canonical campaign persistence and scheduler mechanics.

Template engine:

- `apps/backend/src/core/bugbounty_workflow_engine.py`

Template definitions:

- `workflows/definitions/workflow_recon_surface_map.yaml`
- `workflows/definitions/workflow_web_attack_surface.yaml`
- `workflows/definitions/workflow_quick_vuln_sweep.yaml`
- `workflows/definitions/workflow_secret_exposure_scan.yaml`
- `workflows/definitions/workflow_priority_target_ranking.yaml`

## Canonical Stage Set

- `passive_recon`
- `active_recon`
- `live_host_validation`
- `web_crawling`
- `endpoint_discovery`
- `parameter_discovery`
- `vuln_scan`
- `secret_scan`
- `tech_fingerprint`
- `prioritization_and_correlation`
- `report_prep`

## API Endpoints

- `GET /api/v1/campaigns/workflow-templates`
- `POST /api/v1/campaigns/start-workflow`
- `POST /api/v1/campaigns/execute-workflow`

`start-workflow` supports:

- dry-run plan generation (`dry_run=true`)
- safe mode enforcement
- per-step enable/disable (`enable_steps`, `disable_steps`)
- persisted phase seeding into canonical `CampaignRun`/`ExecutionBranch`/`PhaseJob`

`execute-workflow` supports:

- end-to-end execution without waiting for Celery orchestration
- resumable workflow manifests (`resume=true`)
- normalized output emission under `output/`

## Minimum Viable Workflows

- `workflow_recon_surface_map`
- `workflow_web_attack_surface`
- `workflow_quick_vuln_sweep`
- `workflow_secret_exposure_scan`
- `workflow_priority_target_ranking`

## Execution Model

Workflow templates are converted into ordered `PhaseSeedSpec` entries with dispatch payloads:

- `dispatch.tool_id` references a registered adapter/tool
- `dispatch.params` carry normalized target input
- scheduler enqueues and dispatches via existing worker path (`run_tool_task`)

## Resumability

Resumability is provided by existing canonical persistence:

- persisted campaign/branch/phase/tool state
- replay-safe scheduler runs
- replay-safe result ingestion

Restart behavior does not depend on in-memory workflow state.
