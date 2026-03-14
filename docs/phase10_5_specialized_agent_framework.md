# Phase 10.5 Specialized Agent Framework

## Goal

Phase 10.5 introduces a canonical, safety-first agent framework for narrowly scoped specialized agents without creating a parallel orchestration system.

All agent runs are:

- scope/context-bound
- persisted in the canonical database
- visible in API/CLI/operator console
- explainable (confidence + reasoning + evidence refs)
- escalation-aware

## Canonical Persistence

Added canonical records:

- `agent_registry_records`
  - source of truth for enabled agents and role contracts
- `agent_execution_records`
  - execution history, routing decisions, confidence, escalation
- `agent_evaluation_records`
  - deterministic benchmark/evaluation outcomes

Migration:

- `apps/backend/alembic/versions/0011_phase10_5_specialized_agent_framework.py`

## First-Wave Agent Inventory

Phase 10.5 seeds and syncs these roles:

- `scope_parsing_agent`
- `url_discovery_classification_agent`
- `technology_fingerprint_explanation_agent`
- `delta_importance_agent`
- `duplicate_risk_agent`
- `evidence_completeness_agent`
- `opportunity_ranking_agent`
- `next_best_workflow_agent`
- `recommendation_explanation_agent`
- `alert_summarizer_agent`
- `analyst_briefing_agent`

Each agent is registered with:

- explicit input/output schema references
- allowed/forbidden tool families
- confidence threshold
- runtime bounds
- retry policy
- escalation path

## Routing Policy

Routing is self-hosted-first:

1. `K1_AGENT_MODEL_<AGENT_ID>` (explicit per-agent override)
2. `K1_AGENT_MODEL_SELF_HOSTED`
3. agent definition default (`model_preference`)

Optional escalation model:

- `K1_AGENT_MODEL_ESCALATION`

All runs record:

- `model_used`
- `routing_policy`
- confidence and escalation outcome

No silent remote fallback is introduced.

## Confidence + Escalation

If a run returns `SUCCEEDED` but confidence is below the registry threshold:

- status transitions to `ESCALATED` when an escalation agent exists
- otherwise status transitions to `DEFERRED`
- reason is persisted in `failure_reason` and output metadata

## API Surface

New canonical routes under `/api/v1/bug-bounty`:

- `POST /agents/sync`
- `GET /agents`
- `GET /agents/{agent_id}`
- `GET /agents/executions`
- `GET /agents/evaluations`
- `POST /agents/{agent_id}/run`
- `POST /agents/{agent_id}/evaluate`

## CLI Surface

Added commands under `kai-cli bug-bounty`:

- `phase10-5-agents-sync`
- `phase10-5-agents`
- `phase10-5-agent-run`
- `phase10-5-agent-executions`
- `phase10-5-agent-evaluate`
- `phase10-5-agent-evaluations`

## Operator Console Surface

Added route:

- `/agents`

The page surfaces:

- agent registry
- execution telemetry
- evaluation history
- sync/run/evaluate controls

This extends the existing operator console patterns and query architecture.

## Safety Notes

- Agents do not bypass canonical workflow, scope, or authorization systems.
- Agents do not become source-of-truth state; they write structured outputs into canonical records.
- No destructive actions are enabled by this phase.
