# Kai / K1

## Project Title
Kai (K1) is a backend-first orchestration platform for authorized security research workflows.

## What Kai Is
Kai provides a persisted execution model for campaign-based work:

- campaign and branch orchestration
- phase scheduling with dependency handling
- approval-gated execution paths
- worker result ingestion
- artifact and observation persistence
- deterministic observation-to-finding correlation
- human review and submission package preparation
- provider payload preview/export staging (no auto-submission)

## Key Capabilities

- Canonical execution entities (`CampaignRun`, `ExecutionBranch`, `PhaseJob`, `ToolExecution`, `ApprovalGate`, `Artifact`, `Observation`, `AuditEvent`, `IntentionRecord`)
- Idempotent scheduler and ingestion behavior for replay/concurrency safety
- Branch-local approval blocking semantics
- Review queue and finding review actions
- Diagnostics and health endpoints for operators

## Architecture Overview

- API/control plane: FastAPI (`apps/backend/src/main.py`)
- Persistence: PostgreSQL + SQLAlchemy models + Alembic migrations
- Worker execution: Celery (`apps/backend/src/worker/`)
- Frontend (canonical operator cockpit): Next.js (`apps/frontend-operator/`)
- Canonical docs:
  - [`docs/architecture.md`](docs/architecture.md)
  - [`docs/backend_system.md`](docs/backend_system.md)
  - [`docs/workflow_engine.md`](docs/workflow_engine.md)
  - [`docs/security_model.md`](docs/security_model.md)
  - [`docs/api_reference.md`](docs/api_reference.md)
  - [`docs/development_guide.md`](docs/development_guide.md)
  - [`docs/frontend_readiness.md`](docs/frontend_readiness.md)
  - [`docs/testing_strategy.md`](docs/testing_strategy.md)
  - [`docs/release_process.md`](docs/release_process.md)

## Repository Structure

```text
apps/
  backend/
    src/              # FastAPI app, core services, models, routers, worker integration
    alembic/          # DB migrations
  frontend-operator/  # Canonical Next.js analyst/operator console
  frontend/           # Legacy frontend surface (compatibility)
tests/              # pytest suites
docs/               # canonical documentation set
scripts/            # policy and maintenance checks
```

## Getting Started

1. Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-dev.txt
```

2. Create env file (MVP quickstart):

```bash
cp .env.mvp.example .env
```

3. Set required environment variables (minimum):

- `DATABASE_URL`
- `REDIS_URL`
- `K1_DEV_TOKEN`
- `JWT_SECRET_KEY`

4. Apply database migrations:

```bash
alembic upgrade head
```

5. Start backend API:

```bash
python3 -m uvicorn apps.backend.src.main:app --host 0.0.0.0 --port 8080 --reload
```

6. Start worker (separate shell):

```bash
celery -A apps.backend.src.worker.celery_app.celery_app worker -Q tools,intrusive --loglevel=info
```

Optional local stack:

```bash
docker-compose -f docker-compose.dev.yml up -d
```

Frontend operator (separate shell):

```bash
cd apps/frontend-operator
npm install
npm run dev
```

Canonical MVP walkthrough:

- [`docs/mvp_quickstart.md`](docs/mvp_quickstart.md)
- `bash scripts/frontend_smoke.sh`
- `bash scripts/mvp_demo_flow.sh`

## Testing

Full suite:

```bash
python3 -m pytest -q
```

Backend quality checks (matches CI):

```bash
bash scripts/check_backend_quality.sh
```

Focused suites:

```bash
python3 -m pytest -q tests/test_campaign*
python3 -m pytest -q tests/test_reports*
python3 -m pytest -q tests/test_hil*
```

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup, coding standards, and PR guidance.
