# Kai (K1) Platform

> **Governance-first autonomous mission orchestration for authorized security research.**

Kai coordinates autonomous agents to perform security research missions under strict governance policies. Every tool call, agent spawn, and scope decision passes through a multi-layer governance stack with human-in-the-loop approval gates, immutable delegation contracts, and defense-in-depth enforcement.

---

## Quick Start

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Linux (Debian/Ubuntu recommended) | — | Windows via WSL2 |
| Python | 3.11+ | `python3 --version` |
| Node.js | 18+ | `node --version` — [nodejs.org](https://nodejs.org) |
| Docker Engine + Compose | 24+ | Supports `docker compose` and `docker-compose` |
| LLM credentials | Optional | Cloud API key or local Ollama runtime |

`bootstrap.sh` installs system packages and Python/Node dependencies automatically on Ubuntu/Debian.
External recon tools (amass, subfinder, nuclei, etc.) are auto-installed when `go` is available.

### First-time setup

```bash
git clone https://github.com/mrmsoc09/Kai.git
cd Kai

./bootstrap.sh   # install deps, configure env, run migrations, verify tools

# Optional local-only profile (Ollama <=9B + Vault dev defaults)
./scripts/apply_local_ollama_profile.sh

./k1-start       # start backend + celery worker + operator UI
```

Open the operator UI at **http://localhost:8081**.
API docs at **http://localhost:8080/docs**.

```bash
./k1-stop        # stop all services
```

### What bootstrap does

1. Installs system packages (`curl`, `git`, `build-essential`, pango/cairo for weasyprint)
2. Creates Python virtualenv at `.venv` — installs `requirements.txt`
3. Installs Node.js packages in `ui/node_modules`
4. Creates `.env` from `.env.example` (first run)
5. Creates artifact/runtime directories (`artifacts/`, `output/`, `runtime/`)
6. Starts PostgreSQL + Redis via Docker Compose and runs Alembic migrations
7. Verifies and auto-installs enabled external tools (amass, subfinder, httpx, nuclei, etc.)
8. Prints a readiness summary — **all lines must show ✓ before running `./k1-start`**

### What must be configured manually

Edit `.env` after the first bootstrap run:
- For cloud providers: `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
- For local-only mode: run `./scripts/apply_local_ollama_profile.sh` to pin Ollama + Vault defaults
- `JWT_SECRET_KEY` — replace placeholder with a cryptographically random value
- `K1_DEV_TOKEN` — replace placeholder

See `.env.example` for the full variable reference.

Legacy container orchestration remains available via `./k1 start` (Docker Compose full stack).

---

## Architecture

Kai is built on six integrated layers, each with explicit authority boundaries:

```
┌─────────────────────────────────────────────────────────┐
│  PraisonAI Control Plane                                │
│  Agent registry · Governance engine · Delegation        │
│  contracts · Adaptive learning · Strategy profiles      │
├─────────────────────────────────────────────────────────┤
│  LangGraph Mission Runtime                              │
│  K1GraphState · DAG execution · Checkpointing ·         │
│  Interrupt-based approval gates · Cluster subgraphs     │
├─────────────────────────────────────────────────────────┤
│  LangChain Model / Tools Layer                          │
│  K1ChatModel · K1GovernedTool · Middleware stack ·      │
│  Structured output schemas · Reasoning engine           │
├─────────────────────────────────────────────────────────┤
│  DeepAgents Specialist Runtime                          │
│  Bridge layer · Sandbox isolation · Contract-aware      │
│  subagent delegation · Namespace-aware streaming        │
├─────────────────────────────────────────────────────────┤
│  LangSmith Observability                                │
│  Trace correlation · Redaction · Evaluations ·          │
│  A/B experiments · Dataset management                   │
├─────────────────────────────────────────────────────────┤
│  Simulation Safety Overlay                              │
│  graph_only · tool_mock · replay · Fixture system ·     │
│  Safety barriers (no mode escalation to live)           │
└─────────────────────────────────────────────────────────┘
```

### Services

| Service | Port | Purpose |
|---------|------|---------|
| backend | 8080 | FastAPI API server |
| frontend | 8081 | Vite React operator cockpit |
| worker | — | Celery worker (tools queue) |
| postgres | 5432 | Primary database + LangGraph checkpoints |
| redis | 6379 | Cache + Celery broker |
| ollama | 11434 | Local model inference |
| vault | 8200 | Secret management |
| mailhog | 8025 | Email testing UI |

---

## Security Model

- **Tool Risk Bands**: Band 0 (passive, auto-approved) through Band 3 (exploit-like, always blocked)
- **Governance Stack**: 5 enforcement layers — PraisonGovernor validates, audit hook records, enforce hook blocks
- **Delegation Contracts**: Frozen, immutable, bidirectional trust enforcement between agents
- **Scope Enforcement**: Deny-by-default. Explicit deny checked first, then CIDR, then allowlist
- **Secrets**: Vault-only. Credentials never pass through graph state or LLM context
- **Approval Gates**: Band 2 tools require human-in-the-loop approval before execution

---

## Execution Modes

| Mode | LLM Calls | Tool Execution | Use Case |
|------|-----------|---------------|----------|
| `live` | Real | Real | Production missions |
| `graph_only` | None | None | Topology validation |
| `tool_mock` | Optional | Fixtures | Strategy testing |
| `replay` | None | None | Historical analysis |

Simulation modes **never** escalate to live tool execution. All simulation artifacts carry provenance markers.

---

## Multi-Provider AI

Kai routes LLM inference through a unified provider abstraction with automatic failover:

- Anthropic Claude
- OpenAI
- Google Gemini
- Ollama (local)
- Gemma, Qwen, OpenRouter

Configure via `K1_PRIMARY_LLM_PROVIDER` and `K1_FALLBACK_LLM_PROVIDERS` environment variables.

---

## Testing

```bash
# Self-contained tests (no external services required)
python -m pytest tests/test_scope_guardrails.py tests/test_tool_registry_catalog.py \
  tests/test_bugbounty_workflow_engine.py tests/test_tool_adapters_bugbounty.py -q

# Full suite (requires PostgreSQL, Redis, Vault)
pytest
```

---

## Documentation

| Document | Content |
|----------|---------|
| [Architecture](docs/architecture.md) | 6-layer system design, control flow, authority boundaries |
| [Security Architecture](docs/security-architecture.md) | Governance model, risk bands, approval flow, delegation contracts |
| [Mission Runtime](docs/mission-runtime.md) | K1GraphState, DAG execution, checkpointing, interrupts |
| [LangChain / DeepAgents / LangSmith](docs/langstudio-integration.md) | Model abstraction, governed tools, specialist execution, observability |
| [Simulation Mode](docs/simulation-mode.md) | graph_only, tool_mock, replay, fixtures, safety barriers |
| [Operator Guide](docs/operator-guide.md) | Missions, approvals, artifacts, troubleshooting |
| [Developer Guide](docs/developer-guide.md) | Adding agents, tools, nodes, schemas, fixtures |

---

## License

Licensed under the MIT License.
