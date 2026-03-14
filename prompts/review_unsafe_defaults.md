# Prompt: Review Unsafe Defaults

Audit Kai for defaults that can create security, scope, or operational risk.

Check:

- safe_mode defaults
- scope denylist/allowlist behavior
- approval requirements for intrusive/manual tools
- fallback behaviors when tool/runtime is missing
- secret handling and env defaults
- logging/audit completeness for blocked actions

Deliver:

- concrete findings with file references
- minimal corrective patches
- tests proving behavior
