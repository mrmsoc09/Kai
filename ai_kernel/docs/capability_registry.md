# Capability Registry

Models and tools declare capabilities in `config/registry/model_capabilities.yaml` and `config/registry/tool_registry.yaml`. Fields include tool_calling, structured_output, multimodal, context_window, privacy_tier, cost_tier, speed_tier, local_or_remote, preferred_workloads, and status. Routing engine reads this registry to pick providers per task class.
