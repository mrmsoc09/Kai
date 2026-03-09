# Governance Model

Policies in `ai-kernel/governance/policies` are the source of truth. Hooks load these policies and enforce scope, tool usage, routing, reporting, provider, and memory rules. All adapters must execute the hook chain: session_init → scope_guard → tool_filter → result_normalizer → quality_gate.
