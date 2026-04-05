# KAISON AI — Autonomous Bug Bounty Platform

> Governance-first autonomous vulnerability research platform for authorized bug bounty programs.
> Built by Spec.1 | Combat-Jack Security Research | SDVOSB

KAISON AI runs autonomous bug bounty hunts across HackerOne, Bugcrowd, and Intigriti programs. It coordinates 51 specialist tool agents across 9 hunt phases, applies governance controls at every phase transition, and produces professional reports ready for program submission.

## What It Does

**51 specialist tool agents** coordinated across 9 hunt phases:
- **Phase 1-2**: Passive recon (subfinder, amass, dnsx, chaos, github-subdomains)
- **Phase 2**: Active fingerprinting (httpx, naabu, masscan, wafw00f, gowitness)
- **Phase 3**: Content discovery (feroxbuster, katana, paramspider, arjun, gf)
- **Phase 4**: OSINT intelligence (spiderfoot, sherlock, phoneinfoga, social-analyzer)
- **Phase 5**: Dark web intelligence (torbot, onionsearch, ahmia-client)
- **Phase 6**: Secret scanning (trufflehog, gitleaks)
- **Phase 7**: Vulnerability scanning (nuclei, nikto, testssl, dalfox, sqlmap)
- **Phase 8**: API security (jwt_tool, kiterunner, graphql-cop, clairvoyance)
- **Phase 9**: Aggregation (faraday-community)

**13 CrewAI and AutoGen2 crews** for intelligent pre-scan reasoning and adversarial finding validation.

**Real-time frontend**: Tool agent dashboard, crew monitor, orchestrator panel, master findings, approval gates.

## Quick Start

```bash
git clone https://github.com/mrmsoc09/Kai
cd Kai
cp .env.example .env
# Add API keys to .env
./bootstrap.sh
./k1 start
```

Open http://localhost:8081 (frontend) | http://localhost:8080/docs (API)

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose
- 8GB RAM minimum (40GB recommended)
- Linux (Ubuntu 22.04+ recommended)

## Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install all 51 tool agent binaries
./scripts/install_community_tools.sh

# Initialize database
alembic upgrade head

# Start all services
./k1 start
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Required
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key

# Optional but recommended
GEMINI_API_KEY=your_key
SHODAN_API_KEY=your_key
GITHUB_TOKEN=your_token
CHAOS_API_KEY=your_key
```

## Running a Hunt

1. Navigate to http://localhost:8081
2. Add a bug bounty program (scope and rules)
3. Click Start Mission
4. Monitor progress in Mission Control
5. Review findings in Master Findings view
6. Approve Band 2 actions in Approvals dashboard
7. Export report when complete

## CrewAI and AutoGen2 Integration

Install optional crew support:
```bash
pip install "praisonai[crewai]" "praisonai[autogen]"
```

Crews run before tool agents to produce strategic scanning plans. AutoGen2 validation crews run Hunter vs Skeptic adversarial review on every finding before submission.

## Commands

```bash
./k1 start                  # Build and launch all services
./k1 stop                   # Stop all services
./k1 restart                # Stop then start
./k1 setup                  # Configuration wizard
./k1 logs                   # Tail container logs

python -m pytest tests/ -q  # Run tests
cd apps/frontend && npm run dev   # Frontend dev server
```

## Governance

- **Band 0**: Passive tools (auto-approved)
- **Band 1**: Active probing (auto-approved)
- **Band 2**: Intrusive scanning (requires approval)
- **Band 3**: Exploitation (blocked in Community Edition)

All tool execution passes through authorization gates with scope validation and audit logging.

## Architecture

**Backend**: FastAPI with 70+ routers, SQLAlchemy ORM, Celery workers, multi-provider LLM routing.

**Frontend**: React + Material UI with real-time WebSocket updates and agent streaming.

**Database**: PostgreSQL 16 with async SQLAlchemy, Alembic migrations.

**Orchestration**: LangGraph pipeline with Kahn's algorithm topology, GeminiOrchestrator, MidnightOrchestrator.

**Security**: httpOnly sessions, CSRF protection, Vault secrets, scope validation at every phase.

**Services**: Backend (8080), Frontend (8081), Worker (Celery), PostgreSQL, Redis, Vault.

## Testing

```bash
# Backend tests
python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/test_simulation_mode.py

# Full suite (requires PostgreSQL, Redis, Vault)
pytest
```

## Community Edition vs Pro/Enterprise

| Feature | Community | Pro | Enterprise |
|---------|-----------|-----|------------|
| Tool agents | 51 | 60+ | 70+ |
| Hunt phases | 9 | 9 | 9 |
| Programs | Unlimited | Unlimited | Unlimited |
| Support | GitHub | Email | SLA |

## License

MIT License — see LICENSE file.

## Author

Spec.1 | Combat-Jack Security Research  
kaisonai.com | combat-jack.com
