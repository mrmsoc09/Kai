# Finding Correlation Flow (First Pass)

This document describes the deterministic and conservative correlation layer:

Observation -> Artifact context -> Finding correlation -> Evidence linking -> Submission draft evaluation

## Observation -> Finding Decision

Correlation is deterministic and category-driven:

- `DISCOVERY`, `SIGNAL`, `CONTEXT`
  - never auto-create findings
  - recorded as contextual observations only

- `VALIDATION`, `DECISION`
  - eligible for finding creation or attachment
  - processed with deterministic matching only

No AI scoring, fuzzy matching, or probabilistic similarity is used.

## Deterministic Correlation Keys

When an observation is eligible, correlation uses:

- `campaign_id`
- normalized title
- normalized category
- target/asset identifier
- tool/phase lineage context

Target identifier resolution order:

1. observation payload target fields
2. tool execution input target
3. phase payload target
4. campaign primary scope target
5. campaign fallback identifier

## Duplicate Handling

Duplicate criteria (minimum):

- same `campaign_id`
- same normalized title/category
- same target identifier

On duplicate:

- observation is linked to the existing finding
- related artifacts are still linked as evidence
- no new finding row is created
- deduplication audit event is emitted

## Artifact -> Evidence Linking

Artifacts related to correlated observations are converted into `Evidence` rows:

- evidence kind is derived from artifact type
- URI/path is preserved
- hash uses artifact `content_hash` when valid; otherwise deterministic fallback hash
- metadata carries campaign/branch/phase/tool lineage

Inline artifacts (`inline://...`) and placeholder artifacts are preserved as evidence with `synthetic=true` in evidence metadata.

## Submission Draft Evaluation

After correlation/evidence linking, submission draft state is evaluated:

- `INSUFFICIENT_EVIDENCE`
- `NEEDS_REVIEW`
- `READY_FOR_REVIEW`
- `SUPPRESSED_DUPLICATE`

Drafts are internal-only in this step. No external bug bounty submission is triggered.

## Manual Correlation Endpoint

Operator/debug endpoint:

- `POST /api/v1/campaigns/{campaign_id}/correlate`

This processes observations in the campaign that are not yet linked to findings and returns summary counts.
