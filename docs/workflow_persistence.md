# Workflow Persistence

## Scope
Kai workflow execution now persists canonical records in the primary DB layer while preserving existing disk artifacts.

Disk outputs are still written under:
- `output/raw`
- `output/normalized`
- `output/workflows`
- `output/reports`
- `output/logs`

DB records link back to those artifact paths for queryable run history.

## Canonical Entities

### `workflow_runs`
Stores one workflow execution instance.

Key fields:
- `id`
- `campaign_run_id`
- `scope_target_id`
- `template_name`
- `target`
- `status`
- `safe_mode`
- `dry_run`
- `trigger_source` (`API`/`CLI`/scheduler-compatible text)
- `started_at`, `ended_at`, `duration_ms`
- `artifact_manifest_path`
- `plan_artifact_path`
- `summary_artifact_path`

### `stage_runs`
Stores per-stage execution state inside a workflow run.

Key fields:
- `id`
- `workflow_run_id`
- `campaign_run_id`
- `stage_name`
- `status`
- `phase_count`
- `completed_count`
- `failure_reason`
- `started_at`, `ended_at`, `duration_ms`

### `tool_executions` (extended)
Existing canonical table now also supports workflow stage linkage.

New workflow-relevant fields:
- `stage_run_id`
- `execution_mode`
- `artifact_path`
- `duration_ms`

### `workflow_findings`
Canonical normalized vulnerability/candidate persistence for workflow runs.

Key fields:
- `id`
- `workflow_run_id`
- `campaign_id`
- `stage_run_id`
- `tool_execution_id`
- `asset_identifier`
- `endpoint`
- `parameter`
- `vulnerability_type`
- `confidence_score`
- `severity_hint`
- `evidence_artifact_path`
- `details_json`

### `correlation_records` (extended)
Existing canonical table now supports workflow-signal correlation output.

Workflow fields:
- `workflow_run_id`
- `asset_identifier`
- `signal_sources_json`
- `confidence`
- `priority_rank`
- `explanation`

Legacy finding/observation/campaign linkage remains supported.

## Execution Write Flow
`WorkflowExecutor` persists state in this order:
1. Create/reuse local campaign context for CLI/API local execution.
2. Create `workflow_run` (or reuse latest for resume when available).
3. Create `stage_runs` for configured stages.
4. For each phase/tool:
   - create `tool_execution`
   - mark running
   - execute tool
   - write raw + normalized artifacts to disk
   - mark terminal tool status with summaries, exit code, and `artifact_path`
   - persist `workflow_findings` for normalized vuln candidates
5. Persist `correlation_records` from correlation graph output.
6. Write report/summary/manifest artifacts and finalize workflow status.

Partial failures are retained as run history:
- artifact files are still written
- stage/tool records are persisted
- workflow final status is `FAILED` in DB when one or more stages fail

## API Query Surface
Canonical workflow persistence is exposed via:

- `GET /api/v1/campaigns/workflows/runs`
- `GET /api/v1/campaigns/workflows/runs/{workflow_run_id}`
- `GET /api/v1/campaigns/workflows/runs/{workflow_run_id}/stages`
- `GET /api/v1/campaigns/workflows/runs/{workflow_run_id}/tool-executions`
- `GET /api/v1/campaigns/workflows/runs/{workflow_run_id}/findings`
- `GET /api/v1/campaigns/workflows/runs/{workflow_run_id}/correlations`

## CLI Integration
`scripts/run_workflow_local.py` now opens a canonical DB session and executes `WorkflowExecutor(db=..., trigger_source="CLI")`, so local runs persist DB workflow records in addition to artifact files.

## Migration
Schema alignment is implemented by:
- `0004_workflow_persistence.py`
- `0005_workflow_persistence_extensions.py`

Run:
```bash
alembic upgrade head
```
