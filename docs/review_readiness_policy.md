# Review Readiness Policy (First Pass)

This policy defines conservative draft eligibility for correlated findings.

## Draft Statuses

The correlation layer uses:

- `NEEDS_REVIEW`
- `READY_FOR_REVIEW`
- `INSUFFICIENT_EVIDENCE`
- `SUPPRESSED_DUPLICATE`

## Eligibility Rules

A finding is `READY_FOR_REVIEW` only when all are true:

1. At least one evidence row is linked to the finding.
2. At least one linked observation is validation-class (`VALIDATION` category/type).
3. The finding is not marked as duplicate.

If evidence is missing:

- status is `INSUFFICIENT_EVIDENCE`

If evidence exists but validation-class observation is missing:

- status is `NEEDS_REVIEW`

If duplicate suppression applies:

- status is `SUPPRESSED_DUPLICATE`

## Placeholder Artifact Treatment

Placeholder/inline artifacts are not treated as hard proof.

- They are still persisted as evidence for traceability.
- Evidence metadata marks them as `synthetic=true`.
- Synthetic evidence may support workflow continuity but does not by itself imply exploit certainty.

## Evidence Thresholds

Current threshold is intentionally conservative and minimal:

- at least one linked evidence object
- at least one validation-class observation

This threshold is suitable for first-pass triage only and still requires human review.

## Human Review Requirement

`READY_FOR_REVIEW` means operator review can begin.

It does not mean:

- automatic vulnerability truth
- automatic external submission
- bypass of existing HiL approval/review controls
