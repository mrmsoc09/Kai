# KAI Security Notes

## 2026-03-05

### Security-impacting decisions in this execution cycle
- Maintained strict adapter-only execution path; no direct external tool invocation bypasses introduced.
- Preserved mandatory authorization gate sequencing (`scope_validator`, `authorization_certificate_check`) in worker path.
- Added centralized OPSEC gate (rate/concurrency/hourly budget controls) to execution pipeline.
- Enforced evidence integrity in report packaging via artifact hash revalidation.
- Added explicit approval checks for outbound SMTP sends and approval-gated draft communication workflow.
- Added auditable submission lifecycle and payout ledger records with run/finding linkage.
- Enforced Vault-manager-only production secret retrieval for remaining connector paths (`notification_service`, validation adapters, Neo4j password path, LLM API key resolvers).
- Added repository-level unmanaged secret-read detector (`scripts/check_unmanaged_secrets.py`) and CI gate.
- Added toolpack-adapter compatibility gate and integrated it into weekly update automation + CI.
- Added governance readiness endpoint to expose policy/claims/benchmark/secrets gate posture for release controls.
- Added deterministic hook registry with auditable pre/post/approval/retry/safety hook events.
- Added non-bypassability static gate to CI and weekly updates to block unauthorized execution-path regressions.
- Added deterministic confidence policy enforcement in model assignment to stop/escalate low-confidence decisions.
- Added model-decision telemetry logging (confidence/cost/latency/policy action) for AI governance auditability.
- Added signed skill-router context contracts (run/program/certificate/user HMAC signature verification) to prevent unsigned skill invocation paths.
- Replaced placeholder certificate signature validation with deterministic signature verification (fail-safe configurable for legacy unsigned certs).
- Replaced pending approval TODOs with explicit execution-state tracking for approve/reject flows.

### Known security/testing constraints
- Runtime unit tests are currently limited by missing local test dependencies (`pytest`, some optional libs in this runtime).
- Current mitigations: static compile checks and deterministic script-based benchmark/claims verification.

### Follow-up security tasks (tracked in EXECUTION_PLAN)
- Containerized E2E compose runtime validation is blocked by Docker daemon permissions in this environment (`KAI-019`, see `docs/BLOCKERS.md`).
