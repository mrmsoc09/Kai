
# K1 Finalization Summary

This document captures the stabilization state for K1 (Kaison One), aligning with the dark, calm, enterprise-safe UI doctrine and HiL execution model.

## Deliverables
- Frontend: Dashboard, Operations, Arsenal (attack graph), Intelligence Database, MCP Registry, Persona Market, Logs.
- Backend API: Auth, state, dorks (plan-mode by default with HiL gates), intelligence (/intel), MCP (/mcp), personas (/personas), logs (/logs), graph (/graph), metrics/knowledge.
- Documentation: This file and CONTRIBUTING.md outline architecture, guardrails, and development flow.
- Separation: Kaison Composer (builder) is distinct from K1 (product). K1 runs with env tokens and strict policies; Kaison Composer remains a development orchestrator.

## Visual & Accessibility Compliance
- Dark-first, no pure white; muted semantic accents only.
- Tablet-first responsive layouts; minimal purposeful motion.
- prefers-reduced-motion honored (Arsenal animation disabled when requested).
- Structured, readable UI; color conveys state; labels kept minimal to avoid clutter.

## MVP Scope Complete
- HiL plan-mode with autonomy tiers and approval gating.
- Evidence-first validation model (immutable finalized evidence, findings gate).
- Intelligence ledger with filters; MCP intent registry; Persona maturity view; Reasoning & Learning logs (structured, redacted).
- Attack graph visualization with spider-web metaphor and tablet interaction.

## Optional Next (post-MVP)
- Run selector and pagination in Logs; export utilities.
- Live graph back-end enrichment and stage-sensitive coloring.
- Enable execute-mode dorking with Google CSE keys + explicit approvals.
- Full accessibility audit (WCAG), tests, and contrast tooling.

## How to Run
- Backend: `export K1_DEV_TOKEN=dev-token-change-me && uvicorn apps.backend.src.main:app --host 0.0.0.0 --port 8000 --reload`
- Frontend: `cd apps/frontend && npm install && npm run dev`
- Tablet verification: open /dashboard, /operations, /arsenal, /intelligence, /mcp, /persona, /logs
