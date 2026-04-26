# Bug Bounty Preflight Behavior

## Readiness and Missing Credentials

`BugBountyHuntingService.evaluate_readiness()` now treats missing catalog/API credentials as a warning by default.

- Decision remains `READY` when scope/safety/health checks pass.
- Response details include:
  - `details.credentials.missing_keys`
  - `details.credentials.setup_hints` (signup URLs/instructions when available)
  - `details.credentials.missing_required_credentials`
- The workflow can continue with fallback modes (typically `unauthenticated`) and credential-gated steps are skipped by workflow mode filtering.

Strict behavior is still available:

- Set `block_on_missing_credentials: true` in either:
  - schedule config (`hunt_schedule_jobs.config_json`)
  - program opportunity config (`program.config_json.opportunity`)
- In strict mode, readiness returns `BLOCKED_BY_CONFIG` when required keys are missing.

## Platform Preflight Enrichment (HackerOne)

`POST /api/v1/bug-bounty/programs/import` supports optional platform enrichment fields:

- `auto_fetch_platform_data` (default `true`)
- `allow_partial_platform_data` (default `true`)
- `platform_api_key`
- `platform_api_secret`

When `platform=hackerone` and API credentials are provided, import attempts to:

1. Fetch program policy + structured scope via HackerOne API.
2. Merge discovered scope assets into canonical in-scope/out-of-scope targets.
3. Extract policy/guideline links for artifact tracking.
4. Persist enrichment status/warnings under `program.config_json.opportunity.platform_enrichment`.

If request credentials are omitted, enrichment also checks secret-manager keys:

- `HACKERONE_API_KEY` (or `H1_API_KEY`)
- `HACKERONE_API_SECRET` (or `H1_API_SECRET`)

If enrichment is unavailable, import continues by default and records warnings (no hard stop).

## Access Metadata Defaults

Program import now auto-seeds access metadata (when missing) so UI/API can guide credential onboarding:

- Always seeds `unauthenticated`.
- Seeds HackerOne defaults for `user_account`, `api_key`, and `hunter_account`.
- This enables `GET /api/v1/credentials/{program_id}/scanning-modes` to return actionable signup links.
