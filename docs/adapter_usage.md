# Adapter Usage

- Gemini: uses `.gemini/settings.json` and hooks under `.gemini/hooks`.
- Claude: uses `.claude/settings.json` and hooks under `.claude/hooks`.
- Codex: uses shared skills and provider gateway; configure OpenAI/OpenRouter credentials via env/Vault.
- Sync adapters with `bash scripts/sync_adapters.sh`.
