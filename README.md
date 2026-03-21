# Kai (K1) Platform

> **Governance-first autonomous mission orchestration for authorized security research.**

Kai coordinates autonomous agents to perform security research missions under strict governance policies. Every tool call, agent spawn, and scope decision passes through a multi-layer governance stack with human-in-the-loop approval gates, immutable delegation contracts, and defense-in-depth enforcement.

---

## Quick Start

```bash
./bootstrap.sh       # First-time setup
./k1 start           # Build and launch all services
```

Open the operator cockpit at `http://localhost:5173`.

```bash
./k1 stop            # Stop all services
./k1 restart         # Stop then start
./k1 setup           # Configuration wizard
./k1 logs            # Tail container logs
```

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
| frontend | 5173 | Vite React operator cockpit |
| worker | — | Celery worker (tools queue) |
| postgres | 5432 | Primary database + LangGraph checkpoints |
| redis | 6379 | Cache + Celery broker |
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
