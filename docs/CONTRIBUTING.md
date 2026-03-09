
# Contributing to K1

## Separation of Concerns
- Kaison Composer (builder): development orchestrator, code generation and automation. Not deployed with K1.
- K1 (product): FastAPI backend + React frontend. Operates under HiL, policy gates, and token auth. External actions disabled by default.

## Principles
- Visual-first, dark, calm; no neon or pure whites.
- Evidence-first; logs are structured and redacted.
- Tablet-first layouts; minimal motion; respect prefers-reduced-motion.

## Code Layout
- apps/backend/src: FastAPI app, routers, schemas, auth, logs.
- apps/frontend/src: React/Vite/TS; routes per feature; shared theme tokens.
- artifacts/: logs, evidence, graph snapshots.
- configs/: policies and API keys (never commit real secrets).

## Development
1. `export K1_DEV_TOKEN=...`
2. Start backend (uvicorn) and frontend (npm).
3. Use plan-mode and sample data for UI; do not enable execute without approvals and keys.

## Review Checklist
- Color discipline: no `white/#fff/rgb(255,255,255)`.
- Responsiveness at ~800–1024px widths.
- No raw chain-of-thought in any logs.
- Accessibility: ARIA labels on canvases/lists; reduced motion honored.
