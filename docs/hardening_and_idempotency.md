# Hardening and Idempotency (First Pass)

This pass hardens the canonical campaign backend for replay safety, repeated scheduler entry, repeated human actions, and operator diagnostics.

## Replay-Safe Ingestion Behavior

`ExecutionResultIngestionService` now computes a deterministic ingestion fingerprint from:

- status and result payload
- output refs/summaries
- explicit artifact/observation payloads

Behavior:

- If the same fingerprint was already ingested for the same `ToolExecution`, replay is treated as safe no-op and existing side effects are returned.
- If a replay targets a terminal execution with conflicting status/payload, ingestion is rejected with a conflict error and a diagnostic audit event.
- Terminal replays matching persisted phase output fingerprint are accepted as idempotent no-op, even if replay arrives after partial service interruption.

## Artifact / Observation Dedupe

Artifact and observation creation now include dedupe metadata in JSON payloads (`dedupe_key`, `ingestion_fingerprint`) and check existing rows before insert.

This prevents duplicate rows during:

- duplicate worker callbacks
- ingestion retries after partial failures
- operator/manual replay of identical result payloads

## Scheduler Idempotency Behavior

`BranchScheduler` now includes stronger re-entry guards:

- `RUNNING` phases are never redispatched.
- `QUEUED` phases with active executions are not redispatched.
- `QUEUED` phases with stale `worker_task_id` are skipped with diagnostics instead of duplicate dispatch.
- approval gate creation path now reuses existing gates for the same scope to avoid duplicate gate rows.

Scheduling remains deterministic from persisted state and continues to reconcile branch/campaign status conservatively.

## Review / Approval Conflict Handling

### Finding Review

- Duplicate review action attempts on already-matching finding/draft state are ignored deterministically and audited.
- Conflicting review actions against finalized findings are rejected and audited.

### Approval Gates

- Duplicate decisions (`same status` on same gate) are ignored deterministically and audited.
- Conflicting transition attempts from finalized states are rejected and audited.
- Duplicate gate creation attempts for the same campaign scope are reused instead of creating new rows.

## Retry / Failure Diagnostics

Worker paths now include explicit retry diagnostics in result payloads:

- `retry_attempt`
- `max_retries`
- `worker_task_id` context

Placeholder and Celery tool worker paths now attach clearer failure metadata to ingestion payloads so operators can distinguish repeatable worker failures from hard terminal failures.

## Known Remaining Hardening Gaps

- No true distributed lock/lease system in this step; protections are service-layer and best-effort.
- No global exactly-once guarantee across process crashes; this pass focuses on deterministic replay behavior and dedupe-on-retry.
- No advanced retry orchestration policy yet (backoff classes, retry budget governance, dead-letter automation).
- No external monitoring backend integration yet (Prometheus/OpenTelemetry intentionally out of scope).
