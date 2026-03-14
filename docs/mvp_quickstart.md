# Kai MVP Quickstart

This is the canonical path for a **testable local MVP**.

## 1. Install and configure

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt -r requirements-dev.txt
cp .env.mvp.example .env
```

Minimum required env values in `.env`:

- `DATABASE_URL`
- `REDIS_URL`
- `K1_DEV_TOKEN`
- `JWT_SECRET_KEY`

## 2. Start dependencies and backend

```bash
docker-compose -f docker-compose.dev.yml up -d postgres redis
python3 -m uvicorn apps.backend.src.main:app --host 0.0.0.0 --port 8080 --reload
```

Optional worker:

```bash
celery -A apps.backend.src.worker.celery_app.celery_app worker -Q tools,intrusive --loglevel=info
```

## 3. Run migrations

```bash
alembic upgrade head
```

## 4. Auth bootstrap

Get a bearer token from dev token:

```bash
curl -sS -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$K1_DEV_TOKEN\"}"
```

Set:

```bash
export K1_API_TOKEN="<access_token>"
```

## 5. Seed deterministic MVP demo data

```bash
python3 scripts/seed_mvp_demo.py --apply --trigger-run --create-case-from-first-alert
```

or full script:

```bash
bash scripts/mvp_demo_flow.sh
```

`scripts/mvp_demo_flow.sh` requires either `K1_API_TOKEN` or `K1_DEV_TOKEN`.

## 6. Start operator cockpit

```bash
cd apps/frontend-operator
cp .env.example .env.local
echo "NEXT_PUBLIC_API_BEARER_TOKEN=${K1_API_TOKEN}" >> .env.local
npm install
npm run dev
```

Open `http://localhost:3000` (or `http://localhost:8081` under docker compose frontend service).

## 7. MVP verification checklist

- Programs page shows seeded program.
- Targets page shows monitored target with readiness/status.
- Opportunities/Predictions/Triage show non-empty or explicit empty states.
- Alerts and Cases surfaces are reachable and populated after sync/seed.
- System page shows scheduler/readiness/tool health.

## 8. Regression checks

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q tests/test_mvp_e2e_integration.py
cd apps/frontend-operator && npm run typecheck && npm test && npm run build
```
