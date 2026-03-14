# Configuration Standards Memory

Primary config sources:

- `.env` / `.env.example`
- `config/scope_guardrails.yaml`
- `tools/registry/tool_registry.yaml`

Standards:

- no secrets committed to repository
- all optional integrations must degrade gracefully
- defaults must favor safety (`safe_mode` on)
- paths must be relative/repo-safe unless explicitly configured

Key environment variables:

- `K1_TOOL_REGISTRY_PATH`
- `K1_SCOPE_POLICY_PATH`
- `K1_WORKFLOW_OUTPUT_ROOT`
- `SHODAN_API_KEY`
- `CENSYS_API_ID`
- `CENSYS_API_SECRET`

Validation:

- run `scripts/verify_tool_registry_install.py`
- run workflow dry-run before active execution
