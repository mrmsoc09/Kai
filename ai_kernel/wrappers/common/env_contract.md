Environment variables expected by shared wrappers and adapters:
- `RUN_ID`: unique run identifier.
- `ARTIFACT_DIR`: override artifact output base (default artifacts/<run_id>/<tool_id>/).
- `K1_SECRET_BACKEND`: env|vault selection.
- `K1_STARTUP_VALIDATE_SECRETS`: toggles strict secret validation.
