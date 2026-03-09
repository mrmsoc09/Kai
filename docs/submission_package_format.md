# Submission Package Format (First Pass)

Submission packages are generated only for approved findings (`HIL_APPROVED`) and stored in existing `SubmissionDraft.details_json.package_json`.

No outbound submission is performed.

## Package Structure

`package_json` contains:

- `finding`
  - id, program, asset, title, description, severity, status
- `campaign_context`
  - campaign_id, branch_id, phase_job_id, tool_execution_id
- `evidence`
  - evidence id, kind, uri, sha256_hex, synthetic flag, metadata
- `artifacts`
  - artifact id, uri, type, mime, hash, size, synthetic flag, lineage IDs
- `observations`
  - observation id, type, category, title, summary, confidence
- `reproduction_notes`
  - collected from validation observations
- `prepared_by`
- `prepared_at`

## Draft Persistence

When package preparation succeeds:

- `SubmissionDraft.details_json.package_json` is updated
- `SubmissionDraft.details_json.package_hash` is stored
- `SubmissionDraft.content_uri` is set to inline package URI
- `SubmissionDraft.content_hash` stores package hash
- `SubmissionDraft.status` becomes `READY_FOR_SUBMISSION`

## Evidence and Artifact Linkage

Package evidence comes from existing `Evidence` rows for the finding.

Package artifacts are gathered from:

- artifacts directly linked to `finding_id`
- source artifacts referenced by finding observations

Inline/placeholder artifacts remain represented and flagged as synthetic.

## Auditability

Package preparation emits `submission_package.prepared` audit events with:

- campaign context
- finding id
- draft id
- counts for evidence/artifacts/observations
- package hash
