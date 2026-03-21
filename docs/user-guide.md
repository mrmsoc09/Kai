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
*   **Linux/macOS** (Windows requires WSL2)
*   **Python 3.11+**
*   **Redis** (for task queue)
*   **PostgreSQL** (optional for dev, required for prod state persistence)

### Automated Setup

We provide a script to bootstrap the environment:

```bash
# 1. Clone the repository
git clone https://github.com/mrmsoc09/Kai.git
cd Kai

# 2. Run the setup script
./scripts/setup.sh
```

This script will:
*   Create a Python virtual environment (`.env`).
*   Install all dependencies.
*   Create a default `.env` configuration file.
*   Run database migrations.
*   Create necessary artifact directories.

### Configuration
Edit the generated `.env` file to add your API keys:

```bash
nano .env
```

Ensure you set:
*   `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` (for agents).
*   `DATABASE_URL` (defaults to sqlite/postgres).
*   `REDIS_URL` (defaults to localhost).

---

## 3. Startup

Start the platform services with a single command:

```bash
./scripts/k1-start.sh
```

This starts:
1.  **API Server:** The REST API and mission runtime (Port 8080).
2.  **Celery Worker:** The background worker for executing tools.

You will see output indicating the services have started.

To stop the platform:
```bash
./scripts/k1-stop.sh
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
*   Run `./scripts/setup.sh` again.

**Issue: Tools failing with "Permission Denied"**
*   Some tools (like Nmap) require root. Ensure you have sudo access or use unprivileged modes.

**Issue: "Worker not found" in logs**
*   Check `runtime/logs/worker.log`. Ensure Redis is running (`sudo systemctl start redis`).

**Issue: LLM Errors (401/403)**
*   Check your `.env` file for correct API keys.
*   Ensure you have credits/quota.

For deeper debugging, refer to `docs/developer-guide.md`.
