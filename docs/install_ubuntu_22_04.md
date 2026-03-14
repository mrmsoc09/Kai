# Install on Ubuntu 22.04

## 1. Clone and enter repository

```bash
git clone <repo-url>
cd Kai
```

## 2. Bootstrap host dependencies

```bash
sudo bash install/bootstrap_ubuntu_22_04.sh
```

This script installs core packages and performs best-effort installation for common recon/scanning tooling.

## 3. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # test tooling
```

## 4. Configure environment

```bash
cp .env.mvp.example .env
```

Set at least:

- `DATABASE_URL` — e.g. `postgresql+asyncpg://k1:k1pass@localhost:5432/k1`
- `REDIS_URL` — e.g. `redis://localhost:6379/0`
- `K1_DEV_TOKEN` — local development login token for `/auth/login`
- `JWT_SECRET_KEY` / `K1_JWT_SECRET` — any long random string for signing JWT tokens
- optional API keys (`SHODAN_API_KEY`, `CENSYS_API_ID`, `CENSYS_API_SECRET`)

## 5. Verify tool installation

```bash
python3 scripts/verify_tool_registry_install.py
```

Verification report is written to:

- `output/reports/tool_install_verification.json`

## 6. Start dependencies

```bash
docker-compose -f docker-compose.dev.yml up -d
```

## 7. Apply database migrations

```bash
alembic upgrade head
```

## 8. Development auth bootstrap (required for protected APIs)

```bash
curl -sS -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$K1_DEV_TOKEN\"}"
```

Use returned `access_token` as bearer token for CLI/API and optionally set:

- `NEXT_PUBLIC_API_BEARER_TOKEN=<access_token>` or
- `NEXT_PUBLIC_K1_DEV_BOOTSTRAP_TOKEN=<K1_DEV_TOKEN>`

## 9. Run backend tests

```bash
python3 -m pytest -q
```

## 10. Run workflow smoke test

```bash
bash scripts/smoke_test_workflow.sh example.com workflow_recon_surface_map
```

## 11. Start frontend operator console

```bash
cd apps/frontend-operator
npm install
npm run dev
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'yaml'`

Install the runtime requirements into the active virtualenv:

```bash
pip install -r requirements.txt
```

### `Tool catalog not found: tools/registry/tool_registry.yaml`

The registry YAML is resolved relative to the repo root. Run pytest from the repo root, or set `K1_TOOL_REGISTRY_PATH` to the absolute path.

### Docker compose errors on startup

Ensure Docker and Docker Compose v2 are installed:

```bash
docker --version
docker compose version
```

The dev stack requires Docker Compose v2 (bundled with Docker Desktop 4+). If `docker-compose` (v1) is installed, replace `docker-compose` with `docker compose` in all commands.

### Tests fail with `ModuleNotFoundError: No module named 'pydantic'`

Install all runtime dependencies, not just dev tooling:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### Scope guardrails blocking targets

The default `config/scope_guardrails.yaml` ships with `strict_allowlist: true`, so targets not matching the allowlist are blocked. Populate `allowlist` with authorized scope entries:

```yaml
allowlist:
  - "*.example.com"
denylist:
  - "*.internal"
  - "localhost"
  - "127.0.0.1"
strict_allowlist: true
safe_mode_default: true
```

### Binary not found in PATH

Run the verification script to identify which tools are missing:

```bash
python3 scripts/verify_tool_registry_install.py
```

Install missing tools per their official instructions or use the Docker worker image which bundles the full toolset.
