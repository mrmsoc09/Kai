# Kai MVP Readiness Gap Report (2026-03-14)

## Executive Summary

Kai is **close but not yet MVP-ready** for external/operator testing.  
Core backend and frontend test suites pass in the project venv, but the end-to-end operator path still has critical friction:

- authenticated API surfaces are not wired in frontend/CLI clients,
- default startup path runs the legacy frontend instead of `apps/frontend-operator`,
- first-run DB migration and demo-data flow are not consolidated into one repeatable path.

## Validation Snapshot

- Backend tests (project venv): `.venv/bin/python -m pytest -q` -> **305 passed, 1 skipped**
- Frontend operator:
  - `npm run typecheck` -> **pass**
  - `npm test` -> **pass** (24 tests)
  - `npm run build` -> **pass**
- System Python (without project deps): `python3 -m pytest -q` fails at import (`anyio` missing), confirming setup dependency sensitivity.

## Area-by-Area Readiness

### 1. Installation / Setup Experience

Current state:
- Multiple startup paths exist (`README.md`, `k1`, docker compose, scripts), with conflicting defaults.
- `docker-compose.dev.yml` starts `apps/frontend` (legacy), not `apps/frontend-operator`.

Impact:
- First-time reviewers can boot a stack that does not expose the intended analyst cockpit.

### 2. Environment Configuration

Current state:
- `.env.example` is comprehensive, but no minimal MVP env profile is defined.
- Auth variables exist (`K1_DEV_TOKEN`, `JWT_SECRET_KEY`), but operator-facing auth flow is not documented.

Impact:
- Configuration is possible, but high-friction and easy to misconfigure for first-time evaluators.

### 3. Backend / Frontend Run Path

Current state:
- Backend runs via `uvicorn` and passes tests.
- Analyst cockpit exists under `apps/frontend-operator`, but compose/default scripts do not make it the canonical frontend.

Impact:
- MVP demo path is not one-command reproducible.

### 4. Database / Migrations

Current state:
- Alembic migrations exist through `0011`.
- Main setup docs do not present a canonical "run migrations now" step in the primary onboarding path.

Impact:
- Fresh environments can boot services but fail at first data operations if migrations were skipped.

### 5. Seed / Demo Data

Current state:
- No committed demo seed payload/script for a deterministic bug bounty walkthrough.
- Program import examples exist in docs only.

Impact:
- Reviewers may see empty dashboards unless they manually craft API payloads and run workflows successfully.

### 6. Workflow Launch UX and End-to-End Operator Flow

Current state:
- Campaign and bug bounty surfaces are implemented.
- Many core APIs require auth (`Depends(get_current_user)`), but:
  - `apps/frontend-operator/lib/api/client.ts` sends no auth header,
  - CLI bug-bounty client code sends no auth header,
  - CLI defaults to `http://localhost:8000` while backend docs/start paths use `8080`.

Impact:
- Core operator actions fail in realistic runtime unless users manually patch auth behavior.

### 7. Alert/Case/Recommendation Workflow

Current state:
- Backend models/routes and frontend pages exist and test at component/page level.
- No documented, deterministic way to populate alerts/cases/recommendations for a demo run.

Impact:
- Functionality is implemented, but hard to validate operationally in a fresh environment.

### 8. Documentation Quality / Consistency

Current state:
- Documentation is extensive but inconsistent:
  - README still frames `apps/frontend` as frontend,
  - operator docs reference `apps/frontend-operator`,
  - configuration docs still contain stale statements (for example strict allowlist default mismatch text),
  - CLI URL defaults and docs are not aligned.

Impact:
- High cognitive load and onboarding risk for MVP reviewers.

## Prioritized Blocker List

## Must Fix for MVP

1. **Canonical auth wiring for operator clients**
   - Add authenticated request handling for `apps/frontend-operator` API client.
   - Add auth support to CLI HTTP clients (at minimum bearer token env/config).
   - Document dev login/token acquisition path (`/auth/login`) and expected header usage.

2. **Unify canonical run path to analyst cockpit**
   - Make `apps/frontend-operator` the default frontend in local stack/docs.
   - Ensure startup scripts and docs point to one canonical URL/port model.

3. **Standardize first-run DB boot**
   - Add explicit required migration step in primary setup flow.
   - Provide one canonical command sequence that includes migrations.

4. **Provide deterministic MVP demo seed flow**
   - Add a safe seed path to create:
     - one program,
     - one monitored target,
     - one schedule or direct run trigger,
     - minimal candidate/alert/case artifacts for GUI verification.

## Should Fix for MVP

1. **Resolve port/default mismatches**
   - Align CLI defaults (`8000`) with backend defaults/docs (`8080`) or centralize config.

2. **Consolidate stale scripts**
   - Decommission or clearly mark legacy scripts (`scripts/smoke_e2e.sh`, legacy frontend smoke paths).
   - Keep one canonical smoke script for MVP validation.

3. **Document minimal env profile**
   - Publish "minimum required vars for local MVP demo" separate from full `.env.example`.

4. **Add one integration-level E2E test path**
   - Program import -> schedule trigger/run -> candidate generation -> alert sync -> case creation (API-level).

5. **Frontend operator run docs**
   - Add `apps/frontend-operator/README.md` with exact local run instructions and auth configuration.

## Nice to Have Later

1. Frontend-native program import/schedule creation wizard.
2. Report draft file viewer/download UX from cockpit.
3. Pagination + saved filters across large operational tables.
4. CI job adding frontend build/test gates alongside backend quality.

## Recommended MVP Scope Definition

MVP should explicitly include only:

- authenticated local operator workflow,
- bug bounty program import (manual JSON),
- monitored target management,
- one safe workflow trigger path (manual trigger or run-due),
- persisted outputs in DB + `output/*`,
- analyst cockpit visibility for:
  - overview/programs/targets/opportunities/predictions/triage,
  - alerts/cases/case detail,
  - system health,
- deterministic report draft generation from candidate queue.

Out of MVP scope:

- external auto-submission,
- broad autonomous escalation tuning,
- production-grade distributed scaling features beyond local single-node validation.

## Recommended MVP Demo/Test Flow

1. **Setup**
   - Create venv and install deps.
   - Configure `.env`.
   - Start postgres/redis (and backend/worker).
   - Run `alembic upgrade head`.

2. **Auth bootstrap**
   - Obtain access token via `/auth/login` using `K1_DEV_TOKEN`.
   - Configure CLI/frontend to send bearer token.

3. **Program + scope**
   - Import one program with in-scope/out-of-scope assets.
   - Verify targets list.

4. **Execution**
   - Create one schedule on in-scope target (`safe_mode=true`).
   - Trigger run (`trigger` or `run-due`).
   - Confirm readiness records and workflow run persistence.

5. **Analysis artifacts**
   - Verify deltas/candidates appear.
   - Run alert sync.
   - Create/transition a case from alert.
   - Generate candidate report draft.

6. **GUI verification (`apps/frontend-operator`)**
   - Confirm visibility across overview, opportunities, triage, alerts, cases, system.
   - Confirm status/score/reasoning/evidence fields are readable and linked.

7. **Repeatability check**
   - Re-run with same target and verify deterministic persistence + observable deltas/case transitions.

## Final Readiness Verdict

**Not yet MVP-ready** until the Must Fix items above are closed.  
After those are resolved, Kai can be presented as a testable MVP for operator/reviewer evaluation.
