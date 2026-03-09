# Skill: Provider Routing

Objective: select the right provider/model per task using capability registry and routing policies.

When to use: before any LLM/agent call.

Inputs: task type, privacy level, cost tier, required capabilities (tool_calling, structured_output, multimodal).

Outputs: provider/model selection with fallback chain.

Workflow:
- Load capability registry from `config/registry/model_capabilities.yaml`.
- Apply routing_policy and environment profile (config/environments/*.yaml).
- Emit primary + fallback list; record decision in runtime/logs.

Boundaries:
- Do not route to providers below required privacy tier.
- Do not exceed cost ceilings of current environment.

Failure handling:
- Return `no_route` with reasons; avoid blind retries.
