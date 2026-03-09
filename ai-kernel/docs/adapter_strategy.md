# Adapter Strategy

Shared logic stays in `ai-kernel`. Each platform adapter (Gemini/Claude/Codex) hosts its own settings, policies, hooks, and state directories, but these are rendered from shared templates. No direct provider lock-in; adapters call the provider gateway and respect governance hooks.
