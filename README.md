# KaisonOne — Autonomous Bug Bounty Platform

> **Governance-first autonomous vulnerability research for authorized bug bounty programs**

[![Version](https://img.shields.io/badge/version-0.9--Streamlined-blue)]()
[![Tools](https://img.shields.io/badge/tools-35%20essential-brightgreen)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-lightgrey)]()

KaisonOne runs autonomous bug bounty hunts across HackerOne, Bugcrowd, and private programs. It coordinates **35 specialist security tools** across **3 execution tiers**, applies governance controls at every phase, and produces professional reports ready for program submission.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    KAISONONE PLATFORM ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐           │
│  │   BBP APIs  │────▶│   Ingest    │────▶│   Scope     │           │
│  │  H1, BC, etc│     │   Engine    │     │  Guardrails │           │
│  └─────────────┘     └─────────────┘     └──────┬──────┘           │
│                                                  │                  │
│                          ┌───────────────────────┘                  │
│                          ▼                                          │
│               ┌───────────────────────┐                             │
│               │  TIERED WORKFLOW      │                             │
│               │  ORCHESTRATOR         │                             │
│               └───────────┬───────────┘                             │
│                           │                                         │
│       ┌───────────────────┼───────────────────┐                     │
│       ▼                   ▼                   ▼                     │
│  ┌─────────┐        ┌─────────┐        ┌─────────┐                 │
│  │ TIER 1  │        │ TIER 2  │        │ TIER 3  │                 │
│  │Core     │───────▶│Targeted │───────▶│Special  │                 │
│  │(Always) │        │(Trigger)│        │(Manual) │                 │
│  └────┬────┘        └────┬────┘        └────┬────┘                 │
│       │                  │                  │                       │
│       ▼                  ▼                  ▼                       │
│  [17 tools]         [11 tools]         [7 tools]                   │
│                                                                      │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    INTELLIGENCE & REPORTING LAYER                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │ Deduplicate │─▶│ CVE Enrich  │─▶│   Bounty    │─▶│  Platform  │ │
│  │   Engine    │  │   Engine    │  │   Estimate  │  │  Formatter │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │
│                                                                      │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    HUMAN-IN-THE-LOOP GATE                           │
│                     (Review → Approve → Submit)                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The 35-Tool Stack

### Tier 1 — Core (Always Run)
*Complete reconnaissance and primary vulnerability detection*

| Category | Tools |
|----------|-------|
| **OSINT** | Amass, Subfinder, SpiderFoot, TheHarvester |
| **Network** | Masscan, Nmap, Naabu, HTTPX |
| **Discovery** | GAU, Katana, Arjun, FFUF |
| **Vulnerability** | Nuclei, Dalfox, SQLMap, Ghauri, SSRFMap, XSStrike |

**17 tools | Coverage: Attack surface → Primary vuln detection | Redundancy: 2x for XSS, SQLi**

### Tier 2 — Targeted (Conditional)
*Triggered by asset type detection*

| Trigger | Tools |
|---------|-------|
| API endpoints detected | Kiterunner, GraphQLMap, RESTler |
| Cloud assets found | Prowler, ScoutSuite, Trivy |
| JWT/auth detected | JWT-Tool, AuthMatrix, Hydra |
| Git repos found | TruffleHog, Gitleaks |
| File uploads found | Fuxploider, RaceTheWeb |

**11 tools | Coverage: Specialized assessment | Redundancy: Dual secrets scanning**

### Tier 3 — Specialized (Manual/High-Value)
*Deep inspection for high-value targets*

| Domain | Tools |
|--------|-------|
| Client-Side | DOMDig, CSP-Evaluator |
| Network Internal | BloodHound, CrackMapExec |
| Mobile | MobSF |

**7 tools | Coverage: Niche vulnerabilities | Requires authorization**

---

## Quick Start

```bash
# Clone repository
git clone https://github.com/your-handle/Kai.git
cd Kai

# Bootstrap — auto-installs missing 35 tools
./bootstrap.sh

# Configure API keys
cp .env.example .env
# Edit .env with your keys

# Start platform
./k1 start

# Access
# Frontend: http://localhost:8081
# API Docs: http://localhost:8080/docs
```

---

## Prerequisites

- **OS:** Linux (Ubuntu 22.04+ recommended) or macOS
- **Python:** 3.11+
- **Node.js:** 18+
- **Docker:** 20.10+ with Compose
- **RAM:** 8GB minimum, 16GB recommended
- **Disk:** 20GB for tools + scan data

---

## API Keys (Essential Tools)

| Variable | Tools | Required | Get Key |
|----------|-------|----------|---------|
| `CHAOS_API_KEY` | Subfinder | Recommended | [ProjectDiscovery](https://chaos.projectdiscovery.io/) |
| `GITHUB_TOKEN` | Subfinder, TruffleHog | Recommended | [GitHub](https://github.com/settings/tokens) |
| `SHODAN_API_KEY` | Amass | Optional | [Shodan](https://account.shodan.io/) |
| `OPENAI_API_KEY` | Intelligence Engine | Optional | [OpenAI](https://platform.openai.com/) |

Full API key matrix: [docs/api-keys.md](docs/api-keys.md)

---

## Workflow Execution

```python
from modules.orchestration.tiered_orchestrator import TieredWorkflowOrchestrator

# Initialize orchestrator
orchestrator = TieredWorkflowOrchestrator()

# Run tiered scan
results = await orchestrator.execute_scan(
    target="example.com",
    bbp_mode="public_bbp",  # or "private_contract", "enterprise_audit"
    enable_redundancy=True  # Run secondary tools for 2x coverage
)

# Results include:
# - Tier 1: 17 core tool outputs
# - Tier 2: 11 conditional tool outputs (if triggered)
# - Tier 3: 7 specialized outputs (if requested)
# - Aggregated findings with deduplication
# - Bounty estimate recommendations
```

---

## Autonomous Mode

KaisonOne operates as an agentic system:

1. **Ingest** → Parse BBP scope from API
2. **Recon** → Tier 1 tools map attack surface
3. **Trigger** → Detect assets, activate Tier 2 tools
4. **Analyze** → Intelligence engine scores findings
5. **Report** → Generate platform-ready submissions
6. **Review** → HiL gate for human approval

---

## Project Structure

```
KaisonOne/
├── tools/wrappers/       # 35 tool wrappers (one per tool)
├── modules/
│   ├── orchestration/    # Tiered orchestrator, selection engine
│   └── reporting/        # Intelligence + report generation
├── config/
│   └── bbp_modes.yaml    # Public/Private/Enterprise configs
├── scripts/
│   └── bootstrap.sh      # Auto-installation script
├── docs/                 # Architecture, operator guides
└── vendor/               # PentAGI, CAI submodules
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache 2.0 — See [LICENSE](LICENSE)

---

**Built for autonomous security research. Authorized bug bounty programs only.**
