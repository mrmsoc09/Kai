# Kai Observability And Governance Fusion

## Final Position

Kai audit/governance systems remain the primary source of truth. LangSmith is a secondary telemetry and evaluation plane.

## Primary vs Secondary Planes

| Concern | Primary | Secondary |
| --- | --- | --- |
| Governance decisions | Kai governor/runtime policy | None |
| Scope decisions | Kai scope guardrails | None |
| Mission audit lineage | Kai EventBus + artifacts | LangSmith mirror traces |
| Evaluation experiments | Kai-controlled dataset policy | LangSmith experiment execution |
| Reporting authority | Kai report gates | None |

## Correlation Model

Required identifiers on every exported span/run:
- `mission_id`
- `workflow_id`
- `phase_id`
- `node_id`
- `thread_id`
- `checkpoint_id`
- `tool_execution_id` (if tool span)
- `contract_id` (if agent/specialist span)
- `tenant_id`

Correlation hierarchy:
- mission run -> phase span -> node span -> tool/specialist span -> model spans

## Redaction and Privacy Rules

Default mode: strict.

Strict redaction must remove or hash:
- auth tokens, API keys, vault references
- raw exploit payloads and secret findings
- sensitive target identifiers where policy requires minimization
- large raw command outputs (replace with artifact pointer)

Rules:
1. Redaction runs before export serialization.
2. Failed redaction drops export and emits a Kai security event.
3. No per-request redaction bypass in multi-tenant mode.

## Failure and Degradation Handling

1. LangSmith unavailable:
- Continue mission execution.
- Buffer export queue with bounded retries.
- Keep full Kai audit trail locally.

2. Export backlog pressure:
- Drop debug-level telemetry first.
- Preserve governance, approval, and failure events.

3. Correlation mismatch:
- Quarantine telemetry payload.
- Emit parser/correlation failure artifact in Kai.

4. Evaluation subsystem failure:
- Disable non-critical eval jobs.
- Never block mission completion path.

## What Must Stay Inside Kai

- Governance decisions and approval records
- Scope allow/deny evidence
- Tool command provenance and wrapper-level execution metadata
- Report state transitions and final artifacts
- Tenant-sensitive raw findings that violate export policy

## What May Be Exported

- Redacted execution traces and timing metrics
- Structured span metadata for model/tool/node behavior
- Evaluation scores and experiment identifiers
- Non-sensitive aggregate performance metrics

## Governance Fusion With Runtime Layers

- Selector policy output is attached as audit metadata at stage start.
- Every external substrate call (Praison, DeepAgents, provider SDK) emits:
  - pre-dispatch policy check event
  - execution start/finish/failure event
  - scope/governance decision references
- Report pipeline consumes Kai artifacts only; telemetry is auxiliary.

## Compliance Invariants

1. Telemetry loss cannot alter governance outcomes.
2. Exported traces cannot become legal/compliance source of truth.
3. Audit reconstruction must be possible from Kai stores alone.
4. Every privileged action must be attributable to persona + contract + approval context.
