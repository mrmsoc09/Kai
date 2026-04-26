# Skill: Reporting

Objective: generate policy-compliant, reproducible reports linked to evidence.

When to use: after triage passes.

Inputs: triaged findings, evidence_ids, scope metadata, remediation notes.

Outputs: report objects matching `ai-kernel/governance/schemas/report.schema.json`.

Workflow:
- Assemble per-finding narrative with steps to reproduce and impact.
- Link artifact hashes and timestamps.
- Run quality_gate hook; block if missing evidence or secrets detected.
- Package for submission (email/API) via wrapper in `ai-kernel/wrappers/processing`.

Boundaries:
- No secrets or user data in report body.
- Respect program-specific disclosure rules.

Failure handling:
- Provide lint errors and required fixes before submission.
