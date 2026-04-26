# Skill: Governance Guardrails

Objective: enforce Kai defensive-only, scope-validated execution for all agent actions.

When to use: before dispatching tools, generating reports, or persisting memory.

Inputs: request_id, program_id, target, method, adapter_id, planned action.

Outputs: allow/deny decision, policy warnings, normalized context for downstream hooks.

Workflow:
- Load policies from `ai-kernel/governance/policies`.
- Validate scope + authorization, ensure adapter-bound execution.
- Strip/flag unsafe flags; record decision in session state.
- Forward to result_normalizer and quality_gate.

Boundaries:
- Must not bypass scope_validator/authorization_certificate_check.
- Deny exploit/DoS/credential paths.

Failure handling:
- Fail closed with reason; log to runtime/logs with request_id.
