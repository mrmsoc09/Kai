# Kai

Kai is a governance-first autonomous security research platform for authorized recon, triage, evidence collection, report generation, and mission orchestration. It runs locally on Ubuntu, self-hosts cleanly on a dedicated server, and deploys into cloud or private infrastructure without changing the operator workflow.

At a glance:

- scope-aware opportunity intake
- role-based LLM routing
- live recon with explicit authorization gates
- deterministic evidence and report generation
- SSD-backed persistent storage
- local, self-hosted, and cloud deployment paths

## What Kai Does

- Discovers and queues opportunities for recon and validation.
- Runs live scans only when scope, authorization, and policy gates allow it.
- Uses role-based LLM routing for bulk reasoning, coding, premium escalation, and opportunistic lower-cost routes.
- Captures evidence, logs, timelines, reports, and mission artifacts in a durable store.
- Generates structured reports with reproducible context and audit history.
- Supports local, self-hosted, and cloud-style deployments with the same core stack.

## Core Flow

Kai turns a scoped target into a reviewable outcome through a repeatable pipeline:

1. Import or define an opportunity.
2. Resolve scope and authorization.
3. Route the task to the correct model and toolchain.
4. Execute recon and validation with logging, evidence capture, and rate limits.
5. Synthesize findings into submission-ready reports.
6. Persist artifacts, telemetry, and audit trails to durable storage.

This keeps the workflow in one place and removes the usual switching cost between scanning, note taking, evidence handling, and report drafting.

## Core Capabilities

| Capability | What it covers |
|---|---|
| Mission orchestration | Phase-based workflows, tool execution, approvals, retries, and handoffs |
| Opportunity management | Queueing, approval, execution, and status tracking for scoped targets |
| Live recon | Passive and active recon with explicit scope and authorization gates |
| Evidence pipeline | Screenshots, logs, scripts, bundles, hashes, and report lineage |
| Report generation | Deterministic report synthesis with exportable outputs |
| Model routing | OpenRouter-first role-based routing with local fallback support |
| Observability | Audit logs, telemetry, event streams, and metrics |
| Storage control | External SSD-backed persistence for artifacts, logs, caches, and runtime state |

## How Kai Produces Output

Kai’s output is produced by a chain of controlled steps, not by one monolithic prompt:

1. **Opportunity intake** - a target, finding, or report idea enters the system.
2. **Scope resolution** - Kai checks allowlists, exclusions, and program authorization.
3. **Model selection** - the router chooses a role-appropriate model based on the task.
4. **Tool selection** - the governance layer exposes only the tools allowed for that phase.
5. **Execution** - workers run scans, collection, or analysis in bounded steps.
6. **Evidence capture** - artifacts, logs, and hashes are written to persistent storage.
7. **Synthesis** - reports and summaries are generated from structured evidence.
8. **Export** - operators can review, refine, and submit the result.

That pipeline is what makes the platform useful in practice: repeatable inputs, controlled execution, and reviewable outputs.

## Deployment Models

Kai supports three practical deployment patterns:

| Mode | Best for | Runtime shape |
|---|---|---|
| Local workstation | Development and lightweight research | Docker on the same machine, fast iteration, SSD-backed storage |
| Self-hosted server | Dedicated Ubuntu box or private lab | Same stack, persistent `/srv/kai` storage, optional reverse proxy |
| Cloud VM | Remote Ubuntu instance with persistent disk | Same stack, cloud networking, TLS termination at the edge |

All three use the same codebase and the same environment variables.

## Quick Start

### 1. Download the repository

```bash
git clone https://github.com/mrmsoc09/Kai.git
cd Kai
git submodule update --init --recursive
```

### 2. Create configuration

```bash
cp .env.example .env
```

Edit `.env` before starting the platform. At minimum, set the database password, JWT secret, storage root, and the model provider credentials you intend to use.

### 3. Bootstrap Docker and core services

```bash
sudo ./bootstrap.sh
```

### 4. Start the local UI and API stack

```bash
./k1 start
```

### 5. Verify

```bash
curl http://localhost:8080/health
```

Open the UI at `http://localhost:8081`.

## Self-Hosted and Cloud Setup

For a self-hosted Ubuntu server or a cloud VM, the recommended pattern is:

1. Provision Ubuntu 22.04 or 24.04.
2. Attach a persistent disk or SSD for Kai state.
3. Mount that disk at `/srv/kai`.
4. Clone this repository.
5. Copy `.env.example` to `.env` and fill in the runtime settings.
6. Set `KAI_STORAGE_ROOT=/srv/kai`.
7. Set `OPENROUTER_API_KEY` if you are using OpenRouter inference.
8. Run `sudo ./bootstrap.sh`.
9. Run the appropriate compose entrypoint for your deployment model.

If you are deploying behind a reverse proxy, terminate TLS at the proxy and forward traffic to the backend and frontend services.

For the production-style compose stack:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

For the local full-stack compose path:

```bash
./scripts/deploy-local.sh --rebuild
```

For the dev-oriented workflow:

```bash
./k1 start
```

## Recommended Storage Layout

Kai is designed to keep its persistent state on an external SSD or dedicated volume.

Recommended root:

```text
/srv/kai
```

Recommended subpaths:

- `/srv/kai/artifacts`
- `/srv/kai/output`
- `/srv/kai/docker/postgres`
- `/srv/kai/docker/redis`
- `/srv/kai/docker/qdrant`
- `/srv/kai/docker/frontend-node_modules`

This layout keeps logs, reports, queue state, caches, and database data off the system disk.

See [docs/artifact-storage.md](docs/artifact-storage.md) for the storage initialization and cleanup workflow.

## Configuration

Start with `.env.example`. The most important settings are grouped below.

### Core runtime

- `KAI_STORAGE_ROOT=/srv/kai`
- `K1_ARTIFACTS_HOST_ROOT=/srv/kai/artifacts`
- `K1_WORKFLOW_OUTPUT_ROOT=/srv/kai/output`
- `DATABASE_URL=...`
- `POSTGRES_PASSWORD=...`
- `REDIS_URL=...`

### LLM routing

- `KAI_MODEL_PROVIDER=openrouter`
- `OPENROUTER_API_KEY=...`
- `KAI_OPENROUTER_DISCOVERY_ENABLED=true`
- `KAI_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`
- `KAI_LOCAL_LLM_BASE_URL=...`
- `KAI_MODEL_ROUTE_BULK=deepseek/deepseek-v4-flash`
- `KAI_MODEL_ROUTE_CODING=qwen/qwen3.5-27b`
- `KAI_MODEL_ROUTE_PREMIUM=moonshotai/kimi-k2.5`
- `KAI_MODEL_ROUTE_FREE_PREMIUM=moonshotai/kimi-k2.6:free`

### Security and scope

- `JWT_SECRET_KEY=...`
- `CORS_ALLOWED_ORIGINS=...`
- `K1_SECRET_BACKEND=env|vault`
- `K1_SCOPE_POLICY_PATH=config/scope_guardrails.yaml`
- `K1_ENFORCE_SOVEREIGN_NETWORK=true`

### Tooling and workflow

- `K1_TOOL_REGISTRY_PATH=tools/registry/tool_registry.yaml`
- `K1_ARTIFACT_RETENTION_DAYS=14`
- `K1_ARTIFACT_MAX_BYTES_PER_TOOL=107374182400`

The complete and current list is documented in [.env.example](.env.example).

## Model Strategy

Kai is built around role-based model routing instead of hard-coded one-off model names.

Default strategy:

- Bulk reasoning: DeepSeek V4 Flash
- Coding and repo work: Qwen 3.5 family
- Premium escalation: Kimi K2.5
- Opportunistic free premium lane: Kimi K2.6 free when available
- Local fallback: OpenAI-compatible endpoints such as Ollama, vLLM, SGLang, or LM Studio

This keeps the system cost-aware while still allowing stronger reasoning where the task requires it.

## Safety, Scope, and Authorization

Kai is intended for authorized security research only.

- Live recon requires scope resolution.
- Targets are not promoted to active scanning just because they were discovered passively.
- High-impact tools require explicit approval or approved profiles.
- Audit logs and event traces are written for every important action.
- The platform is designed to fail closed when scope or authorization is unclear.

If you are using Kai against a bug bounty program, import the program scope first and use the scope policy as the source of truth.

## Pro Modules

The repository contains the self-hostable core platform. Optional Pro modules extend the same governance, storage, and reporting flow for teams that want more specialization.

Typical Pro extensions include:

- trained agents for specific tools or phases
- higher-capacity report synthesis workflows
- specialized reconciliation and validation agents
- team-oriented routing and policy packs

These are add-ons, not separate products, so operators keep the same workflow and state model while gaining more automation depth.

## Key Documentation

- [docs/deployment.md](docs/deployment.md) - install, runtime, and deployment flow
- [docs/operator-guide.md](docs/operator-guide.md) - UI and operator workflow
- [docs/model-routing.md](docs/model-routing.md) - OpenRouter and local model routing
- [docs/artifact-storage.md](docs/artifact-storage.md) - SSD-backed persistent storage
- [docs/security-architecture.md](docs/security-architecture.md) - safety and policy model
- [docs/api-reference.md](docs/api-reference.md) - backend API surface

## Repository Layout

- `apps/backend` - FastAPI backend, workers, orchestration, and policy layers
- `apps/frontend` - frontend application
- `docker*` - Dockerfiles and compose files
- `scripts` - bootstrap, deployment, cleanup, and validation scripts
- `docs` - architecture, deployment, operator, and security documentation
- `orchestration` - agent/persona definitions and workflow orchestration assets
- `tools` - tool wrappers, configs, and integration assets

## Troubleshooting

- If Docker startup fails, run `sudo ./bootstrap.sh` again and inspect `output/logs/bootstrap.log`.
- If storage paths are wrong, verify that `/srv/kai` is mounted and that `.env` sets `KAI_STORAGE_ROOT=/srv/kai`.
- If models fail to route, confirm `OPENROUTER_API_KEY` and check `KAI_MODEL_PROVIDER`.
- If the backend fails on startup, check database connectivity and migration state.
- If live recon is blocked, verify the scope policy and program authorization inputs.

## License

See [LICENSE](LICENSE).
