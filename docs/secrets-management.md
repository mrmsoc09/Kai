# Secrets Management

## Rule: never commit real credentials

All secrets live in one of three places depending on the environment:

| Environment | Where secrets live |
|---|---|
| Local dev | `.env` (gitignored) |
| CI / staging | GitHub Actions secrets → injected as env vars at runtime |
| Production | HashiCorp Vault at `secret/k1/*` paths |

No plaintext credentials ever appear in `docker-compose.yml`, `Dockerfile`, or any version-controlled file.

---

## Local development quick-start

```bash
# 1. Copy the template
cp .env.example .env

# 2. Fill in your local test values — use throwaway credentials, not prod
#    Minimum required fields:
#      POSTGRES_PASSWORD=  (any value, e.g. "devpassword")
#      POSTGRES_USER=k1
#      POSTGRES_DB=k1
#      VAULT_TOKEN=       (use "root" when running Vault in dev mode)
#      K1_JWT_SECRET=     (any 32+ char random string)

# 3. Start services — compose reads .env automatically
./k1 start
```

The `.env` file is blocked by `.gitignore`. If you accidentally stage it, the pre-commit hook and the `detect-secrets` baseline check will both catch it.

---

## How docker-compose.yml uses secrets

`docker-compose.yml` uses `${VAR}` placeholders with `:?` guards for required secrets:

```yaml
postgres:
  environment:
    - POSTGRES_DB=${POSTGRES_DB:-k1}
    - POSTGRES_USER=${POSTGRES_USER:-k1}
    - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in .env}
```

The `:?` guard causes `docker compose` to **fail fast** with a clear error message if the variable is not set — preventing silent use of empty passwords.

**Why `DATABASE_URL` is constructed inline in compose (not taken from `.env`):**
The `DATABASE_URL` in `.env` uses `localhost` as the host (for host-side tools). Inside Docker, containers resolve each other by service name (`postgres`). Compose therefore constructs the URL with the literal `postgres` hostname rather than passing through `${DATABASE_URL}`.

---

## Production deployment (Vault)

CI uses the [hashicorp/vault-action](https://github.com/hashicorp/vault-action) GitHub Action to inject secrets at deploy time. No secrets are stored in the repo or in container images.

```yaml
- name: Import secrets from Vault
  uses: hashicorp/vault-action@v3
  with:
    url: ${{ secrets.VAULT_ADDR }}
    token: ${{ secrets.VAULT_TOKEN }}
    secrets: |
      secret/k1/db/postgres password | POSTGRES_PASSWORD ;
      secret/k1/db/postgres username | POSTGRES_USER ;
      secret/k1/auth/jwt key         | K1_JWT_SECRET
```

The KAI application service account is governed by `config/vault/kai-policy.hcl` — it can read `secret/k1/*` paths and renew its own token, and is denied everything else.

To provision a secret in Vault:

```bash
# One-time setup: write the KAI policy
vault policy write kai-app config/vault/kai-policy.hcl

# Write a secret
vault kv put secret/k1/db/postgres \
  password="<strong-password>" \
  username="k1" \
  dbname="k1"

# Rotate a secret without redeployment
vault kv patch secret/k1/db/postgres password="<new-password>"
# Then restart only the postgres-dependent containers:
docker compose restart orchestrator worker
```

---

## Secret scanning pipeline

Three layers catch secrets before they reach `main`:

### 1. Local pre-commit (runs on every `git commit`)

Install hooks once:
```bash
pip install pre-commit detect-secrets
pre-commit install
pre-commit install --hook-type pre-push  # installs TruffleHog for pushes
```

The `.pre-commit-config.yaml` runs:
- `detect-secrets` — entropy-based scan against `.secrets.baseline`
- `detect-private-key` — explicit private key header check
- `TruffleHog` (pre-push stage) — verified-credentials scan over new commits

### 2. Standalone script (run ad-hoc or in CI)

```bash
python scripts/pre-commit-check-secrets.py
```

Checks all staged files for high-entropy assignments and known credential patterns. Safe for files listed in its `SAFE_PATHS` set (`.env.example`, docs).

### 3. GitHub Actions (`.github/workflows/secrets-scan.yml`)

Runs automatically on every push and PR to `main`:
- **TruffleHog**: diff-based scan of new commits, verified secrets only
- **Compose validator**: rejects `docker-compose.yml` with non-`${VAR}` credential assignments
- **detect-secrets audit**: checks no new secrets have been introduced outside the baseline

---

## Updating the detect-secrets baseline

When you intentionally add a new file with example values (e.g., a test fixture), update the baseline so CI does not fail:

```bash
detect-secrets scan > .secrets.baseline
git add .secrets.baseline
git commit -m "chore: update secrets baseline"
```

Never add a real secret to the baseline — that just silences the alarm.
