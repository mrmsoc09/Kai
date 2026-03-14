# Development Guide

## Prerequisites

- Python 3.11
- PostgreSQL
- Redis
- Optional: Vault for secret-backed paths

## Environment Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-dev.txt
```

## Environment

Common variables:

- `DATABASE_URL` (default in code: `postgresql://k1:k1pass@localhost:5432/k1`)
- `REDIS_URL`
- `K1_TEST_MODE` (`true` in test harness)
- `K1_DEV_TOKEN`
- `JWT_SECRET_KEY`
- `K1_ARTIFACTS_ROOT` (recommended for local/test isolation)
- `K1_TOOL_REGISTRY_PATH` (defaults to `tools/registry/tool_registry.yaml`)
- `K1_SCOPE_POLICY_PATH` (defaults to `config/scope_guardrails.yaml`)

## Backend Startup

### Local Python process

```bash
python3 -m uvicorn apps.backend.src.main:app --host 0.0.0.0 --port 8080 --reload
```

### Worker

```bash
celery -A apps.backend.src.worker.celery_app.celery_app worker -Q tools,intrusive --loglevel=info
```

### Docker Compose (development stack)

```bash
docker-compose -f docker-compose.dev.yml up -d
```

## Database

- SQLAlchemy async session factory: `apps/backend/src/core/hil_db.py`
- Migrations: `apps/backend/alembic/`

Apply migrations with Alembic before running integration flows against a real database.

## Testing

Primary command:

```bash
python3 -m pytest -q
```

Quality checks (same commands used in CI):

```bash
bash scripts/check_backend_quality.sh
```

Focused groups:

```bash
python3 -m pytest -q tests/test_campaign*
python3 -m pytest -q tests/test_reports*
python3 -m pytest -q tests/test_hil*
```

Tool/workflow-specific checks:

```bash
python3 scripts/verify_tool_registry_install.py
python3 scripts/run_bugbounty_workflow.py --template workflow_recon_surface_map --target example.com --dry-run
```

## Development Rules (Current Practice)

- Keep canonical execution state in database models, not in memory-only structures.
- Emit audit events for significant state transitions.
- Propagate intention linkage where available.
- Avoid claiming unsupported behavior (for example, external provider auto-submission).
