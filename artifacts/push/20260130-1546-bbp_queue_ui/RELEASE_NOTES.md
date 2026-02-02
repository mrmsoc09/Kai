# Release: BBP Queue → Plan Runs + Operator UI (validation, sorting, last-run highlight) + Duplicate-Preflight

- Backend: /programs/bbp/queue now performs a 6h duplicate-preflight (target+chain) before enqueue.
- Frontend: Programs adds validation badges, sorting controls, and auto-redirects to Runs; Runs highlights the newest run via LAST_RUN_ID.
- Safety: Plan-mode only; HiL and scope policies enforced.

Run:
- Backend: uvicorn apps.backend.src.main:app --port 8080
- Frontend: npm run dev (http://localhost:5173), then set USER_TOKEN='dev' in localStorage
