# KAI Platform — Google Cloud Deployment To-Do List

Target: GKE + Cloud SQL (PostgreSQL) + Cloud Memorystore (Redis) +
        BigQuery + Cloud Storage + Multi-cloud DB IPs + Docker/K8s

Deadline window: < 30 days

---

## PHASE 1 — GCP Project & Foundation  *(Days 1–3)*

### 1.1 GCP Project Setup
- [ ] Create GCP project `kaison-prod` (or confirm existing project ID)
- [ ] Enable required APIs:
  - Kubernetes Engine API
  - Cloud SQL Admin API
  - Cloud Storage API
  - BigQuery API
  - Secret Manager API
  - Artifact Registry API
  - Cloud Monitoring API
  - Cloud Logging API
  - Cloud Build API
  - Certificate Manager API
  - Cloud DNS API
  - Compute Engine API (for static IPs)
- [ ] Create GCP service accounts:
  - `kai-backend-sa` — Cloud SQL, GCS, BigQuery, Secret Manager
  - `kai-worker-sa` — same scopes, used by Celery pods
  - `kai-ci-sa` — Artifact Registry push + GKE deploy only
- [ ] Assign IAM roles to each service account (least-privilege)
- [ ] Reserve static external IP addresses (one per cloud provider you use for DB IPs)
- [ ] Set billing alerts at $500 / $1000 / $2000 monthly thresholds

### 1.2 Networking
- [ ] Create VPC `kai-vpc` with custom subnet `kai-subnet` (e.g. 10.10.0.0/20)
- [ ] Create secondary IP ranges for GKE pod/service CIDRs
- [ ] Create Cloud NAT gateway (so GKE nodes can reach external APIs without public IPs)
- [ ] Configure VPC firewall rules:
  - Allow GKE → Cloud SQL (port 5432) via Private Service Access
  - Allow GKE → Cloud Memorystore (port 6379) via VPC
  - Allow HTTPS ingress (port 443) from load balancer only
  - Block all other inbound to nodes
- [ ] Enable Private Google Access on subnet (for GCS, BigQuery, Secret Manager)

---

## PHASE 2 — Container Infrastructure  *(Days 2–5)*

### 2.1 Artifact Registry
- [ ] Create Artifact Registry repo: `us-central1-docker.pkg.dev/kaison-prod/kai`
- [ ] Push all service images to registry (not Docker Hub):
  - `kai-backend`
  - `kai-worker` (Celery)
  - `kai-beat` (Celery Beat)
  - `kai-frontend`
  - `kai-nuclei`
  - `kai-nmap`
  - `kai-theharvester`
  - `kai-amass`
  - `kai-garak` / `kai-llmguard` / `kai-pyrit` / `kai-promptmap`

### 2.2 Dockerfile Hardening
- [ ] **Dockerfile.backend**: add multi-stage build (builder + runtime slim image)
- [ ] **Dockerfile.backend**: pin base image to digest (`python:3.12-slim@sha256:...`)
- [ ] **Dockerfile.backend**: switch entrypoint from `kai_master.py` to:
  `uvicorn apps.backend.src.main:app --host 0.0.0.0 --port 8080`
- [ ] **Dockerfile.backend**: add `HEALTHCHECK` instruction
- [ ] **Dockerfile.backend**: run as UID 1001 (non-root, non-system numeric UID)
- [ ] Create **Dockerfile.worker** (Celery worker — same image, different CMD)
- [ ] Create **Dockerfile.beat** (Celery Beat scheduler)
- [ ] Create **Dockerfile.frontend** (multi-stage: Node build → nginx:alpine serve)
- [ ] Update `nginx.conf`:
  - Add TLS termination (or handle at Ingress layer)
  - Fix API proxy path to match actual backend port (8080, not 8000)
  - Add security headers (X-Frame-Options, CSP, HSTS, etc.)
  - Add gzip compression
- [ ] Fix `docker-compose.yml`:
  - Upgrade PostgreSQL from 13 → 16
  - Add proper health checks to all services
  - Move all secrets to environment variable files (not inline plaintext)
  - Add Celery worker and beat services
  - Add Vault service with dev/prod mode split

### 2.3 GKE Cluster
- [ ] Create GKE Autopilot cluster `kai-cluster` in region `us-central1`
  (Autopilot preferred — managed nodes, auto-scaling, lower ops burden)
- [ ] OR create Standard cluster with node pools:
  - `kai-system` pool: 2×e2-standard-4 (API + frontend)
  - `kai-workers` pool: 2×e2-standard-8 (Celery workers — CPU-intensive scan tools)
  - `kai-tools` pool: 1×e2-standard-4 (privileged tool containers: nmap, nuclei)
- [ ] Enable Workload Identity on cluster (binds k8s service accounts to GCP SA)
- [ ] Enable Binary Authorization (only signed images from Artifact Registry)
- [ ] Enable Cloud Logging and Cloud Monitoring integration

---

## PHASE 3 — Database & Storage  *(Days 3–7)*

### 3.1 Cloud SQL (PostgreSQL 16)
- [ ] Create Cloud SQL instance `kai-postgres`:
  - PostgreSQL 16
  - Machine: `db-custom-4-16384` (4 vCPU, 16 GB RAM)
  - Storage: 100 GB SSD with auto-grow enabled
  - High Availability: yes (for production)
  - Enable private IP (same VPC as GKE)
  - Disable public IP
- [ ] Create databases: `kai_prod`, `kai_staging`
- [ ] Create DB users with minimal privileges
- [ ] Store Cloud SQL connection name in Secret Manager
- [ ] Add **Cloud SQL Auth Proxy** sidecar to backend/worker Deployments
  (replaces current direct `DATABASE_URL` — proxy handles IAM auth)
- [ ] Write and run all Alembic migrations against Cloud SQL:
  - **Currently 0 migration files exist** — must generate initial migration from all models
  - `alembic revision --autogenerate -m "initial_schema"`
  - Validate generated migration covers all 70+ routers' models
- [ ] Update `DATABASE_URL` format for Cloud SQL Proxy:
  `postgresql+asyncpg://kai_user:PASSWORD@127.0.0.1:5432/kai_prod`
- [ ] Add multi-cloud DB IPs to Cloud SQL authorized networks (or use VPN tunnels)

### 3.2 Cloud Memorystore (Redis)
- [ ] Create Memorystore Redis instance `kai-redis`:
  - Version: 7.x
  - Tier: Standard (HA) for production
  - 4 GB memory
  - Private IP in `kai-vpc`
  - Enable AUTH and in-transit encryption
- [ ] Update `REDIS_URL` env var in all deployments to point to Memorystore IP
- [ ] Update `ScanCacheService` Redis URL to use Memorystore endpoint
- [ ] Update Celery broker/backend URL to Memorystore endpoint

### 3.3 Google Cloud Storage
- [ ] Create GCS buckets:
  - `kai-scan-artifacts` — scan output files, tool results, raw findings
  - `kai-reports` — generated PDF/HTML reports
  - `kai-nuclei-templates` — custom Nuclei templates
  - `kai-models` — fine-tuned model checkpoints (future)
- [ ] Set lifecycle rules: auto-delete `kai-scan-artifacts` objects after 90 days
- [ ] Set IAM: `kai-backend-sa` gets `Storage Object Admin` on `kai-scan-artifacts`
- [ ] Install `google-cloud-storage` in requirements.txt
- [ ] Create `apps/backend/src/core/gcs_storage.py`:
  - `GCSArtifactStore` wrapping current `workflow_output_store.py`
  - Replace local file writes with GCS object writes
  - `upload_artifact(mission_id, path, data)` → `gs://kai-scan-artifacts/missions/{mission_id}/...`
  - `download_artifact(mission_id, path)` → stream from GCS
  - Keep local-disk fallback for dev mode
- [ ] Update `run_store.py` to write to GCS in production
- [ ] Update `workflow_output_store.py` to write to GCS in production
- [ ] Update report generation endpoints to serve from signed GCS URLs
- [ ] Configure CORS on GCS buckets (allow frontend domain)

### 3.4 BigQuery
- [ ] Create BigQuery dataset `kai_analytics`:
  - `scan_events` table — every scan start/end with metadata
  - `findings` table — all findings with CVSS, severity, tool, target domain
  - `tool_executions` table — per-tool run times, success/fail, output size
  - `mission_metrics` table — mission-level aggregates (duration, finding count, phase breakdown)
  - `llm_usage` table — model, tokens, cost_usd, task_type per LLM call
- [ ] Install `google-cloud-bigquery` in requirements.txt
- [ ] Create `apps/backend/src/core/bigquery_exporter.py`:
  - `BigQueryExporter` class with async batch insert (`insert_rows_json`)
  - `record_scan_event(mission_id, program_id, event_type, metadata)`
  - `record_finding(finding_id, severity, cvss, tool, target, mission_id)`
  - `record_tool_execution(tool_name, phase, duration_ms, success, scan_id)`
  - `record_llm_usage(model, input_tokens, output_tokens, cost_usd, task_type)`
  - Buffer writes (flush every 30s or 100 rows) — never on hot path
- [ ] Wire `BigQueryExporter` into:
  - `praison_mission_runtime.py` — on mission start/complete events
  - `GeminiOrchestrator.execute()` — after each LLM call
  - Tool agent base class — on tool run complete
- [ ] Create BigQuery views for the frontend Analytics page (`/reports`)
- [ ] Add Data Studio / Looker Studio dashboard connected to `kai_analytics`

---

## PHASE 4 — Kubernetes Manifests  *(Days 5–10)*

### 4.1 Directory Structure
- [ ] Create `/k8s/` directory with:
  ```
  k8s/
    base/
      namespace.yaml
      backend/deployment.yaml, service.yaml, hpa.yaml
      worker/deployment.yaml, hpa.yaml
      beat/deployment.yaml
      frontend/deployment.yaml, service.yaml
      ingress.yaml
      configmap.yaml
      secrets/          (sealed-secrets or external-secrets-operator)
    overlays/
      staging/
      production/
  ```

### 4.2 Core Manifests
- [ ] `namespace.yaml` — namespace `kai` with resource quotas
- [ ] `configmap.yaml` — all non-secret environment variables
- [ ] **Backend Deployment**:
  - 2 replicas minimum, HPA min=2 max=8 on CPU 60%
  - Cloud SQL Auth Proxy sidecar container
  - Liveness probe: `GET /health`
  - Readiness probe: `GET /ready`
  - Resource requests/limits (e.g. 500m CPU, 512Mi memory)
  - Workload Identity annotation
  - SecurityContext: `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`
- [ ] **Celery Worker Deployment**:
  - 2 replicas minimum, HPA on Celery queue depth (KEDA)
  - Same Cloud SQL Auth Proxy sidecar
  - Higher memory limit (scan tools are memory-intensive)
- [ ] **Celery Beat Deployment**:
  - 1 replica only (must be singleton)
  - `strategy: Recreate` (never run two beat instances)
- [ ] **Frontend Deployment**:
  - 2 replicas, HPA on CPU
  - Nginx serving static files + proxying to backend
- [ ] **Tool Pod Deployments** (nmap, nuclei, etc.):
  - Isolated namespace `kai-tools`
  - Network policy: only allow egress to target IPs within approved scope
  - `securityContext.capabilities.add: [NET_RAW]` for nmap only
  - No internet egress from tool pods except scan targets

### 4.3 Ingress & TLS
- [ ] Install GKE Ingress controller (or use GKE built-in HTTP(S) Load Balancer)
- [ ] `ingress.yaml`:
  - TLS termination using Google-managed certificate
  - Route `/api/*` → backend service
  - Route `/*` → frontend service
  - Add Cloud Armor policy for WAF/DDoS protection
- [ ] Configure Cloud DNS: point domain to GKE Ingress external IP
- [ ] Set up Google-managed SSL certificate for domain
- [ ] Configure `ALLOWED_ORIGINS` in CORS settings to production domain

### 4.4 Secrets Management
- [ ] Install External Secrets Operator (ESO) in cluster
- [ ] Create SecretStore resource pointing to GCP Secret Manager
- [ ] Migrate all secrets from HashiCorp Vault (dev) to GCP Secret Manager (prod):
  - `DATABASE_URL`
  - `REDIS_URL` / `REDIS_PASSWORD`
  - `JWT_SECRET` (rotate from dev default!)
  - `GOOGLE_API_KEY`
  - `GCP_PROJECT_ID`, `GCP_LOCATION`
  - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
  - All tool API keys: SHODAN, CENSYS, VIRUSTOTAL, NVD, MISP_API_KEY, CORTEX_API_KEY, etc.
  - Wazuh, TheHive, Shuffle credentials
- [ ] Create ExternalSecret resources mapping GCP Secret Manager secrets → k8s Secrets
- [ ] Update `secret_manager.py` to support GCP Secret Manager backend:
  - Add `K1_SECRET_BACKEND=gcp` option
  - Add `GCPSecretProvider` class using `google-cloud-secret-manager`
  - Keep Vault backend as option for self-hosted deployments
- [ ] Rotate the `jwt_secret` from `"dev-secret-change-in-production"` default

### 4.5 KEDA (Kubernetes Event-Driven Autoscaling)
- [ ] Install KEDA in cluster
- [ ] Create ScaledObject for Celery worker — scale on Redis list length (`celery` queue)
- [ ] Create ScaledObject for report-generation worker — scale on dedicated queue depth

---

## PHASE 5 — CI/CD Pipeline  *(Days 7–12)*

### 5.1 GitHub Actions Workflows
- [ ] Create `.github/workflows/ci.yml`:
  - Trigger: PR to main
  - Steps: Python lint (ruff), type check (mypy), test suite (`pytest tests/ -q`)
  - Build Docker images (no push on PR)
  - Security scan: `trivy image` on built images
  - Dependabot alerts: address the 53 current GitHub security vulnerabilities
- [ ] Create `.github/workflows/deploy-staging.yml`:
  - Trigger: merge to `main`
  - Build and push images to Artifact Registry with `git sha` tag
  - Run Alembic migrations against staging DB
  - `kubectl set image` to update staging deployments
  - Smoke test: hit `/health` and `/ready` endpoints
- [ ] Create `.github/workflows/deploy-production.yml`:
  - Trigger: manual workflow dispatch + version tag push (`v*`)
  - Require approval from 1 reviewer
  - Same steps as staging + production health gate
- [ ] Store GCP service account key as GitHub secret `GCP_SA_KEY`
- [ ] Configure Workload Identity Federation (preferred over SA key)

### 5.2 Image Tagging Strategy
- [ ] Tag images with both `git sha` and semantic version
- [ ] Pin k8s manifests to digest (not `latest`)
- [ ] Set up automatic Dependabot updates for base Docker images

---

## PHASE 6 — Application Code Changes  *(Days 5–15)*

### 6.1 Health & Readiness Endpoints
- [ ] Add `GET /health` endpoint — returns 200 if app is up (no DB check)
- [ ] Add `GET /ready` endpoint — returns 200 only when DB + Redis are reachable
  (Kubernetes readiness probe calls this; failing it removes pod from load balancer)

### 6.2 Configuration / Environment
- [ ] Update `settings.py` to read `DATABASE_URL` from GCP Secret Manager in production
- [ ] Ensure all hardcoded `localhost` addresses use env vars
- [ ] Update CORS `cors_origins` to read from env var `K1_CORS_ORIGINS`
- [ ] Add `TRUSTED_PROXIES` setting (GKE LB injects `X-Forwarded-For`)
- [ ] Add `PORT` env var support (GCP Cloud Run uses `PORT=8080`)

### 6.3 Database / Migrations
- [ ] **Generate initial Alembic migration** (currently 0 migration files):
  ```bash
  alembic revision --autogenerate -m "initial_schema"
  ```
- [ ] Review autogenerated migration — ensure all 70+ router models are covered
- [ ] Add migration runner to deployment pipeline (pre-deploy job)
- [ ] Test rollback path (`alembic downgrade -1`)
- [ ] Add connection retry logic in `database.py` for Cloud SQL cold starts

### 6.4 GCS Artifact Storage
- [ ] `gcs_storage.py` (see Phase 3.3) — abstract file I/O behind GCS client
- [ ] Update all `open()` / file path writes in scan results to use `GCSArtifactStore`
- [ ] Nuclei/nmap tool outputs: write to GCS, not local `/tmp`
- [ ] Replace local `output/` and `artifacts/` directories with GCS paths

### 6.5 BigQuery Integration
- [ ] `bigquery_exporter.py` (see Phase 3.4)
- [ ] Wire into mission runtime + orchestrator + tool agents

### 6.6 Structured Logging
- [ ] Switch all `logging.getLogger` calls to emit structured JSON logs
  (GCP Cloud Logging natively parses JSON logs with `severity`, `message`, `trace`)
- [ ] Add `trace_id` / `span_id` fields from `CorrelationIdMiddleware` to every log line
- [ ] Add GCP trace context (`X-Cloud-Trace-Context` header) propagation

### 6.7 Secret Manager Backend
- [ ] Add `GCPSecretProvider` to `secret_manager.py` (see Phase 4.4)
- [ ] Update `scan_cache.py` ScanCacheService Redis URL to use env var cleanly

### 6.8 Celery / Task Queue
- [ ] Ensure Celery broker URL supports SSL/TLS for Memorystore (add `rediss://` scheme)
- [ ] Add Celery result backend expiry (prevent unbounded Redis growth)
- [ ] Add dead-letter queue for failed scan tasks

### 6.9 Security Hardening for Production
- [ ] Rotate all default/dev secrets (JWT secret, admin passwords, API keys)
- [ ] Ensure `K1_ALLOW_ENV_SECRETS=false` in production (force Vault/Secret Manager)
- [ ] Ensure `K1_RELAX_AUTH_GATES_FOR_TESTS=false` in production (already default)
- [ ] Ensure `K1_ALLOW_UNSIGNED_CERTIFICATES=false` in production (already default)
- [ ] Add rate limiting configuration appropriate for production traffic
- [ ] Address 53 Dependabot security vulnerabilities (run `pip audit` + `npm audit`)
- [ ] Enable Cloud Armor WAF policy on GKE Ingress (OWASP ruleset)

---

## PHASE 7 — Observability  *(Days 10–18)*

### 7.1 Cloud Monitoring
- [ ] Create uptime checks for `https://yourdomain.com/health`
- [ ] Create alerting policies:
  - Backend pod crash-looping (GKE)
  - Database CPU > 80%
  - Redis memory > 80%
  - 5xx error rate > 1% over 5 min
  - Celery queue depth > 100 (scan backlog)
- [ ] Set up notification channels (email, PagerDuty, or Slack)

### 7.2 Cloud Logging
- [ ] Create log-based metrics:
  - `scope_violation_count` — from `scope_decisions.jsonl` entries
  - `band2_approval_requests` — from approval gate logs
  - `llm_error_rate` — from LLM provider error logs
- [ ] Create log router sink: forward `kai-scan-artifacts` bucket access logs to BigQuery
- [ ] Create log-based alert: any `CRITICAL` log line pages on-call

### 7.3 Distributed Tracing
- [ ] Enable Cloud Trace
- [ ] Add OpenTelemetry instrumentation to FastAPI app
- [ ] Propagate trace context through Celery tasks

---

## PHASE 8 — Multi-Cloud DB IPs  *(Days 12–20)*

*For compliance, resilience, or regulatory reasons the user wants DB endpoints
across multiple cloud providers.*

### 8.1 Per-Cloud Setup
- [ ] **AWS RDS (PostgreSQL 16)** in `us-east-1`:
  - Private subnet, Multi-AZ
  - VPN or AWS PrivateLink to GCP VPC
  - Store connection string in GCP Secret Manager
- [ ] **Azure Database for PostgreSQL** (flexible server):
  - Private endpoint
  - VPN tunnel or ExpressRoute to GCP VPC
  - Store connection string in GCP Secret Manager
- [ ] Assign purchased static IPs to each cloud DB endpoint
- [ ] Add IPs to Cloud SQL authorized networks (if fallback reads are needed)

### 8.2 Application Layer
- [ ] Create `apps/backend/src/core/db_router.py`:
  - `MultiCloudDatabaseRouter` — primary Cloud SQL, read replicas on AWS/Azure
  - Health-check loop; promote next replica if primary unreachable
  - `K1_DB_ROUTER_MODE` env: `single` (default), `read_replica`, `multi_primary`
- [ ] Update `database.py` to use `MultiCloudDatabaseRouter` in production
- [ ] Test failover: take down Cloud SQL, verify traffic routes to replica

---

## PHASE 9 — Staging Environment  *(Days 14–22)*

- [ ] Mirror production GKE namespace as `kai-staging` namespace
- [ ] Create staging Cloud SQL instance (smaller: `db-g1-small`)
- [ ] Create staging Memorystore instance (1 GB basic tier)
- [ ] Create staging GCS buckets (`kai-scan-artifacts-staging`, etc.)
- [ ] Create staging BigQuery dataset `kai_analytics_staging`
- [ ] Configure staging ingress on subdomain: `staging.yourdomain.com`
- [ ] All deploys from `main` branch go to staging automatically
- [ ] Production deploys require manual approval after staging validation

---

## PHASE 10 — Pre-Launch Checklist  *(Days 20–28)*

### 10.1 Load Testing
- [ ] Run `k6` or `locust` load test against staging:
  - 50 concurrent users, 10-minute ramp
  - Target: p99 API latency < 500ms
  - Target: 0 errors on `/api/v1/hunt` submit endpoint
- [ ] Verify HPA scales workers appropriately under scan load
- [ ] Verify BigQuery ingest handles burst write load

### 10.2 Security Review
- [ ] Run `trivy` against all container images — fix HIGH/CRITICAL CVEs
- [ ] Run `kube-bench` CIS Kubernetes benchmark against GKE cluster
- [ ] Verify Binary Authorization blocks unsigned images
- [ ] Pen-test the login + CSRF flow against production domain
- [ ] Verify all scope guardrail enforcement works end-to-end
- [ ] Verify Band 2 approval gates function over HTTPS

### 10.3 Backup & Recovery
- [ ] Enable automated Cloud SQL backups (daily, 7-day retention)
- [ ] Enable GCS versioning on `kai-scan-artifacts`
- [ ] Test database restore from backup
- [ ] Document RTO (Recovery Time Objective) and RPO targets

### 10.4 Cost Optimisation
- [ ] Set GKE cluster to use Spot VMs for `kai-workers` node pool (60-80% cheaper)
- [ ] Set BigQuery table expiry for raw events older than 1 year
- [ ] Enable committed use discounts for Cloud SQL (1-year CUD)
- [ ] Enable GCS Nearline storage class for objects older than 30 days

### 10.5 Documentation
- [ ] Write ops runbook: deploy, rollback, database migration
- [ ] Write incident response guide for production alerts
- [ ] Document all GCP Secret Manager secret names and rotation schedule
- [ ] Update CLAUDE.md with production service URLs and k8s context names

---

## Summary — Critical Path Items (Must Ship Before Launch)

| # | Item | Blocks |
|---|------|--------|
| 1 | Generate Alembic initial migration | Database schema in Cloud SQL |
| 2 | Cloud SQL instance + Auth Proxy sidecar | All backend pods |
| 3 | GCP Secret Manager + rotate JWT secret | Production security |
| 4 | K8s manifests (Deployment, Service, Ingress) | Any GKE deployment |
| 5 | CI/CD GitHub Actions (build → push → deploy) | Repeatable deploys |
| 6 | GCS artifact store (`gcs_storage.py`) | Scan output persistence |
| 7 | `/health` and `/ready` endpoints | GKE liveness/readiness probes |
| 8 | Fix Dockerfile.backend (proper entrypoint + healthcheck) | Image builds |
| 9 | BigQuery exporter + dataset | Analytics/reporting in production |
| 10 | Address 53 Dependabot security vulnerabilities | GitHub security compliance |

---

*Last updated: 2026-05-07*
