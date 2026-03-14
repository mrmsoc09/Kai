# Configuration

## Core Files

| File | Purpose |
|------|---------|
| `.env.example` | All environment variable defaults — copy to `.env` |
| `tools/registry/tool_registry.yaml` | Tool catalog (binary, timeout, safety class) |
| `ops/toolpacks.yaml` | Toolpack policy overrides |
| `config/scope_guardrails.yaml` | Scope allowlist/denylist/CIDR policy |
| `config/api_keys.example.yaml` | API key template |
| `workflows/definitions/*.yaml` | Workflow stage definitions |

---

## Environment Variable Reference

### Runtime

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Runtime mode. Use `production` to enable stricter checks. |
| `DEBUG_MODE` | `false` | Enable debug output. Never true in production. |
| `LOG_LEVEL` | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `BACKEND_HOST` | `0.0.0.0` | API bind host. |
| `BACKEND_PORT` | `8080` | API listen port. |
| `BACKEND_URL` | `http://localhost:8080` | Public base URL for API. |
| `FRONTEND_URL` | `http://localhost:8081` | Public base URL for frontend. |

### Authentication / JWT

| Variable | Default | Description |
|----------|---------|-------------|
| `K1_JWT_SECRET` | — | JWT signing secret. Use ≥32 random bytes. **Required.** |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm. |
| `K1_ACCESS_TOKEN_EXPIRY_MINUTES` | `60` | Access token TTL. |
| `K1_REFRESH_TOKEN_EXPIRY_DAYS` | `7` | Refresh token TTL. |
| `K1_DEV_TOKEN` | — | Development-only bearer token for test paths. |
| `ADMIN_API_KEY` | — | Legacy admin key (to be replaced by JWT). |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL asyncpg URL: `postgresql+asyncpg://user:pass@host/db`. **Required.** |
| `DATABASE_POOL_SIZE` | `20` | SQLAlchemy pool size. |
| `DATABASE_MAX_OVERFLOW` | `10` | Pool overflow. |
| `DATABASE_POOL_TIMEOUT` | `30` | Pool checkout timeout (seconds). |
| `DATABASE_ECHO` | `false` | Log all SQL (verbose). |

### Redis / Celery

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL for cache and Celery broker. |

### Security Controls

| Variable | Default | Description |
|----------|---------|-------------|
| `K1_FORCE_HTTPS` | `false` | Redirect HTTP → HTTPS. Enable in production. |
| `K1_SECURE_COOKIES` | `false` | Set Secure flag on session cookies. Enable in production. |
| `K1_HSTS_MAX_AGE` | `31536000` | HSTS max-age header in seconds. |
| `K1_RATELIMIT_BACKEND` | `memory` | Rate limit store: `memory` or `redis`. |
| `K1_RATELIMIT_DEFAULT_PER_USER` | `100` | Requests per minute per user. |
| `K1_RATELIMIT_DEFAULT_PER_IP` | `1000` | Requests per minute per IP. |
| `K1_ALLOW_UNSIGNED_CERTIFICATES` | `false` | Allow auth certificates with no signature. **Never enable in production.** |
| `K1_AUTH_CERT_SIGNING_KEY` | — | HMAC-SHA256 key for certificate signature validation. |
| `K1_ALLOW_DEV_VAULT_ROOT` | `false` | Allow Vault dev root token. **Never enable in production.** |
| `K1_TEST_MODE` | `false` | Enable test-mode paths. **Never enable in production.** |
| `K1_RELAX_AUTH_GATES_FOR_TESTS` | `false` | Skip authorization gates in test mode. Requires `K1_TEST_MODE=true`. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:8081` | Comma-separated CORS origins. |

### Vault

| Variable | Default | Description |
|----------|---------|-------------|
| `VAULT_ADDR` | `http://localhost:8200` | Vault server address. |
| `VAULT_TOKEN` | — | Vault root/access token. |
| `VAULT_NAMESPACE` | `k1` | Vault namespace prefix. |

### LLM Providers

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `anthropic` | Primary provider: `anthropic`, `openai`, `gemini`, `ollama`. |
| `ANTHROPIC_API_KEY` | — | Anthropic API key. |
| `OPENAI_API_KEY` | — | OpenAI API key. |
| `GOOGLE_API_KEY` | — | Google/Gemini API key. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama base URL. |
| `OLLAMA_MODEL` | `llama3.1:8b` | Ollama model name. |
| `K1_PATCH_LLM_MODEL` | `claude-opus-4-5` | Model used for patch generation. |
| `K1_VALIDATION_LLM_MODEL` | `claude-3-haiku-20240307` | Model used for validation. |

### External Intelligence APIs

| Variable | Description |
|----------|-------------|
| `SHODAN_API_KEY` | Shodan internet scan API. |
| `CENSYS_API_ID` | Censys certificate search API ID. |
| `CENSYS_API_SECRET` | Censys API secret. |
| `VIRUSTOTAL_API_KEY` | VirusTotal file/URL analysis. |
| `GOOGLE_CSE_API_KEY` | Google Custom Search API key. |
| `GOOGLE_CSE_ID` | Google Custom Search engine ID. |

### Tool Catalog and Scope

| Variable | Default | Description |
|----------|---------|-------------|
| `K1_TOOL_REGISTRY_PATH` | `tools/registry/tool_registry.yaml` | Path to tool catalog YAML. |
| `K1_SCOPE_POLICY_PATH` | `config/scope_guardrails.yaml` | Path to scope guardrails YAML. |
| `K1_WORKFLOW_OUTPUT_ROOT` | `output` | Root directory for workflow plans, reports, and scope audit logs. |
| `K1_ARTIFACTS_ROOT` | `artifacts` | Root directory for tool run outputs, recordings, and dork runs. |
| `K1_TOOLPACKS_ENABLE` | — | Comma-separated tool IDs to force-enable. |
| `K1_TOOLPACKS_DISABLE` | — | Comma-separated tool IDs to force-disable. |
| `K1_TOOLPACKS_PATH` | `ops/toolpacks.yaml` | Toolpack policy file override. |

### Startup Validation

| Variable | Default | Description |
|----------|---------|-------------|
| `K1_STARTUP_VALIDATE_DEPENDENCIES` | `true` | Fail startup if required Python deps are missing. |
| `K1_STARTUP_VALIDATE_SECRETS` | `true` | Fail startup if required secrets are unconfigured. |
| `K1_STARTUP_VALIDATE_TOOLPACKS` | `false` | Fail startup if tool catalog has missing binaries. |

### Scoring and Review Thresholds

| Variable | Default | Description |
|----------|---------|-------------|
| `K1_CONFIDENCE_REVIEW_THRESHOLD` | `0.6` | Findings below this confidence are queued for human review. |
| `K1_CONFIDENCE_SENSITIVE_THRESHOLD` | `0.4` | Findings below this are flagged sensitive. |
| `K1_CONFIDENCE_STOP_THRESHOLD` | `0.2` | Confidence below which automated execution halts. |
| `K1_MIN_REPORT_COMPLIANCE_SCORE` | `70` | Minimum score (0–100) to pass report compliance gate. |

### Submission / Attachment Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `K1_MAX_ATTACHMENT_FILE_BYTES` | `52428800` | Max single attachment size (50 MB). |
| `K1_MAX_ATTACHMENT_TOTAL_BYTES` | `104857600` | Max total attachment size per submission (100 MB). |
| `K1_MAX_RECORDING_ATTACHMENTS` | `10` | Max number of recording files per submission. |

---

## Safe Mode

Workflow start requests default to `safe_mode=true`. In safe mode:

- Tools with `safety_classification: intrusive` or `manual_only` are blocked at planning time.
- Operators must explicitly pass `safe_mode=false` to enable intrusive tool execution.
- Safe mode status is recorded in campaign audit events.

## Scope Guardrails

`config/scope_guardrails.yaml` supports:

| Field | Type | Description |
|-------|------|-------------|
| `allowlist` | list of patterns | Hosts/patterns explicitly in scope. |
| `denylist` | list of patterns | Hosts/patterns explicitly blocked (checked first). |
| `cidr_allowlist` | list of CIDRs | IP ranges allowed as targets. |
| `safe_mode_default` | bool | Default safe-mode for new campaigns. |
| `strict_allowlist` | bool | If `true`, targets not matching allowlist are rejected. |

Pattern formats: exact hostname, `*.example.com` (subdomain wildcard), `/regex/` (regex).

**Default config ships with an empty allowlist and `strict_allowlist: true`**, meaning deny-by-default until explicit scope entries are configured. For local exploratory testing only, operators may set `strict_allowlist: false`.

Scope enforcement for template workflows: `apps/backend/src/core/scope_guardrails.py`
