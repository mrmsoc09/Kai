# KAISON AI Changelog

## v1.0.0-community — 2026-04-05

First open source Community Edition release.

### Platform

- Governance-first autonomous bug bounty pipeline
- 9-phase hunt workflow from passive recon to reporting
- Band 0/1/2/3 authorization gates at every phase
- LangGraph mission runtime with Kahn's algorithm DAG execution
- GeminiOrchestrator with 5-tier model routing and automatic failover
- VisionValidationService with Playwright + Claude vision
- Midnight API key orchestrator with quota management
- Confirmed-finding feedback loop for agent improvement
- Real-time WebSocket agent event streaming

### Tool Agents (51 total)

**Phase 1-2 (Recon & Fingerprinting - 15 agents)**
- subfinder, amass, dnsx, gau, waybackurls
- httpx, naabu, masscan, wafw00f, gowitness
- assetfinder, findomain, chaos, github-subdomains, nmap

**Phase 3 (Content Discovery - 7 agents)**
- feroxbuster, katana, paramspider, arjun, hakrawler, ffuf, gf

**Phase 4-5 (OSINT & Dark Web - 8 agents)**
- spiderfoot, sherlock, phoneinfoga, social-analyzer, reconftw
- torbot, onionsearch, ahmia-client

**Phase 6-7 (Secrets & Vulnerabilities - 12 agents)**
- trufflehog, gitleaks
- nuclei, nikto, testssl, dalfox, sqlmap, ssrfmap
- corsy, crlfuzz, smuggler, searchsploit

**Phase 8-9 (API & Aggregation - 9 agents)**
- jwt_tool, kiterunner, graphql-cop, clairvoyance
- owasp-zap, caido
- faraday-community

### Crew Orchestration Agents (7 total)

- OSINTIntelligenceAgent
- DarkWebIntelAgent
- SecretScannerAgent
- ContentDiscoveryAgent
- VulnerabilityAgent
- APISecurityAgent
- FaradayCoordinatorAgent

### CrewAI and AutoGen2 Crews (13 definitions)

**CrewAI Crews (9)**
- primary_recon_crew (Scout/Mapper/Validator)
- certificate_intel_crew (CT analyst/Acquisition tracker)
- dns_intelligence_crew (DNS specialist/Takeover hunter)
- primary_vuln_crew (Hunter/Analyst/Verifier)
- business_logic_crew (Logic analyst/Auth flow analyst)
- rest_api_crew (API analyst/Schema mapper)
- graphql_specialist_crew (GraphQL specialist)
- organization_intel_crew (Org investigator/Credential monitor)
- scope_guardian_crew (Scope guardian/Policy auditor)

**AutoGen2 Validation Crews (2)**
- finding_review_conversation (Hunter vs Skeptic agents)
- severity_consensus (CVSS analyst/Severity reviewer)

### Frontend

Complete operator GUI built with React 18 + Material UI 7 + Vite.

**17 Routes**
- /dashboard — Command center
- /hunt — Workflow manager
- /scan-pool — Scan queue
- /findings — All findings
- /master-findings — Deduplicated findings
- /operations/approvals — Approval gates
- /intel — Threat intel
- /recon — Reconnaissance
- /attack-graph — Attack surface
- /ai — Natural language composer
- /providers — LLM provider dashboard
- /console — Command console
- /agents — Tool agent dashboard
- /crew — Crew agent monitor
- /registry — Tool registry browser
- /crews — CrewAI crew browser
- /status — Platform health

**Features**
- Real-time WebSocket streaming
- Tool filtering by safety/phase/category
- Crew execution with modal previews
- Platform health checks (30s auto-refresh)
- Mission readiness indicators
- Band 2 approval UI
- Agent streaming responses

### Security

- httpOnly sessions
- CSRF protection
- Vault secret management
- No credentials in logs
- Band 3 blocked
- Scope validation before active phases
- Audit logging
- PGP certificate verification

### Infrastructure

- Docker Compose stacks
- Prometheus + Grafana monitoring
- Alembic database migrations
- install_community_tools.sh
- bootstrap.sh setup wizard
- k1 platform commands

### Code Quality

- 1719 tests passing
- Black + Ruff + isort + mypy
- SQLAlchemy async ORM
- FastAPI with OpenAPI docs
- Pydantic validation
- pytest with fixtures

### Documentation

- README.md — Platform overview
- CLAUDE.md — Dev guidance
- docs/architecture/ — Architecture
- docs/HANDOFF.md — Session tracking

---

## Installation

```bash
git clone https://github.com/mrmsoc09/Kai
cd Kai
./bootstrap.sh
./k1 start
```

## Support

GitHub: https://github.com/mrmsoc09/Kai

## License

MIT License — see LICENSE file.

## Author

Spec.1 | Combat-Jack Security Research
kaisonai.com | combat-jack.com
