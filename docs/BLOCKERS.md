# KAI Blockers

## Resolved

### 2026-03-05 | KAI-019 | Docker Compose E2E Smoke
- Resolution source: operator-executed validation in host shell.
- Evidence provided:
  - `k1_postgres` up and healthy
  - `k1_redis` up and healthy
  - `k1_backend` up with health check starting
  - compose attach/log invocation reached backend container
- Status: resolved for execution-plan closure.

## 2026-03-05 | KAI-019 | Docker Compose E2E Smoke

### Evidence
- `docker-compose -f docker-compose.dev.yml config -q` passes.
- `docker-compose -f docker-compose.dev.yml up -d postgres redis backend` fails with:
  - `docker.errors.DockerException: ... PermissionError(13, 'Permission denied')`
  - Cannot connect to Docker Unix socket from current execution context.
- Post-login verification:
  - `id` shows user groups do not include `docker`.
  - `/var/run/docker.sock` is `srw-rw---- root docker`.

### Why Blocked
- Full containerized smoke requires daemon-level Docker socket access.
- Current Codex execution runtime denies Docker daemon access even with escalated command execution and approved prefixes.
- Host shell user may be fixed, but the agent runtime context still cannot connect to `/var/run/docker.sock`.

### Options
1. Grant this environment membership/access to the Docker socket.
- Pros: enables true E2E compose smoke as requested.
- Cons: broader host-level privilege exposure.
2. Run the compose smoke in a CI runner with Docker-in-Docker and collect artifacts/logs.
- Pros: reproducible, auditable, no local privilege changes.
- Cons: slower feedback loop.
3. Accept static compose validation + non-container smoke as temporary fallback.
- Pros: immediate local verification.
- Cons: does not satisfy full runtime container orchestration validation.
4. Run the three compose commands in your shell and provide outputs for evidence closure.
- Pros: immediate unblock without changing agent sandbox/runtime policy.
- Cons: validation evidence is user-executed rather than agent-executed.

### Minimal Unblock Question
- Can you provide Docker daemon access for this environment (or direct me to a CI runner target) so I can complete `KAI-019` end-to-end compose smoke?
