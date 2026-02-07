# Kaison K1
Autonomous OSINT & Vulnerability Hunting with FastAPI + Celery + React.

## Run it
```bash
docker-compose -f docker-compose.dev.yml up --build backend worker redis postgres
# Frontend (in another shell)
cd apps/frontend && npm install && npm run dev -- --host
```

## Key capabilities
- Recon/Vuln tool adapters (amass, subfinder, naabu, httpx, nuclei, ffuf, shodan, theHarvester, trufflehog, exiftool) via Celery queue `tools`.
- FastAPI REST: `/api/v1/tasks/enqueue` to run tools, `/api/v1/tasks/{id}` to poll results; artifacts saved under `artifacts/`.
- Modular tool registry with autonomy tiers and approval hooks.
- Worker image (`Dockerfile.worker`) ships the core binaries; backend image is framework-only.

## Quick API example
```bash
curl -X POST http://localhost:8080/api/v1/tasks/enqueue \
  -H 'Content-Type: application/json' \
  -d '{"tool_id":"httpx_probe","params":{"target":"https://example.com"}}'
```

## Cleanup
See `docs/CLEANUP_PLAN.md` for what to archive/remove.

