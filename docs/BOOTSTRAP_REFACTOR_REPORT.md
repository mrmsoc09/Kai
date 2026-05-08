# Bootstrap Auth Hardening and Dev Certificate Migration

This document describes the changes made to remove unsafe bootstrap auth from production and to replace hardcoded development tokens with temporary signed certificates.

## What changed

- Added `K1_ENABLE_BOOTSTRAP_AUTH_BUILD` as a build-time flag.
  - This flag is injected by `Dockerfile.backend` and defaults to `false` in the production backend image.
  - When disabled, bootstrap admin creation and bootstrap token/certificate login paths are inactive.

- Hardened `apps/backend/src/auth/bootstrap.py`.
  - `K1_BOOTSTRAP_ADMIN_ENABLED` now requires `K1_ENABLE_BOOTSTRAP_AUTH_BUILD=true`.
  - This prevents bootstrap admin creation in production image builds even if the runtime env var is set.

- Hardened `apps/backend/src/core/auth.py`.
  - Bootstrap token login is now gated behind `K1_ENABLE_BOOTSTRAP_AUTH_BUILD=true`.
  - Added dev-only certificate authentication support using `K1_DEV_CERT_AUTH_ENABLED=true`.
  - Added CA path configuration via `K1_DEV_AUTH_CA_PATH`, defaulting to `dev-certs/ca.crt.pem`.

- Added `scripts/validate_bootstrap_env.py`.
  - Scans `.env`, `.env.example`, `docker-compose.yml`, and additional files for unsafe bootstrap variables.
  - Optionally validates the active environment with `--check-env`.

- Added `scripts/dev_auth_cert.py`.
  - Generates a temporary signing CA and client certificate for local development.
  - Uses OpenSSL to create private keys and short-lived certs.

- Added GitHub Actions workflow `.github/workflows/validate-no-bootstrap-auth.yml`.
  - Validates forbidden bootstrap auth variables in repo files and the current environment.
  - Builds the backend container with bootstrap disabled and verifies the built image environment does not include `K1_ENABLE_BOOTSTRAP_AUTH` or `K1_DEV_TOKEN`.

## Developer migration steps

1. Generate local dev certificates:

```bash
python scripts/dev_auth_cert.py --output-dir dev-certs --days 7
```

2. Enable dev cert login for local development only:

```bash
export K1_DEV_CERT_AUTH_ENABLED=true
export K1_DEV_AUTH_CA_PATH=dev-certs/ca.crt.pem
```

3. Submit the signed certificate PEM to the new dev login endpoint:

- `POST /auth/token/dev-cert`
- Body JSON: `{ "client_certificate_pem": "<PEM contents>" }`

4. Avoid setting `K1_DEV_TOKEN` or `K1_ENABLE_BOOTSTRAP_AUTH` in production.

## Production safety

- Production builds should use:
  - `--build-arg K1_ENABLE_BOOTSTRAP_AUTH_BUILD=false`
  - `ENVIRONMENT=production`
  - no `K1_DEV_TOKEN`
  - no `K1_BOOTSTRAP_ADMIN_ENABLED`

- The CI workflow now prevents merge if any forbidden bootstrap env variables leak into repo or image metadata.
