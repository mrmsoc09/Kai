# Repository Cleanup Plan (Kaison K1)

Objective: produce a lean, user-friendly repo that ships only what is necessary to build and run the FastAPI backend, Celery worker, and React frontend.

## Safe-to-archive buckets
- **Legacy PDFs / slides / market research**: move to `archive/docs/` or remove. Examples: `*_REPORT.md`, `*_SUMMARY.md`, `*_VIS*.pdf`, `*_heatmap*.pdf`, `*_malware*.pdf`, `*_Blackhat*.pdf`.
- **One-off prompts / brainstorming files**: `_inv_*.txt`, `*_prompt*.pdf`, `*_planning*.pdf`.
- **Old completion reports**: `IMPLEMENTATION_COMPLETE.md`, `V7.6_COMPLETION_SUMMARY.md`, `PHASE*_*.md`, etc.
- **VM setup notes and vendor-specific checklists** no longer used by compose: `VMWARE_*.md`, `FIRST_VM_BOOT_CHECKLIST.md` (keep latest in `docs/deploy/` if needed).
- **Cache/log artifacts**: `var/lib/kai/logs/**`, `firebase-debug.log`, old `artifacts/` outputs.

## Keep (ship-ready)
- Source: `apps/backend/**`, `apps/frontend/**`, `apps/orchestrator/**` (if used), `config/`, `docker-compose.dev.yml`, `Dockerfile.dev`, `Dockerfile.worker`.
- Docs: `README.md`, `DEPLOYMENT_GUIDE.md`, `SECURITY.md`, `THREATMODEL.md`, `SYSTEM_ARCHITECTURE.md`, this `docs/CLEANUP_PLAN.md`.
- Config/templates: `env.example`, `pre-commit-config.yaml`, `pyproject.toml`, `requirements*.txt`.

## Steps to execute (non-destructive first)
1) Create `archive/` and move non-essential PDFs/old reports there.
2) Delete build artifacts/logs: `var/lib/kai/**`, `artifacts/**`, `firebase-debug.log`.
3) Remove orphaned helper scripts no longer referenced in docs or compose.
4) Run `git status` to confirm only source/docs remain; commit with `chore: repo cleanup`.

## Optional git hygiene
- Add `.gitignore` entries for `artifacts/`, `var/`, `*.log`, `*.pem`, `archive/` (if not tracked).
- Add `LICENSE` and `CONTRIBUTING.md` if missing.

## Post-cleanup verification
- `docker-compose -f docker-compose.dev.yml up --build --detach backend worker redis postgres`
- Hit `http://localhost:8080/health` (backend) and enqueue a tool via `/api/v1/tasks/enqueue`.
- `npm run lint` in `apps/frontend`.
