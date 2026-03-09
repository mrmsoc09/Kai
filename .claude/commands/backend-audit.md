Use the architect and security-auditor subagents to audit the repository backend.

Produce:
- docs/backend_gap_audit.md
- docs/backend_execution_plan.md

Audit scope:
- Whether begin-scan is real execution or simulated UI flow
- All backend routes: stubbed, incomplete, or missing — with file:line references
- Worker and queue architecture: present or absent
- Database models and persistence layer completeness
- Orchestration logic: missing, partial, or broken
- Artifact generation: reports, findings, evidence packaging
- HiL pause/resume: implemented or missing
- Intention tracking status across all layers
- Tool execution path: direct subprocess or properly isolated
- Authentication and authorization flow completeness

Do not implement anything. Inspect and document only.
Reference exact files and line numbers for every finding.
Be direct. No padding. Surface every gap.
