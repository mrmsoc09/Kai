# LangStudio Observability Design For Kai

## Goal

Integrate LangSmith observability into Kai without weakening Kai's audit authority, safety controls, or tenant boundaries.

## Design Principles

1. Kai EventBus is source of truth for compliance and mission state.
2. LangSmith is a secondary telemetry/evaluation plane.
3. Every exported trace element must preserve Kai correlation IDs.
4. Redaction is mandatory before external telemetry export.
5. Observability failures must never block mission execution.

## Correlation Model

| Kai entity | LangSmith entity | Required correlation fields |
| --- | --- | --- |
| Mission | root run | `mission_id`, `workflow_id`, `program_id`, `tenant_id` |
| Phase | child run/span | `phase_id`, `phase_name`, `execution_mode` |
| Node execution | child run/span | `node_id`, `attempt`, `thread_id`, `checkpoint_id` |
| Tool execution | tool span | `tool_id`, `tool_name`, `policy_band`, `scope_decision_id` |
| Specialist task | specialist span | `agent_identity`, `contract_id`, `subagent_id` |
| Evaluation result | feedback/eval record | `experiment_id`, `dataset_id`, `run_id`, `metric_key` |

## Event Pipeline

1. Kai runtime emits structured events for mission/phase/node/tool/specialist lifecycle.
2. LangSmith bridge subscribes and maps events into run/span hierarchy.
3. Redaction layer strips secrets, tokens, PII, raw exploit payloads, and unsafe blobs.
4. Exported payloads include normalized tags for replay/debug joins.
5. Async export queue retries on transient failure with bounded backoff.

## Redaction Policy

- Strict mode for production: remove credentials, auth headers, vault tokens, private keys, and sensitive target payloads.
- Moderate mode only for controlled internal troubleshooting.
- No redaction bypass in tenant-facing environments.
- Truncated payload strategy for large tool outputs with pointer to local Kai artifact.

## Sampling and Cost Controls

- 100% sampling for policy events, failures, approvals, and security-relevant tool calls.
- Adaptive sampling for repetitive low-risk successful model/tool spans.
- Keep mission-level aggregate metrics even when detail spans are sampled out.
- Separate sampling profiles by execution mode (`live`, `tool_mock`, `graph_only`, `replay`).

## Failure Handling

1. LangSmith API unavailable: queue locally, degrade to Kai-only telemetry.
2. Redaction failure: drop export chunk and emit internal security event.
3. Correlation mismatch: quarantine trace segment and attach parser error artifact.
4. Backpressure: shed non-critical debug spans first, retain governance-critical spans.

## Implementation Anchors In Kai

- Bridge lifecycle: `apps/backend/src/core/langsmith_integration.py`
- Redaction: `apps/backend/src/core/langsmith_redaction.py`
- Evaluation ingestion: `apps/backend/src/core/langsmith_evaluations.py`
- Mission event source: Kai execution event bus and mission runtime modules

## Validation Criteria

- Every mission has deterministic run hierarchy mapping.
- No secret leakage in exported traces under strict mode tests.
- Telemetry outage does not change mission outcome.
- Evaluation datasets can be regenerated from mission runs deterministically.

## Recommended Rollout

1. Phase 1: mission/phase/node trace correlation and strict redaction.
2. Phase 2: tool/specialist spans with policy metadata.
3. Phase 3: online/offline evaluation loops and regression dashboards.
4. Phase 4: automated quality gates tied to release workflows.
