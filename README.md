# Kai

**Autonomous OSINT, Reconnaissance, and Enterprise Vulnerability Assessment Platform**

---

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/ mrmsoc09/Kai)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## 🚀 Overview
Agent-Zero is a next-generation, open-source platform for automated OSINT, recon, and vulnerability assessment with strict human-in-the-loop (HiL) validation and enterprise-grade security. Designed for bug bounty hunters, penetration testers, SOC analysts, and compliance teams, Agent-Zero fuses AI reasoning, rule-based policy gates, and modular workflows for safe, auditable vulnerability discovery, triage, and professional reporting.

## 🌐 Key Capabilities
- **Autonomous OSINT & Recon:**
  - Domain enumeration, DNS, WHOIS, TLS/SSL, subdomain and cloud mapping
  - Tech stack fingerprinting, exposure mapping, and third-party dependency discovery
  - Knowledge graph relationship and attack-path mapping
- **Vulnerability Discovery:**
  - Passive scan pipelines (OWASP/CVE/ExploitDB correlation, CVSS v3 severity)
  - Advanced triage (EPSS/NVD/KEV scores, ML-powered exploitability ranking)
  - CVE/CPE/KEV/EPSS ingestion, RAG vector search, and contextual scoring
- **Evidence-First Reporting:**
  - Automated, HiL-gated vulnerability reporting
  - Professional output: PDF (primary), HTML, JSON, CSV
  - Actionable mitigation guidance and stakeholder format templates
  - Screen recording, audit chain, and immutable evidence links
- **Automation & Compliance:**
  - Role-based access control (RBAC), audit logs, and privacy enforcement
  - Policy and scope enforcement baked into every action
  - Automated artifact and report storage with no host spillage
- **Integration & Extensibility:**
  - Clean REST API, webhook support, program-driven ingest
  - Provider registry (for API keys, compliance, target sources)
  - Pluggable toolchains, Nuclei/Semgrep/CodeQL pipelines, and scheduled/adhoc scans
- **Built for Operators:**
  - Secure, neon-themed SOC dashboard (Display Hub) for real-time orchestration
  - Live status, logs, stream/historic artifacts—all with HiL control and auditability
---

## 📦 Architecture & Tech Stack
- **Backend:** Python (FastAPI), modular agent orchestrator (kai/k1), key routers and microservices
- **Frontend:** React/Vite (neon dark SOC UI), live dashboard, planner, and HiL review/approval GUIs
- **Storage:** Postgres + pgvector, Redis (STM), Qdrant (vector alt), Vault (key management)
- **Pipelines:** Dorks/OSINT, triage (offline/online), evidence-first reporting
- **Orchestrator:** Agent pipeline executor, audit logs, jobs/queue, RBAC, compliance engine
- **Deployment:** Docker Compose, K8s manifests, Vault, TheHive, Elastic/Jaeger
---

## 🏁 Getting Started
1. **Clone the Repo:**
   ```sh
   git clone https://github.com/mrmsoc09/Kai.git
   cd Kai # Adjust if directory name differs

Configure (env):
Copy .env.example as needed (do not add secrets to Git—see docs/KEY_INTAKE.md)
Deploy the Stack:
Docker Compose: docker compose -f deploy/docker-compose.dev.yml up --build
See k1/docs/DEV_STACK_RUN.md for details
Access the Dashboard:
Open localhost:3000 for the SOC UI
Begin OSINT/Scan:
Queue a Bug Bounty Program, configure scope, and launch a run
Human-in-the-Loop Review:
Approve, redact, and submit findings (no reports leave the system without HiL approval)

See OPERATOR_QUICKSTART.md for step-by-step flow.

🔒 Security & Privacy
No sensitive data, scan artifacts, or real secrets are ever stored or pushed by default
All secrets are .env-managed, Vault-protected, and must not be committed
All actions are auditable and HiL-gated for compliance
💡 Use Cases
Autonomous bug bounty hunting (policy-aware, scope-safe)
Penetration testing (internal and ext. surface mapping)
Continuous vulnerability triage and triage enrichment
Enterprise reporting/audit and compliance validation
Managed security service orchestration (MSSP)
🛠️ Contributing & Extending
PRs welcome—see CONTRIBUTING.md
All modules are designed for extension (custom scanners, report formats, personas, plugins)
Strict no-secrets-touched policy on pushes
📖 Further Documentation
ARCHITECTURE.md (Layered design, agent workflow, API schema)
SECURITY.md (Threat model & policy info)
SCALING_PLAN.md (Hybrid compute, LLM, ethics)
REPORT_FORMATS.md
KEY_INTAKE.md
TheHive/Elastic integrations: THEHIVE_BOOTSTRAP.md
💰 Productization & Monetization
Fully open-source (permissive license)
Built for commercial SOC/consulting, MSSP service delivery, or in-house CTA/DFIR/SOC
Monetizable as a compliant vulnerability management/triage solution, SaaS, or managed bounty platform
Integration ready for third-party plugins, external scan engines, and security workflow tools
📣 License & Credits
MIT License; see LICENSE. Built by and for the autonomous operator/security research community.

Contact, live support, and bounty program sponsorships: see GitHub Issues or repo Discussions.


Save as README.md in the root of your sanitized codebase (e.g., /home/user23/kai/kaison-one-latest/README.md) prior to any public/post-push. For separate docs or API/architecture breakdown, ask anytime.

# K1 (Kaison One) – HiL RL-AGI Vulnerability Hunting System
Human-in-the-Loop, reflection-driven recon and vulnerability hunting platform. Modular (Recon-NG/Metasploit-style), with MCP/RAG/DAG/GAG connectivity and a Display Hub UI.
