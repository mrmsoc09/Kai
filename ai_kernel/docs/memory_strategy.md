# Memory Strategy

Static guidance lives in `GEMINI.md`, `CLAUDE.md`, and `AGENTS.md`. Runtime operational memory is Kai-owned under `runtime/memory/*` with session/index separation. Providers may read runtime memory but must not persist data outside runtime/. No secrets or artifacts go into static guidance. Hash integrity is required for session stores and indexes.
