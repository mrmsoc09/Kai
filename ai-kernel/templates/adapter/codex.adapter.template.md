Adapter: Codex

Required config:
- `model`: e.g., gpt-4.1 or gpt-4o-mini
- `base_url` (optional for Azure/OpenRouter style)
- `api_key` via secret manager

Routing:
- Enable tool_calling only for models that advertise it in capability registry.
- Use structured output for governance hooks where supported.

Memory:
- Mount `runtime/memory/sessions` read/write.
- Do not store artifacts in vendor directories.
