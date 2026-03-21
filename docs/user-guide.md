# Kai Platform User Guide

> **The primary manual for installing, running, and operating the Kai Platform.**

Kai (K1) is an enterprise-grade AI orchestration platform for autonomous security research. This guide covers everything you need to go from zero to a running mission.

---

## 1. Platform Overview

Kai coordinates autonomous agents to perform security research missions. Unlike simple script runners, Kai enforces strict governance:

*   **Agents** are role-based (Director, Coordinator, Specialist).
*   **Missions** are directed acyclic graphs (DAGs) of tasks.
*   **Governance** checks every tool execution against policy.
*   **Human-in-the-Loop (HIL)** allows operators to approve sensitive actions.

### Architecture Summary

The platform is built on six integrated layers:

1.  **PraisonAI (Control Plane):** Manages agent identities, lifecycle, and governance policy.
2.  **LangGraph (Runtime):** Executes the mission graph, managing state and checkpoints.
3.  **LangChain (Middleware):** Wraps LLMs and tools, providing a standard interface.
4.  **DeepAgents (Specialists):** Runs deep-dive tasks in isolated sandboxes.
5.  **LangSmith (Observability):** Tracks every trace, span, and token for debugging.
6.  **Simulation (Safety):** Allows dry-runs (`graph_only`, `tool_mock`) without real-world impact.

---

## 2. Installation

### Prerequisites

| Requirement | Minimum | How to check |
|-------------|---------|--------------|
| Linux (Ubuntu 22.04+ recommended) | — | Windows: use WSL2 |
| Python | 3.11+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Docker Engine + Compose plugin | 24+ | `docker compose version` |
| LLM API key | — | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` |

**Docker is required** to run PostgreSQL and Redis automatically. If you manage those services yourself, Docker is optional but you must ensure PostgreSQL (port 5432) and Redis (port 6379) are reachable before running `./k1-start`.

`bootstrap.sh` handles the following automatically on Ubuntu/Debian:
- System packages (curl, git, build-essential, pango/cairo libraries for weasyprint)
- Python virtualenv and all pip dependencies
- Node.js packages
- External recon tools (amass, subfinder, httpx, nuclei, dnsx, naabu, gau, gitleaks, etc.)

### First-time setup

```bash
# 1. Clone
git clone https://github.com/mrmsoc09/Kai.git
cd Kai

# 2. Bootstrap — installs everything, runs migrations, verifies tools
./bootstrap.sh

# 3. Configure API keys (REQUIRED before starting)
nano .env
# Set: ANTHROPIC_API_KEY or OPENAI_API_KEY
# Set: JWT_SECRET_KEY  (replace placeholder with a random string)
# Set: K1_DEV_TOKEN    (replace placeholder)

# 4. Start
./k1-start
```

Bootstrap prints a readiness summary at the end:
```
  ✓ Python deps installed
  ✓ UI deps installed
  ✓ Environment configured
  ✓ Migrations applied
  ✓ External tools verified
```

All lines must show `✓` before running `./k1-start`. If any show `✗`, follow the printed instructions and re-run `./bootstrap.sh`.

### What bootstrap installs

**System packages** (apt, Ubuntu/Debian):
- `curl`, `git`, `build-essential`, `libssl-dev`, `libffi-dev`
- `libpango-1.0-0`, `libpangocairo-1.0-0`, `libpangoft2-1.0-0` (weasyprint)
- `libgdk-pixbuf-2.0-0`, `libcairo2`, `libglib2.0-0`, `shared-mime-info`

**Python packages** (`.venv`):
- FastAPI, Uvicorn, SQLAlchemy, Alembic, Celery, Redis
- Anthropic, OpenAI, Google GenerativeAI SDKs
- PraisonAI agents, LangChain core, LangGraph, LangSmith
- LlamaIndex, ChromaDB, sentence-transformers (RAG/vector search)
- weasyprint, Pillow (PDF/report generation)
- Full list: `requirements.txt`

**Node packages** (`ui/node_modules`):
- React 18, Vite, Tailwind CSS, ReactFlow, Recharts, Zustand
- Full list: `ui/package.json`

**External tools** (auto-installed via `go install` or `apt`):
- Subdomain: amass, subfinder, assetfinder, findomain, dnsx
- Web: httpx, httprobe, naabu, tlsx, hakrawler, gau, waybackurls
- Secrets: gitleaks
- Scanning: nmap, theharvester
- If `go` is not installed, bootstrap will attempt to install `golang-go` via apt first.

**Manually install yourself** (tools that need user-supplied credentials or complex setup):
- `nuclei` templates are downloaded on first run by the nuclei binary
- HashiCorp Vault (port 8200) if using credential-backed tool execution
- Neo4j (port 7687) if using intelligence graph features

### Configuration

Edit `.env` after bootstrap:

```bash
nano .env
```

Required keys to set before starting:

| Key | Description |
|-----|-------------|
| `ANTHROPIC_API_KEY` | Or use `OPENAI_API_KEY` / `GOOGLE_API_KEY` |
| `JWT_SECRET_KEY` | Random 32+ byte string (never reuse across deployments) |
| `K1_DEV_TOKEN` | Local dev authentication token |

Optional keys for full capability:
- `VAULT_TOKEN` — Vault credential backing for tool execution
- `LANGCHAIN_API_KEY` — LangSmith observability (get from smith.langchain.com)
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` — Intelligence graph
- `SHODAN_API_KEY`, `VIRUSTOTAL_API_KEY` — External threat intel

---

## 3. Startup

Start the platform services with a single command:

```bash
./k1-start
```

This starts:
1.  **API Server:** The REST API and mission runtime (Port 8080).
2.  **Celery Worker:** The background worker for executing tools.
3.  **Operator UI:** Frontend workbench (Port 8081).
4.  **PostgreSQL + Redis:** Auto-started via Docker when available.

You will see output indicating the services have started.

To stop the platform:
```bash
./k1-stop
```

---

## 4. Running a Mission

You can interact with Kai via the **Analyst Cockpit** (Web UI) or API.

### Starting via API (Quickest)
(Assuming you don't have the frontend running yet)

You can trigger a standard reconnaissance mission via `curl`:

```bash
curl -X POST "http://localhost:8080/api/v1/missions/start" \
     -H "Content-Type: application/json" \
     -d '{
           "template": "standard_recon",
           "target": "example.com",
           "mode": "live"
         }'
```

### Monitoring Progress
Check the status of your mission:

```bash
curl "http://localhost:8080/api/v1/missions/{mission_id}/status"
```

Logs are streamed to `runtime/logs/api.log` and `runtime/logs/worker.log`.

---

## 5. Using Simulation Mode

Simulation allows you to test agent logic without spending money on LLMs or scanning real targets.

**Modes:**
*   **`graph_only`**: No LLM calls, no tools. fast topology check.
*   **`tool_mock`**: Real LLM reasoning, but tools return fake JSON data.
*   **`replay`**: Re-run a past mission from logs.

To run in simulation mode, simply change the `mode` parameter:

```bash
./scripts/run_workflow_local.py --template standard_recon --target example.com --mode tool_mock
```

---

## 6. Interpreting Results

All mission artifacts are stored in the `output/` directory:

*   **`output/reports/`**: Final PDF/Markdown reports.
*   **`output/raw/`**: Raw tool output (Nmap XML, JSONs).
*   **`output/logs/`**: Detailed execution logs.
*   **`output/workflows/`**: JSON dump of the mission state.

**Key Files:**
*   `mission_summary.json`: High-level overview of findings.
*   `findings.csv`: List of all discovered vulnerabilities.

---

## 7. Troubleshooting

**Issue: "Virtual environment not found"**
*   Run `./bootstrap.sh` again.

**Issue: Tools failing with "Permission Denied"**
*   Some tools (like Nmap) require root. Ensure you have sudo access or use unprivileged modes.

**Issue: "Worker not found" in logs**
*   Check `runtime/logs/worker.log`. Ensure Redis is reachable (or re-run `./k1-start` to restart managed infra).

**Issue: LLM Errors (401/403)**
*   Check your `.env` file for correct API keys.
*   Ensure you have credits/quota.

For deeper debugging, refer to `docs/developer-guide.md`.
