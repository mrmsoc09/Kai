# Finding Review Flow (First Pass)

This layer adds deterministic, auditable human review on top of correlated findings.

## Lifecycle Overview

Observation -> Finding -> Evidence Bundle -> SubmissionDraft -> Human Review -> Submission Package

No external submission is performed in this step.

## Review Actions

Supported review actions:

- `APPROVE`
- `REJECT`
- `NEEDS_MORE_EVIDENCE`
- `DUPLICATE`
- `SUPPRESS`

## Finding Status Mapping

The existing `Finding` table is reused without schema changes.  
Logical review states are mapped to existing enum values:

- logical `UNDER_REVIEW` -> `IN_REVIEW`
- logical `APPROVED` -> `HIL_APPROVED`
- logical `REJECTED` -> `REJECTED`
- logical `DUPLICATE` -> `DUPLICATE`
- logical `SUPPRESSED` -> `RESOLVED` plus `scope_json.suppressed=true`

`NEW` findings are moved to `IN_REVIEW` when review begins.

## SubmissionDraft Status Mapping

Review actions deterministically update draft status:

- `APPROVE` -> `READY_FOR_SUBMISSION`
- `NEEDS_MORE_EVIDENCE` -> `NEEDS_REVIEW`
- `REJECT` -> `CLOSED`
- `DUPLICATE` -> `SUPPRESSED_DUPLICATE`
- `SUPPRESS` -> `CLOSED`

Drafts remain tied to `finding_id`.

## Review Queue

`GET /api/v1/findings/review-queue` returns findings with reviewable draft states:

- draft status in `NEEDS_REVIEW`, `READY_FOR_REVIEW`
- finding not terminally rejected/duplicate/submitted/resolved

Each queue item includes:

- finding metadata
- campaign context (from draft)
- evidence count
- observation summary
- readiness status

## Audit Logging and Intention

Review events emit `AuditEvent` records with:

- `campaign_id`
- `finding_id`
- reviewer identity (`actor`)
- action + notes + timestamp (payload)
- `intention_id` when provided

Review metadata is also persisted in:

- `Finding.scope_json.review_history`
- `SubmissionDraft.details_json.review`
