# Security Model

## Security Objectives

- Enforce authorized access to API operations.
- Preserve auditability for execution and human decisions.
- Keep provider export non-destructive (no automatic external submission).
- Maintain branch-local approval gating instead of global freeze.

## Authentication and Authorization

- API auth is implemented in `apps/backend/src/core/auth.py`.
- Role checks use `require_roles(...)` dependencies at route level.
- Canonical mutation surfaces are authenticated and role-gated:
  - `/api/v1/campaigns` mutation routes require operator/analyst/admin.
  - `/api/v1/findings` review/prepare/export mutation routes require operator/analyst/admin.
  - `/api/v1/tools` execute/orchestrate routes require operator/analyst/admin; approve/reject require analyst/admin.
  - `/api/keys` key-management routes require admin.
- Legacy mutation routes in `/findings` (`/set_status`, `/ingest/tool-result`) require operator/analyst roles.
- Non-production developer token fallback is supported for test/dev contexts.
- JWT support is present; import-time failure for optional JWT dependency is guarded.

## Scope and Policy Controls

- Scope acceptance checks exist in `core/scope.py` (`X-Accept-Scope` / `ACCEPT_SCOPE` behavior).
- Template workflow planning enforces allowlist/denylist/CIDR policy via `core/scope_guardrails.py`.
- Scope policy defaults are configured in `config/scope_guardrails.yaml`.
- Tool execution path enforces authorization and OPSEC policy checks before execution.
- Risk/policy class fields are persisted on campaign, branch, phase, scope target, and intention entities.

## Human-in-the-Loop Controls

- Approval gates are durable entities with requester/decider identity and notes.
- Approval-required phases are moved to `WAITING_APPROVAL`.
- Decision handling is auditable and re-triggers scheduling.
- Gate logic is branch-local; unrelated branches can continue if eligible.

## Audit and Intention Continuity

- `AuditEvent` is written for campaign lifecycle, scheduling, ingestion, review, and export events.
- `IntentionRecord` captures:
  - source/type
  - initiated_by
  - declared goal/reason
  - policy basis / risk class
  - approval requirement context
- Intention linkage propagates across execution and review workflows where available.

## Secret Handling

- Secret access boundary uses `SecretManager`.
- Unmanaged secret read policy is validated by `scripts/check_unmanaged_secrets.py`.
- `key_manager` resolves Vault token with explicit precedence:
  1. constructor argument
  2. `VAULT_TOKEN` environment
  3. optional secret-manager lookup
  4. explicit error when unavailable

## Hardening Notes

### Authorization gate test-mode bypass
`authorization_gate.py` supports a test-mode relaxation path gated by `K1_TEST_MODE=1` AND `K1_RELAX_AUTH_GATES_FOR_TESTS=true`. Both flags must be explicitly set to `true`. `K1_RELAX_AUTH_GATES_FOR_TESTS` defaults to `false` — it is never on in production deployments. Do not set `K1_TEST_MODE=1` in any internet-accessible container.

### Certificate signature validation
`kai_security_guardrails.py` validates certificate signatures with HMAC-SHA256. `K1_ALLOW_UNSIGNED_CERTIFICATES` defaults to `false` — unsigned certificates are rejected. Set `K1_AUTH_CERT_SIGNING_KEY` in production. If neither flag nor key is configured, certificates will be rejected.

### Wildcard domain matching
The `_matches_target` wildcard check in `kai_security_guardrails.py` and the glob resolver in `scope_resolver.py` both enforce a dot-boundary: `*.example.com` matches `sub.example.com` but not `evilexample.com`.

### Tool output size cap
`CatalogBackedCLITool` caps stdout at ~25 MB chars before parsing. nmap XML output is additionally capped at 50 MB before XML parsing to prevent XML bomb DoS.

### Collection file path restriction
`IntegrationHookTool` restricts Postman/Insomnia collection reads to paths within `K1_ARTIFACTS_ROOT`. Paths outside this directory are silently rejected without error — collection_summary returns None.

### Vault credential failures
When a tool declares `api_keys_required` in the catalog, Vault failure is fatal — the task is terminated with FAILED status rather than proceeding without credentials. Tools with no `api_keys_required` log a warning and continue.

## Current Limitations

- No true distributed lock manager; conflict safety is guard-based at service layer.
- Export adapters stage payloads only and do not perform outbound provider submission.
- Legacy modules outside canonical execution paths still have mixed artifact path configuration styles.
- `kai_security_guardrails.py` authorization ledger uses full-file JSON overwrite, not append-only. This means the ledger is mutable post-fact. Move to PostgreSQL or JSONL append for tamper-evidence.
- `approved=True` in `tool_runner.enqueue()` is caller-controlled. No persistent approval record is verified server-side. A proper implementation would verify against a database row before queuing.
- `kai_orchestrator.py` builds subprocess commands using `shlex.split()` on a string. Prefer `list[str]` argument construction (as in `CatalogBackedCLITool`) to eliminate string-based tokenization risk.
