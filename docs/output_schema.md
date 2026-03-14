# Output Schema

## Normalized Wrapper Output

Catalog-backed tool wrappers return `ToolResult` payloads with:

- `target`
- `parsed` (normalized structure based on parser mode)
- `stdout`
- `stderr`
- `exit_code`
- `command`
- `attempts`
- `catalog_entry`
- `evidence`

## Evidence Object

Evidence is created via `create_evidence_object()` and includes:

- `evidence_id`
- `type`
- `tool`
- `target`
- `timestamp`
- `structured_data`
- `confidence_score`
- `artifacts[]`:
  - `artifact_path`
  - `sha256`
  - `mime_type`
  - `description`
- `scope_status`

## Campaign Execution Persistence

Worker result ingestion persists:

- `ToolExecution`
- `Artifact`
- `Observation`
- `AuditEvent`

through:

- `apps/backend/src/core/execution_result_service.py`
- `apps/backend/src/core/artifact_service.py`
- `apps/backend/src/core/observation_service.py`

## Correlation Output

Internal correlation emits deterministic structures:

- host → ports/services/urls/endpoints/parameters mapping
- duplicate suppression keys
- priority queue with conservative severity/exploitability hints

Implemented in:

- `apps/backend/src/core/recon_correlation.py`

## Normalized Workflow Models

Normalized workflow model schemas are defined in:

- `apps/backend/src/schemas/bugbounty.py`

Models include:

- `Target`, `ScopeRule`
- `WorkflowRun`, `StageRun`, `ToolExecution`
- `DiscoveredAsset`, `DNSRecord`, `LiveService`, `WebApplication`
- `URLRecord`, `EndpointRecord`, `ParameterRecord`
- `TechnologyFingerprint`, `SecretFinding`, `VulnCandidate`
- `CorrelationRecord`, `AnalystExport`

Persistence helper:

- `apps/backend/src/core/workflow_data_store.py`
