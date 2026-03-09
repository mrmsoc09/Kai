# Persistence Spine Status

This document describes what persistence patterns existed before this change, what the new canonical persistence layer now covers, and what still remains to be wired.

## Legacy Persistence Patterns Still Present

The repository still contains mixed persistence approaches:
- DB-backed HiL/finding/reporting models (`findings`, `evidence`, `hil_approvals`, `reports`, `program_scopes`, `execution_contexts`).
- Filesystem JSON/JSONL stores (workflow/run/job artifacts under `artifacts/`).
- In-memory structures in legacy orchestration and approval components.
- File-only audit traces in middleware and helper utilities.

These legacy patterns were not removed in this step.

## New Canonical Persistence Layer Added

A new durable campaign execution schema now exists via ORM models + Alembic migration:

- `programs`
- `scope_targets`
- `campaign_runs`
- `execution_branches`
- `phase_jobs`
- `approval_gates`
- `tool_executions`
- `artifacts`
- `observations`
- `scan_notes`
- `submission_drafts`
- `audit_events`
- `intention_records`

### Coverage now provided

1. Campaign execution lifecycle persistence:
   - campaign, branch, phase, tool statuses
   - retry/cancel/block timestamps and metadata
2. Branch/job dependency persistence:
   - `depends_on_branch_id`
   - `depends_on_job_id`
3. Durable HiL gate persistence:
   - requested/decided actor + status + reason + notes + timestamps
4. Tool execution persistence:
   - tool identity, adapter identity, inputs, output refs, exit code, retry metadata
5. Artifact/observation persistence:
   - production lineage and metadata
   - optional finding/report linkage
6. Canonical audit event persistence:
   - event payload + entity linkage + policy/risk context
7. First-class intention persistence:
   - explicit intention records
   - direct intention linkage on major action entities

## Service/Repository Scaffolding Added

Minimal async scaffolding now exists to build orchestration against:
- `core/campaign_service.py`
- `core/approval_gate_service.py`
- `core/tool_execution_service.py`
- `core/audit_events.py`

This includes transition validation for campaign/branch/phase/gate/tool lifecycles and creation methods for canonical entities.

## What Is Still Not Wired

This step intentionally does not complete orchestration.

Still pending in future prompts:
- Triggering canonical campaign creation from existing frontend/API begin-scan paths.
- Scheduler/dispatcher wiring from `CampaignRun` + dependencies into worker queues.
- Runtime worker consumption and tool adapter execution against `phase_jobs`/`tool_executions`.
- Branch-local pause/resume engine behavior driven by dependency graph + `approval_gates`.
- Automatic artifact/observation writes from live tool results.
- Canonical migration of legacy file-backed workflow/job stores to DB-backed campaign entities.
- Unified read APIs that expose the new canonical entities to frontend views.

## Legacy Components to Migrate Eventually

Likely migration targets:
- file-backed workflow/run stores in legacy workflow/run modules
- JSONL ad hoc job queues
- in-memory approval stores and orchestration state maps
- file-only trace/audit logs that should be mirrored into `audit_events`
- ad hoc tool execution stores not tied to canonical `tool_executions`

## Reality Check

This change provides durable data and lifecycle primitives only.

It does not claim:
- complete orchestration
- complete begin-scan wiring
- full worker integration
- full UI/API migration to canonical entities

Those are next-step integration tasks on top of this persistence spine.
