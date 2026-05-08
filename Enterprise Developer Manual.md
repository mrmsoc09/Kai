# Enterprise Developer Manual

This manual serves as a comprehensive resource for developers working with the KaisonOne platform. It details architectural overviews, API references, development guides, agent and skill authoring, tool integration, and best practices for extending and contributing to the platform.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [The 35-Tool Stack](#the-35-tool-stack)
4. [Workflow Execution](#workflow-execution)
5. [Autonomous Mode](#autonomous-mode)
6. [Project Structure](#project-structure)
7. [Contributing](#contributing)
8. [License](#license)

---

## 1. Project Overview

KaisonOne runs autonomous bug bounty hunts across HackerOne, Bugcrowd, and private programs. It coordinates **35 specialist security tools** across **3 execution tiers**, applies governance controls at every phase, and produces professional reports ready for program submission.

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    KAISONONE PLATFORM ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐           │
│  │   BBP APIs  │────▶│   Ingest    │────▶│   Scope     │           │
│  │  H1, BC, etc│     │   Engine    │     │  Guardrails │           │
│  └─────────────┘     └──────┬──────┘     └──────┬──────┘           │
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

## 3. The 35-Tool Stack

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

## 4. Workflow Execution

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

## 5. Autonomous Mode

KaisonOne operates as an agentic system:

1. **Ingest** → Parse BBP scope from API
2. **Recon** → Tier 1 tools map attack surface
3. **Trigger** → Detect assets, activate Tier 2 tools
4. **Analyze** → Intelligence engine scores findings
5. **Report** → Generate platform-ready submissions
6. **Review** → HiL gate for human approval

---

## 6. Project Structure

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

## 7. Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 8. License

Apache 2.0 — See [LICENSE](LICENSE)
