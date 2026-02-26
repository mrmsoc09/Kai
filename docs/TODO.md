K1 Build — Running TODO Tracker

- [x] Add TheHive first-run bootstrap guide (API key generation) and wire into backend config docs.
- [ ] Validate backend container connectivity to postgres/thehive in compose on a docker host. (pending on docker host)
- [ ] Confirm pgvector schema applied (verify tables and vector index creation).
- [ ] Implement provider key intake endpoints end-to-end with Vault (dev token) in container.
- [ ] E2E HiL gate flow via containers: create finding → add evidence → request/approve → submit (TheHive). (scripted in smoke; verify on docker host)
- [x] Frontend: add basic GUI to drive HiL flow and provider registry management. (DONE — minimal stubs)
- [ ] CI: enable action to run compose smoke on push and upload logs.
- [ ] Security hardening pass for images (non-root, pinned tags, healthchecks).
- [ ] Observability: expose metrics, integrate OpenTelemetry to Jaeger.
- [ ] RAG: confirm pgvector embedding write/read path and fallback to Qdrant.

Enhancement Backlog
- [ ] Add scope policy editor UI with presets per BBP program.
- [ ] Dashboard of findings with evidence integrity (Merkle tree) visualization.
- [ ] Persona switcher UI (include new hacker persona) and session logs.
- [ ] API rate limiting, authZ roles (admin/reviewer/runner) across endpoints.
- [ ] Automated API key rotation scheduler with Vault leases and quotas.

## 2026-01-30 — Hub v1 hardening
- [x] Agent Zero Wizard (HiL chat) wired to /agent0/chat with audit logs
- [x] Agent Zero Comms panel rendering rolling logs
- [x] Docs portal serving Markdown from k1/docs
- [x] Dashboard health/state patched; visuals (heatmap/scanlines)
- [x] Backend auth: gate /agent0/* and /docs/* with ROLE_OPERATOR via Bearer token
- [x] Frontend: attach Authorization header from localStorage (k1_token|K1_DEV_TOKEN)
- [ ] Replace dashboard placeholders with real metrics (findings over time, rates, severities)
- [ ] Connect Wizard quick-actions to HiL workflows (findings/evidence → TheHive staging)
- [ ] E2E docker run on docker-capable host and TheHive bootstrap
- [ ] RBAC UI: user role indicator and token config panel

- [x] Hub docs added: HUB_OVERVIEW.md, OPERATOR_QUICKSTART.md
- [x] Recording API (start/stop/list) + frontend page
- [x] Report formats registry + builder + HiL finalize gate (mitigation + recording required)
- [x] Chain builder (lower→critical linkage) + UI
- [x] Mailer preview/send endpoints (send blocked by policy by default)
- [ ] Integrate real recorder sidecar (ffmpeg + Xvfb) and link to /recordings API
- [ ] Duplicate check connectors (TheHive/VRP portals) under policy & HiL
- [ ] Email templates per stakeholder and auto-format validation rules
- [ ] Kubernetes Helm chart for all services + PVCs for artifacts
- [ ] Add real DeepAgents/LLM integration for planner (LangGraph/Haystack optional extras)
- [ ] Implement TheHive live integration paths (no mocks) with config and secure tokens
- [ ] Wire pgvector persistence for findings/embeddings; add migrations
- [ ] Replace placeholder recorder with ffmpeg/browser capture in production
- [ ] Build GUI pages for Planner and Chains with live visualizations
- [ ] Add stakeholder-specific checklists and multipliers (Google VRP) into packaging


## 2026-01-30 13:51:17Z – Status Update (K1 Autonomous)

- Backend test suite: 11/11 PASSED
- Evidence: see pytest log artifact at /a0/tmp/chats/opK97zzU/messages/216.txt
- Environment constraint: Docker not available on this runner → full compose+TheHive E2E deferred to docker-capable host
- Safety: Refused offensive T1562.001 (disable defenses) implementation. Will deliver defensive-only detection/training blueprints with strict HiL gates.

Next Actions (Prioritized)
1) Frontend (Operator UX)
   - Wire Approve → Finalize → Submit HiL → Package → Dispatch in UI
   - Add Outbox viewer and artifact download; show Merkle audit trail
   - Live logs panel: decision_trace.jsonl stream; color semantics
2) Vector Store Integration
   - Feature-flag pgvector (when Postgres available); fallback to embeddings.jsonl
   - Implement /vector/upsert, /vector/search admin endpoints; dedupe signals in UI
3) Secrets & Governance
   - Vault-backed SMTP/api keys; redact logs; rotate test creds
   - Enforce scope policy gates across dorks/plans; expand SCOPE_ENFORCEMENT.md
4) Model Provider Config
   - Replace invalid 'gpt-2.5' with user-approved models (gemini/gemini-2.0-flash-exp or claude-3-5-sonnet-20241022)
   - Add env-driven model routing + health checks
5) CI & Smoke
   - Ensure GitHub Actions job uses docker runner; run compose.dev + smoke_e2e.sh
6) VRP Programs & Revenue Tracks
   - Enrich /programs with importers and multiplier hints
   - Package sample stakeholder-compliant reports; add IaaS lead funnel in UI
7) TheHive Connector
   - Config toggle for live TheHive; verify create case/observables when host available

Follow-ups
- Convert utcnow() usages to timezone-aware UTC
- Add retention job for logs/artifacts; finalize RECORDING_POLICY.md



## Running TODO (Auto-updated)
- [x] Add /state/config with provider/model diagnostics and vector info
- [x] Implement safe MITRE-based Planner with strict HiL gating (no execution)
- [x] Planner API + tests (plan, execute -> denied)
- [ ] Frontend: expose /state/config in Settings and Dashboard health
- [ ] Frontend: add Planner UI (technique selector, plan preview, HiL request button)
- [ ] Backend: enrich planner with program-aware templates (non-destructive)
- [ ] Docs: Planner usage and safety policy


- [x] Frontend: Settings page shows /state/config (providers/vector/policy)
- [x] Frontend: Planner page for safe plan-mode (HiL gate, execution disabled)
- [ ] Frontend: Hook SOC HUD indicators to /state/global and /state/agents
- [ ] E2E UI smoke: Validate Planner Plan, Settings load under dev token
- Implemented offline vector embeddings (hashed) and triage scoring service; built embeddings from NVD recent or stub and produced triage demo.
