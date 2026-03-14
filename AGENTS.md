# AGENTS.md

Operational rules for human and AI contributors in the Kai repository.

## Project Purpose

Kai is a defensive bug bounty orchestration platform focused on authorized, auditable automation.
The platform must support:

- modular tool execution
- resumable, stage-based workflows
- scope-first safety controls
- evidence-quality normalized outputs
- persistent and reviewable execution history

Kai must never run unauthorized or destructive operations by default.

## Architecture Overview

Kai is organized around these layers:

- API/control plane: FastAPI routers and service modules
- execution runtime: worker/task dispatch and tool wrappers
- workflow planning: template-driven stage graphs
- safety: scope validation and policy gates
- data surfaces: canonical backend persistence + normalized workflow artifacts

Primary implementation anchors:

- tool catalog: `tools/registry/tool_registry.yaml`
- catalog loader: `apps/backend/src/core/tool_registry_catalog.py`
- wrappers: `apps/backend/src/core/tool_adapters_bugbounty.py`
- workflow planner: `apps/backend/src/core/bugbounty_workflow_engine.py`
- workflow executor: `apps/backend/src/core/workflow_executor.py`
- scope policy: `apps/backend/src/core/scope_guardrails.py`

## Coding Rules

- Prefer small, coherent changes over broad rewrites.
- Preserve existing API contracts unless change is required and documented.
- Keep dangerous behavior opt-in and explicitly gated.
- Do not embed secrets, API keys, or local absolute paths.
- Do not bypass wrapper/adaptor interfaces from routers.
- Use deterministic parsing and explicit failure states.
- Avoid fake success statuses when a tool is unavailable or blocked.

## Wrapper Design Contract

All wrappers must provide:

- normalized input parameters with validation
- safe command construction (argument arrays, no shell string interpolation)
- timeout handling and retry behavior
- stdout/stderr/exit-code capture
- structured JSON output
- provenance metadata (tool, target, command, attempts, duration)
- explicit status semantics (`COMPLETED`, `FAILED`, etc.)

Wrappers must support heterogeneous availability:

- native binary when present
- Docker fallback when configured and available
- clear failure message when neither is available

## Schema Expectations

Normalized workflow artifacts should align with:

- `Target`
- `ScopeRule`
- `WorkflowRun`
- `StageRun`
- `ToolExecution`
- `DiscoveredAsset`
- `DNSRecord`
- `LiveService`
- `WebApplication`
- `URLRecord`
- `EndpointRecord`
- `ParameterRecord`
- `TechnologyFingerprint`
- `SecretFinding`
- `VulnCandidate`
- `CorrelationRecord`
- `AnalystExport`

Schema source:

- `apps/backend/src/schemas/bugbounty.py`

## Scope Enforcement Rules

Scope validation is mandatory before execution.

Minimum requirements:

- allowlist and denylist evaluation
- wildcard and parent/subdomain handling
- CIDR/IP policy checks when relevant
- safe mode default behavior
- explicit rejection for out-of-scope targets
- durable logging of scope decisions

Scope implementation:

- policy file: `config/scope_guardrails.yaml`
- logic: `apps/backend/src/core/scope_guardrails.py`

## Logging Requirements

All meaningful operations must emit structured records:

- workflow lifecycle events
- tool execution starts/completions/failures
- scope decisions
- normalization/correlation outcomes
- review/export actions where applicable

Logs and outputs must be reproducible and inspectable under `output/` and artifact paths.

## Testing Standards

Required test coverage for new behavior:

- wrapper unit tests (command build, parse behavior, error handling)
- workflow orchestration tests (stage generation/execution)
- scope-rule tests (allow/deny/cidr/safe-mode)
- normalized output tests for parser stability
- idempotency and replay behavior where relevant

Do not merge major execution logic without tests.

## Documentation Standards

When behavior changes, update docs in `docs/` in the same change.

At minimum document:

- what is implemented
- what is partial or pending
- expected inputs/outputs
- operational safety assumptions

Avoid roadmap hype and avoid claiming capabilities that are not code-backed.

## Internal Knowledge Structure

Repository knowledge scaffolding:

- `skills/` reusable procedural guides
- `hooks/` extension hook contracts
- `memory/` architecture/reference memory
- `prompts/` internal AI prompt templates

Contributors should extend these before introducing new architecture patterns.
