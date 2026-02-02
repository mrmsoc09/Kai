# Operator Quickstart — K1 Hub

1) Start services locally (no Docker):

Backend
```
cd k1/apps/backend
export K1_DEV_TOKEN=devtoken123
# optional HiL relay target (Agent Zero A2A endpoint)
export AGENT_ZERO_CHAT_URL="http://<agent-zero-host>/agent0/a2a-chat"
uvicorn src.main:app --host 0.0.0.0 --port 8080
```

Frontend
```
cd k1/apps/frontend
npm install
VITE_API_BASE=http://localhost:8080 npm run dev
```

2) In Settings, set API Base and Bearer token (devtoken123), which is attached to all protected endpoints.

3) Workflows
- Wizard: Ask Agent Zero to stage a recon plan. Messages are logged to Agent Zero Comms.
- Docs: Read HIL Gate Spec, Scope Enforcement, Vector Memory, and TheHive Bootstrap.
- Recon Planner: Select a dork chain and run in plan-mode. Execute-mode is blocked pending HiL approval + policy toggle.
- Attack Graph: Inspect current knowledge graph counts and nodes list. Visualization canvas is reserved for the next iteration.
- Dashboard: Health chips reflect backend /health and /state; heatmap and KPI canvases are placeholders pending live metrics wiring.

4) Security
- /agent0/*, /docs/*, /dorks/* require ROLE_OPERATOR (Bearer token)
- All outbound communication funnels via Agent Zero (HiL). The relay can be down; messages are still audited and visible in the Comms panel.

Next steps (already queued in TODO):
- Live metrics wiring (findings/time, severity heatmap)
- Force/cytoscape attack-graph visualization
- Wizard quick-actions -> TheHive staging (HiL approve/submit)
- Docker E2E run on a docker-capable host

## Pre-Dispatch Checklist and Follow-ups
- API: POST /reports/checklist { run_id, format_id, finding, evidence, mitigation }
  - Validates stakeholder formatting, recording presence, mitigation plan, and duplicate status.
- API: POST /submissions/followup { run_id, stakeholder }
  - Generates an .eml follow-up draft in artifacts/submissions/outbox for operator review.

K8s Ops:
- deploy/k8s/recorder.yaml contains a Deployment for the 24/7 screen recorder and a CronJob for retention.
