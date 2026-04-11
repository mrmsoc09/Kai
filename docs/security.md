# Kai Platform Security

> **Governance, Policy, and Architecture for High-Assurance Missions.**

Kai enforces a **defense-in-depth governance model** with five independent enforcement layers. Every tool execution must pass through all layers; a denial at any layer is authoritative and final.

---

## 1. Governance Model Overview

### Enforcement Layers (in execution order)

| Order | Layer | Module | Latency | LLM Required |
|-------|-------|--------|---------|--------------|
| 1 | **PraisonGovernor sync fast-path** | `praison_governor.py` | Sub-millisecond | No |
| 2 | **Scope guardrails** | `scope_guardrails.py` | Sub-millisecond | No |
| 3 | **Authorization gate** | `authorization_gate.py` | Low (DB lookup possible) | No |
| 4 | **Scope resolver** | `scope_resolver.py` | Low (async DB lookup) | No |
| 5 | **KAI orchestrator** | `kai_orchestrator.py` | Sub-millisecond | No |

### Layer Responsibilities

**Layer 1 -- PraisonGovernor**
The first enforcement point. Sync `validate_tool_request()`:
- **Band 3 tools**: Unconditionally blocked.
- **Band 2 tools**: Require campaign context (`workflow_id` + `program_id`).
- **Band 0-1 tools**: Approved for downstream validation.

**Layer 2 -- Scope Guardrails**
Canonical scope policy engine. Priority:
1. **Empty / invalid target**: Rejected.
2. **Denylist match**: Rejected (always first).
3. **CIDR allowlist match**: Approved.
4. **Allowlist match**: Approved.
5. **Strict allowlist**: Rejected if no match.

**Layer 3 -- Authorization Gate**
Enforces identity and PGP certificate chain validation.

---

## 2. Tool Risk Bands

All tools are classified into four risk bands.

| Band | Policy | Description | Examples | Governance Path |
|------|--------|-------------|----------|-----------------|
| **Band 0** | Always autonomous | Passive collection. | `whois`, `dns_lookup` | Sync pass-through. |
| **Band 1** | Autonomous within scope | Low-risk active checks. | `port_scan`, `http_probe` | Sync pass-through + Scope check. |
| **Band 2** | Approval required | State-modifying/Intrusive. | `nuclei_scan` | **HIL Approval Required**. |
| **Band 3** | Never autonomous | Exploitation/Destructive. | `exploit_exec` | **Hard Blocked**. |

Additional runtime guardrail:
- `metasploit-framework` executes in **CHECK-only** mode in Kai (`check; exit -y`), with sanitized target/module input and no free-form `extra_args`.

---

## 3. Role-Based Access Control (RBAC)

Kai implements role-based access control at the API layer (`apps/backend/src/core/auth.py`).

### Roles
*   **Admin**: Full access to all resources, including key management and system configuration.
*   **Analyst**: Can start missions, approve Band 2 requests, and review findings.
*   **Operator**: Can view missions and results but cannot approve sensitive actions.

### Enforcement
*   **Mutation Routes** (`POST /api/v1/campaigns`): Require `operator`, `analyst`, or `admin`.
*   **Approval Routes** (`POST /api/v1/tools/approve`): Require `analyst` or `admin`.
*   **Key Management** (`/api/keys`): Require `admin`.

---

## 4. Human-in-the-Loop (HIL) Flow

When a Band 2 tool is requested:
1.  **Governor** checks context.
2.  **LLM Risk Assessment** is generated (async).
3.  **Approval Request** is created in the database.
4.  **Mission Pauses** at the node.
5.  **Human Operator** approves or rejects via Analyst Cockpit.
    *   **Approve**: Tool dispatched to `intrusive` queue.
    *   **Reject**: Node fails with `GovernanceViolation`.

---

## 5. Delegation Contracts

Every agent delegation carries a **frozen, immutable contract**.

*   `allowed_tools`: Tuple of permitted tools. Empty tuple = **NO tools**.
*   `allowed_targets`: Tuple of permitted scopes.
*   `delegation_scope`: `local`, `phase`, `global`, or `none`.

**Invariants:**
*   A Coordinator cannot delegate to another Coordinator (only to Specialists).
*   A Specialist cannot delegate at all.
*   Contracts are validated before activation.

---

## 6. Secrets Handling

*   **Vault Integration**: Credentials are fetched by the Celery worker at execution time.
*   **Redaction**: Secrets are stripped from logs and LangSmith traces.
*   **No Leakage**: `_credentials` keys are transient and never persisted to the database or artifact storage.

---

## 7. Sandbox Restrictions (DeepAgents)

Specialist agents execute code in isolated sandboxes.

*   **Blocked Modules**: `os`, `subprocess`, `socket`, `requests` (unless explicitly allowed).
*   **No Network**: Sandboxes are air-gapped by default.
*   **TTL**: Sandboxes auto-destroy after 1 hour.
*   **Memory Limit**: 256MB per sandbox.

---

## 8. Simulation Safety

In simulation modes (`graph_only`, `tool_mock`, `replay`):
*   **Live Tools**: Hard blocked via `is_live_tool_blocked()`.
*   **Live Models**: Blocked in `graph_only`.
*   **Provenance**: All artifacts tagged with `_simulation=True`.

---

## 9. Authentication Model

### 9.1 Supported Auth Methods

| Method | Header | Use Case |
|--------|--------|----------|
| JWT Bearer | `Authorization: Bearer <token>` | Interactive sessions, UI |
| API Key | `X-API-Key: <token>` | CLI, integrations, CI/CD |

API Key takes priority when both are present.

### 9.2 JWT Configuration

```bash
JWT_SECRET_KEY=<min-32-char-random-string>    # required
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30            # default
JWT_ALGORITHM=HS256                           # default
```

Operational guardrails:
- Insecure JWT defaults are rejected by auth helpers unless explicitly opted-in for non-production testing (`K1_ALLOW_INSECURE_JWT_SECRET=true`).
- Supported signing algorithms are restricted to HMAC SHA-2 (`HS256|HS384|HS512`).

JWTs carry: `sub` (user_id), `tid` (tenant_id), `rol` (role), `exp`, `iat`.

Token blocklist checked on every request via `core/token_blocklist.py`.

### 9.3 API Token Hashing

API tokens are SHA-256 hashed before storage. The raw token is returned **only at creation time** and cannot be retrieved again.

---

## 10. RBAC — Role-Based Access Control

### 10.1 Role Hierarchy

```
ADMIN > ANALYST > OPERATOR > VIEWER
```

Roles are hierarchical: a user with ADMIN can satisfy any role requirement. A user with OPERATOR can satisfy OPERATOR and VIEWER requirements.

### 10.2 Role Permissions

| Role | Permissions |
|------|-------------|
| **admin** | Full access. Create tenants, create users, manage settings, view billing. |
| **analyst** | Run missions, approve governance, view all artifacts, query usage. |
| **operator** | Run missions, approve governance actions (Band 2), view own tenant data. |
| **viewer** | Read-only access to missions, artifacts, events. Cannot trigger actions. |

### 10.3 Route Protection

Routes are protected via `require_roles()` dependency:

```python
@router.post("/missions")
async def create_mission(
    _auth=Depends(require_roles(ROLE_OPERATOR, ROLE_ADMIN))
):
    ...
```

Frontend enforcement is additive (UI hides actions) but backend is the authority.

---

## 11. Multi-Tenant Isolation

### 11.1 Tenant Model

Every resource (users, API tokens) is scoped to a `tenant_id`. Authentication resolves `tenant_id` from the JWT claim `tid` or from the API token record.

### 11.2 Isolation Rules

- No cross-tenant data access. Tenant-aware surfaces enforce `tenant_id` server-side.
- Tenant admin can manage their own users only.
- Platform superadmin (ADMIN with `is_superuser=True`) can manage all tenants.
- `tenant_id` is validated at the dependency layer, not at the handler level.
- Realtime mission subscription and admin broadcast paths validate mission ownership before event delivery.

### 11.3 Tenant Boundaries in Resources

| Resource | Tenant Enforcement |
|----------|--------------------|
| Users | `tenant_id` on User model, unique constraint per tenant |
| API Tokens | `tenant_id` on APIToken model |
| Missions | `tenant_id` in mission context, usage tracking |
| Intelligence Memory | tenant-filtered read paths for non-admin users |
| Reports | tenant-scoped list/get/export when JWT includes `tid` |
| Artifacts/Timeline | mission-to-tenant runtime guard where mission ownership can be resolved |
| Audit Log | `tenant_id` field in every record |

---

## 12. Audit Logging

All security-relevant events are written to `artifacts/audit/audit.jsonl`:

### 12.1 Record Schema

```json
{
  "audit_id":   "uuid",
  "timestamp":  "2026-03-18T12:00:00Z",
  "event_type": "governance.decision",
  "tenant_id":  "uuid",
  "user_id":    "uuid",
  "mission_id": "uuid",
  "decision":   "blocked",
  "reason":     "Band 3 tool unconditionally denied",
  "detail":     { "tool_id": "...", "target": "..." }
}
```

### 12.2 Event Types

| Event | Trigger |
|-------|---------|
| `auth.login` | Login attempt (success or failure) |
| `auth.api_token_issued` | API token created |
| `auth.api_token_revoked` | API token revoked |
| `governance.decision` | Tool approved/blocked by governance |
| `approval.action` | HIL approval/rejection |
| `mission.created` | Mission started |
| `scope.violation` | Scope boundary violated |

### 12.3 Log Security

- Append-only writes with threading lock
- No in-place modification (tamper-evident)
- Log path overridable via `K1_AUDIT_LOG_PATH`
- Write failures log a warning but never break the request path

---

## 13. Rate Limiting

Configured via environment or defaults in `core/rate_limiter.py`:

| Endpoint Pattern | Default Limit |
|-----------------|---------------|
| `/missions` (POST) | 10 req/min per IP |
| `/auth/token` | 5 req/min per IP |
| `/simulation` | 5 req/min per IP |
| General API | 120 req/min per IP |

Redis-backed sliding window in production, in-memory in development.

Set `K1_TRUSTED_PROXY_CIDRS` to trust `X-Forwarded-For` from known reverse proxies.

---

## 14. Usage Tracking

All resource consumption is recorded to `artifacts/usage/usage.jsonl` for future billing:

- LLM token usage (by provider, model, mission, tenant)
- Tool executions (by tool, status, duration)
- Mission runs (by mode, workflow)
- Simulation runs (by mode, scenario)

Query via: `GET /billing/usage/summary?tenant_id=<id>` (OPERATOR+)

---

## 15. Security Checklist for Production

- [ ] `JWT_SECRET_KEY` is ≥ 32 random chars (`openssl rand -hex 32`)
- [ ] `K1_DEV_TOKEN` is unset or rotated in production
- [ ] `K1_ENABLE_BOOTSTRAP_AUTH=false` in production (`assert_bootstrap_auth_safe()` enforces)
- [ ] `CORS_ALLOWED_ORIGINS` is restricted to your domain(s)
- [ ] `COOKIE_SECURE=true` in production
- [ ] Vault is unsealed and `VAULT_TOKEN` is set
- [ ] `K1_METRICS_INTERNAL_ONLY=true` with scrape token set
- [ ] PostgreSQL not exposed on public network (`expose:` not `ports:`)
- [ ] Redis has `requirepass` set (`REDIS_PASSWORD`)
- [ ] Artifact volumes backed up
- [ ] TLS termination in front of all public-facing services
