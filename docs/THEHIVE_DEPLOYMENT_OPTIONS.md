# TheHive — Deployment & Alternatives

Chosen for dev testing: Self-hosted TheHive 5 (Elasticsearch + Cassandra) via docker-compose.dev.yml.

Options:
1) Self-hosted (prod): Hardened images, externalized ES/Cassandra clusters, backups, SSO (Keycloak), TLS, Cortex analyzers.
2) Self-hosted (dev): Compose stack (as provided). No mocks in developer testing.
3) Alternatives for case/Q&A lifecycle:
   - Jira Service Management + Security workflows
   - ServiceNow SecOps (Vuln Response)
   - OpenCTI + MISP (intel first, case secondary)
   - RTIR / GitLab Issues (lightweight)

Selection factors: SOC familiarity, automation, cost, on-prem constraints, integrations with BBP.

Dev Test Plan (no mocks):
- Bring up compose; create project + case templates; verify API (TheHive v5 /api).
- Wire submit flow: create case on HIL approval; sync comments for stakeholder Q&A.
