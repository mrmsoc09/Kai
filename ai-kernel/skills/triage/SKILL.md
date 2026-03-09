# Skill: Finding Triage

Objective: de-duplicate, validate severity, and ensure reproducibility.

When to use: after recon signals and before report drafting.

Inputs: candidate findings, Evidence Objects, scope metadata.

Outputs: triaged findings with duplication verdict, severity, required evidence list.

Workflow:
- Run duplicate detection (hash of key evidence + target).
- Check evidence completeness and schema conformance.
- Request clarifying data if gaps; otherwise mark ready for reporting.

Boundaries:
- Do not auto-escalate severity without evidence.
- Do not store PII/secrets in triage notes.

Failure handling:
- Return actionable reasons; tag findings as `needs_evidence` or `needs_scope_review`.
