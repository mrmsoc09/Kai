# Release: BBP Queue → Plan Runs + Operator UI (validation, sorting, highlight, duplicate-preflight)

Changes:
- Backend: Added duplicate-preflight (6h window) in queue path to block redundant plan runs for same target+chain.
- Frontend: Programs page — validation badges, sorting controls, persist-and-redirect to Runs; Runs page — highlights the newly queued run.
- Safety: Plan-mode only; HiL and scope policies enforced upstream.

Run:
- Backend: uvicorn apps.backend.src.main:app --port 8080
- Frontend: npm run dev (http://localhost:5173), set localStorage USER_TOKEN to 'dev'

