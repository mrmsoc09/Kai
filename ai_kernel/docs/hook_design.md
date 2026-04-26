# Hook Design

Hooks are deterministic functions with JSON-safe IO. Shared implementations live in `ai-kernel/governance/hooks`. Vendors register them in their adapters. The standard chain is session_init → scope_guard → tool_filter → result_normalizer → quality_gate. Hooks must fail closed, log reasons, and avoid stdout noise.
