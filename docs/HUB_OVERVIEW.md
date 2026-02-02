# K1 Display Hub — Operator Overview

This is the SOC-style hub for the K1 vulnerability hunting platform with mandatory Human-in-the-Loop (HiL) controls. All external communications are relayed via Agent Zero.

Core areas:
- Agent Zero Wizard (HiL chat): Human approval, guidance, and controlled comms relay
- Agent Zero Comms Panel: Auditable logs of HiL chat events
- Docs Hub: Operational manuals, runbooks, policies
- Recon Planner: Plan-only dork chain generation (execute requires HiL + policy)
- Attack Graph: Knowledge graph snapshot (nodes/edges) and upcoming force-graph
- Dashboard: Health/state, heatmap, and KPIs (live metrics wiring next)
- Settings: API base and token management (Authorization Bearer)

Security & Governance:
- RBAC: /agent0/*, /docs/*, /dorks/* require ROLE_OPERATOR (Bearer token)
- HiL: Execute-mode OSINT and all outbound comms are gated through Agent Zero
- Audit: Chat logs persisted to k1/artifacts/logs/ (Merkle-ready bundle planned)

Environment:
- Backend (FastAPI) at :8080; Frontend (Vite) at :5173
- Config: K1_DEV_TOKEN for backend auth; VITE_API_BASE for frontend API base

