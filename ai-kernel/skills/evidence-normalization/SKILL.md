# Skill: Evidence Normalization

Objective: enforce Evidence Object schema and artifact hashing across tools.

When to use: immediately after tool execution and before storage/reporting.

Inputs: raw tool output, artifact paths, metadata.

Outputs: normalized evidence aligned with `tool_result.schema.json` and `runtime_artifact.schema.json`.

Workflow:
- Hash artifacts (SHA256) and store under `artifacts/<run_id>/<tool_id>/`.
- Validate against schemas; attach scope/authorization metadata.
- Record provenance for RAG/graph indexing.

Boundaries:
- Do not store secrets or customer data in artifacts.
- Do not bypass adapter normalization.

Failure handling:
- Mark evidence invalid with reasons; require rerun or manual review.
