# Adding a Provider

- Create `config/providers/<name>.yaml` using `ai-kernel/templates/docs/provider_config.template.yaml`.
- Add capability entry to `config/registry/model_capabilities.yaml`.
- Include auth method (env/vault) and privacy/cost tiers.
- Ensure routing_matrix includes the new workload mapping.
