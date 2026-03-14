# Kai Architecture

## Purpose
Kai is a backend-first system for orchestrating authorized security research workflows.  
The current implementation includes a canonical campaign execution spine, worker dispatch, result ingestion, finding review, and provider payload export staging.

## System Layout

- API layer: FastAPI application in `apps/backend/src/main.py` and routers under `apps/backend/src/routers/`.
- Persistence layer: PostgreSQL via SQLAlchemy models under `apps/backend/src/models/` with Alembic migrations in `apps/backend/alembic/`.
- Orchestration layer: campaign and scheduler services under `apps/backend/src/core/`.
- Worker layer: Celery tasks in `apps/backend/src/worker/`.
- Tool catalog + wrappers:
  - `tools/registry/tool_registry.yaml`
  - `apps/backend/src/core/tool_registry_catalog.py`
  - `apps/backend/src/core/tool_adapters_bugbounty.py`
- Local workflow executor:
  - `apps/backend/src/core/workflow_executor.py`
  - `apps/backend/src/core/workflow_normalizer.py`
  - `apps/backend/src/core/workflow_data_store.py`
- Frontend: React app in `apps/frontend/` (not fully wired to canonical backend paths).

## Canonical Execution Path

1. `POST /api/v1/campaigns/start` creates a `CampaignRun`, root `ExecutionBranch`, seeded `PhaseJob` records, and a campaign-start `IntentionRecord`.
2. Scheduler evaluates dependencies and approval requirements, then queues runnable phases.
3. Dispatch creates durable `ToolExecution` records; worker tasks execute real tool runs or explicit placeholders.
4. Result ingestion updates `ToolExecution`, `PhaseJob`, `ExecutionBranch`, `CampaignRun`, and creates `Artifact` and `Observation`.
5. Correlation links observations to `Finding`, attaches `Evidence`, and manages `SubmissionDraft` readiness.
6. Human review actions transition findings/drafts and can prepare submission packages.
7. Provider export builds preview/staged payloads (no external auto-submission in current implementation).

## Source-of-Truth Entities

- Execution: `CampaignRun`, `ExecutionBranch`, `PhaseJob`, `ToolExecution`, `ApprovalGate`.
- Evidence and analysis: `Artifact`, `Observation`, `Finding`, `Evidence`.
- Review/reporting: `SubmissionDraft`, `Report`, `HILApproval`.
- Auditability: `AuditEvent`, `IntentionRecord`.

## Current Constraints

- Tool coverage is improved, but optional/manual integrations still require operator setup and binary/API availability.
- Some execution plans may still rely on placeholders where a specific runtime mapping is not configured.
- Frontend integration with canonical campaign routes is partial.
- Provider export is preview/staging only; external submission adapters are not implemented.
