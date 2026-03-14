# Kai Frontend Operator Console

Canonical analyst/operator cockpit for Kai.

## Local Run

From repo root:

```bash
cd apps/frontend-operator
npm install
npm run dev
```

Default URL: `http://localhost:3000` (or `http://localhost:8081` when started via `docker-compose.dev.yml`).

## Required Backend

The console expects the backend API at:

- `NEXT_PUBLIC_API_BASE_URL` (default: `http://localhost:8080`)

## Auth Configuration

Most backend routes are bearer-protected.

Supported frontend auth options:

1. `NEXT_PUBLIC_API_BEARER_TOKEN`
   - direct access token used on every request.

2. `NEXT_PUBLIC_K1_DEV_BOOTSTRAP_TOKEN`
   - development bootstrap token (`K1_DEV_TOKEN`) used to call `/auth/login`.
   - obtained access token is cached in browser localStorage key `k1_access_token`.

If both are set, `NEXT_PUBLIC_API_BEARER_TOKEN` takes precedence.

## Validation

```bash
npm run typecheck
npm test
npm run build
```
