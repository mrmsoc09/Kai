# Canonical Campaign Domain Model

This document describes the new durable backend domain model added for campaign-based autonomous bug bounty execution.  
This is a persistence foundation, not full orchestration.

## Core Entities

### Program
- Represents an external bounty/VRP program.
- Canonical fields include `program_key`, `name`, `platform`, policy metadata, and configuration JSON.
- Parent of `ScopeTarget` and `CampaignRun`.

### ScopeTarget
- Represents a scope unit associated with a `Program` (domain, URL, CIDR, asset).
- Stores scope eligibility (`is_in_scope`) and policy classification.
- `CampaignRun.primary_scope_target_id` can reference the campaign’s initial target.

### CampaignRun
- Represents one persisted campaign execution attempt.
- Captures campaign lifecycle state (`CREATED`, `READY`, `RUNNING`, `PAUSED`, `BLOCKED`, `COMPLETED`, `FAILED`, `CANCELED`).
- Captures declarative execution intent fields for campaign creation:
  - `initiated_by`
  - `declared_goal`
  - `declared_reason`
  - `policy_basis`
  - `risk_class`
  - `approval_required`
- Stores resumability metadata (`retry_count`, `max_retries`, `last_error`) and lifecycle timestamps.

### ExecutionBranch
- Represents branch-local execution within a campaign.
- Supports branch graphs with:
  - `parent_branch_id` (branch derivation lineage)
  - `depends_on_branch_id` (dependency-aware scheduling semantics)
- Branch lifecycle uses durable status values:
  - `PENDING`, `READY`, `RUNNING`, `WAITING_APPROVAL`, `BLOCKED`, `COMPLETED`, `FAILED`, `CANCELED`.
- Contains branch-local retry/cancel metadata.

### PhaseJob
- Represents a concrete phase unit under a branch (e.g., recon, signal, validation).
- Supports job dependency via `depends_on_job_id`.
- Durable lifecycle:
  - `CREATED`, `QUEUED`, `RUNNING`, `WAITING_APPROVAL`, `BLOCKED`, `COMPLETED`, `FAILED`, `SKIPPED`, `CANCELED`.
- Includes worker linkage placeholders (`worker_task_id`, `queue_name`) and retry metadata.

### ApprovalGate
- Durable HiL gate attached to campaign/branch/phase context.
- Durable lifecycle:
  - `PENDING`, `APPROVED`, `REJECTED`, `DEFERRED`, `EXPIRED`, `CANCELED`.
- Captures `gate_reason`, `requested_by`, `decided_by`, timestamps, operator notes, policy basis, and risk class.
- Tool executions can be explicitly linked through `tool_executions.approval_gate_id`.

### ToolExecution
- Represents a persisted tool execution attempt.
- Linked to campaign/branch/phase and optionally to approval/intention records.
- Durable lifecycle:
  - `CREATED`, `QUEUED`, `RUNNING`, `WAITING_APPROVAL`, `COMPLETED`, `FAILED`, `CANCELED`.
- Captures:
  - tool and adapter identity
  - target/input payload
  - stdout/stderr refs and summaries
  - exit code and worker task id
  - retry/cancel metadata
  - policy classification

### Artifact
- Durable artifact metadata with production lineage:
  - producing campaign/branch/phase/tool
  - optional finding/report linkage
- Stores URI/path, content hash, MIME type, size, type, and additional metadata.

### Observation
- Durable normalized observation record with optional source artifact linkage.
- Supports category/type/payload and confidence score.
- Carries campaign/branch/phase/tool/finding lineage.

### ScanNote
- Durable notes with campaign context and optional branch/phase/tool/finding/report references.
- Supports operator/system notes and intention linkage.

### SubmissionDraft
- Durable report submission draft metadata with campaign context.
- Supports finding/report linkage, lifecycle state string, actor metadata, and external submission identifiers.

### AuditEvent
- Canonical audit event table for durable event logging.
- Supports linkage to campaign/branch/phase/tool/gate/artifact/observation/finding/report/intention contexts.
- Supports policy/risk attributes, correlation IDs, event payloads, and happened-at timestamps.

### IntentionRecord
- First-class intention entity for explicit purpose tracking.
- Captures:
  - `source` (`USER`, `AGENT`, `SYSTEM`, `POLICY_ENGINE`, `OPERATOR`)
  - `intention_type` (campaign/branch/phase/tool/approval/report/note categories)
  - `initiated_by`
  - `declared_goal`
  - `declared_reason`
  - `policy_basis`
  - `risk_class`
  - `risk_posture_changed`
  - `approval_required` and `approval_reason`
  - contextual JSON
- Linked to campaign/branch/phase entities directly; execution artifacts/events reference intentions via `intention_id`.

## Relationship Spine

Primary lineage path now supported durably:

`Program -> ScopeTarget -> CampaignRun -> ExecutionBranch -> PhaseJob -> ToolExecution -> Artifact -> Observation`

Cross-links into existing persisted data:

- `Artifact.finding_id -> findings.id`
- `Artifact.report_id -> reports.id`
- `Observation.finding_id -> findings.id`
- `ScanNote.finding_id/report_id`
- `SubmissionDraft.finding_id/report_id`

This gives a persistent bridge from new campaign execution entities to existing finding/report tables.

## Intention Flow

Intention is modeled as a separate durable record (`IntentionRecord`) and also linked directly on significant action entities (`intention_id` on gate/tool/artifact/observation/note/submission/audit).

Conceptual flow:
1. Declare campaign/branch/phase intention in `intention_records`.
2. Attach that intention to execution actions (`tool_executions.intention_id`, `approval_gates.intention_id`, etc.).
3. Emit `audit_events` with the same `intention_id` to preserve decision traceability.

This allows post-hoc reconstruction of:
- who initiated an action
- intended goal and reason
- policy basis and risk posture interpretation
- where/why human approval was required

## Branch-Local Approval Blocking (Conceptual)

The model supports branch-local gating by combining:
- `execution_branches.status` and `phase_jobs.status` (`WAITING_APPROVAL`, `BLOCKED`)
- scoped `approval_gates` linked to campaign + optional branch/phase context
- dependency pointers (`depends_on_branch_id`, `depends_on_job_id`)

Expected behavior for future orchestration:
- only branches/jobs that depend on a pending gate transition to blocked/waiting states
- independent branches continue if policy allows

This branch-local behavior is not yet fully wired in orchestrator runtime code; this model enables it.
