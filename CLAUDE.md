# CLAUDE.md

Guidance for Claude Code working on KAISON AI.

## Platform

**KAISON AI** — Autonomous bug bounty hunting platform with 51 specialist tool agents, 7 crew orchestration agents, 11 CrewAI crews, 2 AutoGen2 validation crews, LangGraph mission runtime, and governance-first architecture.

**Current SHA**: v1.0.0-community (commit: 8598660)

## Quick Start

```bash
./k1 start          # Build and launch all services
./k1 stop           # Stop all services
./k1 restart        # Stop then start
./k1 setup          # Configuration wizard
./k1 logs           # Tail container logs
```

## Testing

```bash
pytest tests/ -q --ignore=tests/integration --ignore=tests/test_simulation_mode.py
pytest tests/test_foo.py                    # Single file
pytest tests/test_foo.py::test_bar          # Single test
```

## Frontend Development

```bash
cd apps/frontend
npm run dev         # Vite dev server on :5173
npm run build       # Production build
```

## Backend API

```bash
python3 -m uvicorn apps.backend.src.main:app --host 0.0.0.0 --port 8080 --reload
```

## Architecture Summary

**Backend** (`apps/backend/src/`): FastAPI with 70+ routers, SQLAlchemy ORM, Celery workers, multi-provider LLM routing (Anthropic/OpenAI/Gemini/Ollama).

**Frontend** (`apps/frontend/src/`): React 18 + TypeScript + MUI 7 with Zustand stores, 13 routes, real-time WebSocket updates.

**Database**: PostgreSQL 16 with asyncpg, Alembic migrations.

**Orchestration**: LangGraph pipeline using Kahn's algorithm, GeminiOrchestrator (5-tier routing), MidnightOrchestrator (API quota management).

**Tool Agents**: 51 agents across 9 phases (recon, fingerprinting, discovery, OSINT, dark web, secrets, vuln scanning, API testing, aggregation).

**Crew Agents**: 7 orchestration crews + 11 CrewAI crews + 2 AutoGen2 validation crews (Hunter vs Skeptic).

**Security**: httpOnly sessions, CSRF protection, Vault secrets, scope validation before every active phase, Band 0/1/2/3 authorization gates.

## Key Files

- `apps/backend/src/main.py` — FastAPI entry point
- `apps/backend/src/core/kai_orchestrator.py` — Scope enforcement
- `apps/backend/src/core/praison_mission_runtime.py` — Mission DAG execution
- `apps/backend/src/core/crew_yaml_runner.py` — Crew YAML executor
- `apps/frontend/src/App.tsx` — React router configuration
- `crews/crew_registry.yaml` — Crew mapping to hunt phases
- `docs/architecture/` — Architecture documentation

## Commands Reference

| Command | Purpose |
|---------|---------|
| `./bootstrap.sh` | First-time setup (deps, migrations, tools) |
| `./k1 start` | Start all services (Docker Compose) |
| `./k1 stop` | Stop all services |
| `pytest tests/ -q` | Run core tests |
| `npm run build` (frontend) | Production build |
| `black . && ruff check .` | Format and lint Python |

## Code Style

- **Python**: black (100 char), ruff, isort (black profile), mypy
- **Frontend**: TypeScript strict mode, MUI components, Zustand stores
- **pytest**: pythonpath is `apps/backend/src`
- All imports resolve from `apps/backend/src` in tests

## Development Rules

- Read existing code before modifying architecture
- Never claim features are implemented without proof from code
- Use Celery workers for tool execution (never direct API calls)
- Preserve public interfaces when practical
- Write docs before major rewrites
- Surface uncertainty explicitly

## Database

**PostgreSQL 16** via SQLAlchemy async (asyncpg, pool_size=20).

**Migrations**: Alembic in `alembic/versions/`.

**Connection**: `get_db()` dependency injection in routers.

## Multi-Provider LLM

Providers configured in `config/providers/*.yaml` and `config/registry/routing_matrix.yaml`.

Primary: `K1_PRIMARY_LLM_PROVIDER` env
Fallback: `K1_FALLBACK_LLM_PROVIDERS` env

Supported: Anthropic, OpenAI, Gemini, Ollama, Gemma, Qwen, OpenRouter.

## Services (Docker Compose)

| Service | Port | Purpose |
|---------|------|---------|
| backend | 8080 | FastAPI API |
| frontend | 5173 | Vite dev (or 8081 prod) |
| worker | — | Celery worker |
| postgres | 5432 | Database |
| redis | 6379 | Cache + broker |
| vault | 8200 | Secrets |

## Governance

- **Band 0**: Passive tools (auto-approved)
- **Band 1**: Active probing (auto-approved)
- **Band 2**: Intrusive scanning (approval required)
- **Band 3**: Exploitation (blocked)

Scope validation: deny-by-default → explicit deny → CIDR → allowlist.

Approval gates use LangGraph interrupts with human-in-the-loop Band 2 enforcement.
