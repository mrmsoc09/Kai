# leakix Output Patterns

Expected output is JSON and may include sparse or partial fields depending on API limits. Parsing logic must tolerate empty objects, missing keys, and mixed record quality while preserving deterministic field mapping.

All findings are normalized with target, severity, confidence, source_tool, context, and recommended next actions for orchestration continuity.
