# Deployment Guide

> Production deployment, configuration, and operations for the Kai platform.

---

## 1. Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Linux (Ubuntu 22.04+) | — | Windows: WSL2 |
| Python | 3.11+ | `python3 --version` |
| Node.js | 18+ | `node --version` — required for operator UI |
| Docker Engine | 24+ | Docker Desktop acceptable for local |
| docker compose | v2 (plugin) | `docker compose` not `docker-compose` |
| RAM | 4 GB (local) / 8 GB (prod) | Backend + worker + DB |
| Disk | 10 GB | For artifacts, DB, images |
| LLM API key | — | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` required |

On Ubuntu/Debian, `./bootstrap.sh` installs system packages (pango/cairo for weasyprint, curl, git, build-essential) and all Python/Node dependencies automatically.

---

## 2. Quick Start (Local Development)

```bash
# First time
./bootstrap.sh
./k1-start

# Subsequent runs
./k1-start

# Stop stack
./k1-stop
```

Alternative (containerized full stack):

```bash
./scripts/deploy-local.sh
./scripts/deploy-local.sh --down
```

Persistent runtime data, logs, and Docker-backed service state are stored on the external SSD under `/srv/kai`. Initialize it once with `./scripts/init_kai_artifacts.sh` if the startup scripts have not already done so.

Services after startup:
- Backend API: `http://localhost:8080`
- Frontend UI: `http://localhost:8081`
- API Docs (Swagger): `http://localhost:8080/docs`
- Prometheus metrics: `http://localhost:8080/metrics`

---

## 3. Environment Configuration

### 3.1 Required Variables

Copy `.env.example` to `.env` (local) or `.env.prod` (production):

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET_KEY` | **Yes** | Min 32-char random string. `openssl rand -hex 32` |
| `K1_DEV_TOKEN` | Dev only | Dev operator token. Remove in production. |
| `POSTGRES_PASSWORD` | **Yes** | Database password |
| `REDIS_PASSWORD` | Recommended | Redis AUTH password |
| `CORS_ALLOWED_ORIGINS` | **Yes (prod)** | Comma-separated allowed origins |
| `ANTHROPIC_API_KEY` | Conditional | Required if using Anthropic provider |
| `OPENAI_API_KEY` | Conditional | Required if using OpenAI provider |
| `LANGSMITH_API_KEY` | Optional | Enables LangSmith observability |
| `K1_METRICS_SCRAPE_TOKEN` | Recommended | Bearer token for Prometheus scrape |

### 3.2 LLM Provider Configuration

```bash
K1_PRIMARY_LLM_PROVIDER=anthropic
K1_FALLBACK_LLM_PROVIDERS=openai,gemini,ollama
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OLLAMA_HOST=http://localhost:11434
```

### 3.3 Secrets Backend

By default, secrets are loaded from environment variables. For production, use Vault:

```bash
K1_SECRET_BACKEND=vault
K1_VAULT_HOST_BIND=127.0.0.1
K1_VAULT_HOST_PORT=8200
VAULT_ADDR=http://localhost:8200
VAULT_TOKEN=<vault-token>
VAULT_MOUNT_POINT=secret
VAULT_SECRET_PREFIX=kai
```

See [secrets-architecture.md](security-architecture.md) for details.

---

## 4. Production Deployment

### 4.1 Create Production Env File

```bash
cat > .env.prod << 'EOF'
POSTGRES_PASSWORD=$(openssl rand -hex 24)
REDIS_PASSWORD=$(openssl rand -hex 16)
JWT_SECRET_KEY=$(openssl rand -hex 32)
CORS_ALLOWED_ORIGINS=https://your-domain.com
ANTHROPIC_API_KEY=sk-ant-...
LOG_LEVEL=INFO
ENVIRONMENT=production
EOF
```

### 4.2 Deploy

```bash
./scripts/deploy-prod.sh
```

This will:
1. Validate required env vars
2. Check JWT secret length (≥ 32 chars)
3. Build production images (from `Dockerfile.prod`)
4. Start all services
5. Wait for backend health check

### 4.3 Services Architecture

```
                    ┌──────────┐
                    │  nginx   │ :443 (TLS termination — add your own)
                    └────┬─────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
    ┌─────▼──────┐              ┌───────▼──────┐
    │  backend   │ :8080        │  frontend    │ :8081
    │ (FastAPI)  │              │  (nginx/SPA) │
    └─────┬──────┘              └──────────────┘
          │
    ┌─────┴──────┬──────────────┐
    │            │              │
┌───▼───┐  ┌────▼────┐  ┌──────▼─────┐
│ redis │  │postgres │  │  worker    │
│ :6379 │  │  :5432  │  │ (Celery)   │
└───────┘  └─────────┘  └────────────┘
```

### 4.4 TLS / Reverse Proxy

The production compose does NOT include a TLS terminator — add nginx or Caddy in front:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate     /etc/ssl/certs/kai.crt;
    ssl_certificate_key /etc/ssl/private/kai.key;

    location /api/ {
        proxy_pass http://backend:8080/;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
    }

    location / {
        proxy_pass http://frontend:8081/;
    }
}
```

Configure `K1_TRUSTED_PROXY_CIDRS` to include your reverse proxy's IP so that `X-Forwarded-For` is trusted for rate limiting.

---

## 5. Observability Stack

### 5.1 Start Prometheus + Grafana

```bash
# Overlay monitoring compose on top of dev stack
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

# Or with production
docker compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml up -d
```

Access:
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (default: admin/admin)

### 5.2 Available Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `kai_missions_total` | Counter | Missions created (by tenant, mode) |
| `kai_missions_active` | Gauge | Currently running missions |
| `kai_mission_duration_seconds` | Histogram | Mission duration |
| `kai_tool_executions_total` | Counter | Tool executions (by tool, status) |
| `kai_llm_tokens_total` | Counter | LLM tokens (by provider, type) |
| `kai_api_requests_total` | Counter | HTTP requests (by method, path, status) |
| `kai_api_duration_seconds` | Histogram | Request duration |
| `kai_worker_queue_depth` | Gauge | Celery queue depth |
| `kai_errors_total` | Counter | Errors by type |
| `kai_approvals_pending` | Gauge | Pending HIL approvals |

### 5.3 Metrics Security

```bash
# Restrict /metrics to Prometheus scraper only
K1_METRICS_INTERNAL_ONLY=true
K1_METRICS_SCRAPE_TOKEN=$(openssl rand -hex 16)
```

Configure Prometheus with:
```yaml
authorization:
  credentials: "${K1_METRICS_SCRAPE_TOKEN}"
```

---

## 6. Database Migrations

```bash
# Run inside backend container
docker compose exec backend alembic upgrade heads

# Or directly
alembic -c apps/backend/alembic.ini upgrade heads
```

---

## 7. Health Checks

```bash
# Backend liveness
curl http://localhost:8080/health

# System status (authenticated)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/system/status

# Metrics (Prometheus)
curl http://localhost:8080/metrics
```

---

## 8. Log Management

Logs are written to:
- Container stdout: captured by Docker json-file driver (50 MB max, 5 files)
- Audit log: `artifacts/audit/audit.jsonl` — append-only, tamper-evident
- Usage log: `artifacts/usage/usage.jsonl` — billing data
- Tool runs: `artifacts/telemetry/tool_runs.jsonl`
- Mission events: `artifacts/telemetry/mission_events.jsonl`

To ship logs to an external system:
- Mount artifact volumes to a log shipper (Filebeat, Vector)
- Or configure the container driver to send to syslog/fluentd
- For read-only tool container output mounts and retention policy automation, see `docs/artifact-storage.md`.

---

## 9. Backup

```bash
# Database backup (runs on schedule via scripts/db-backup.sh)
docker compose exec postgres pg_dump -U k1 k1 | gzip > backup_$(date +%Y%m%d).sql.gz

# Artifact backup
tar -czf artifacts_$(date +%Y%m%d).tar.gz artifacts/
```

---

## 10. Scaling

The platform is horizontally scalable for workers:

```bash
# Scale Celery workers
docker compose -f docker-compose.prod.yml up -d --scale worker=3
```

Backend API instances can be scaled behind a load balancer when using PostgreSQL checkpointer (shared state via DB).

---

## 11. Troubleshooting

| Symptom | Action |
|---------|--------|
| Backend fails to start | Check `docker compose logs backend`. Verify `DATABASE_URL` and `JWT_SECRET_KEY`. |
| Auth 401 on all requests | Verify `JWT_SECRET_KEY` matches between backend restarts. |
| Worker not processing tasks | Check `docker compose logs worker`. Verify `REDIS_URL`. |
| Vault credential errors | Ensure Vault is unsealed. Check `secret/tools/{tool_id}`. |
| High memory usage | Check Celery worker count. Limit with `--concurrency 2`. |
| Metrics endpoint 403 | Check `K1_METRICS_SCRAPE_TOKEN` configuration. |
