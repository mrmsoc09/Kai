Dev Stack Bring-Up and E2E Smoke (Docker)

Manual (you do):
1) Use a Linux host with 8GB+ RAM and open ports 5432, 6333, 6379, 8200, 9200, 9042, 9000, 8080, 16686.
2) If Docker is missing, run: sudo bash k1/scripts/bootstrap_docker_host.sh (log out/in after).
3) Prepare env: copy any required .env files for backend and set secrets (Postgres, Vault dev token, TheHive admin, JWT, etc.).
4) Bring up stack: bash k1/scripts/stack_up.sh
5) Run smoke: bash k1/scripts/smoke_e2e.sh
6) Optional real target after scope approval: TARGET=<google_bbp_url> ACCEPT_SCOPE=1 bash k1/scripts/smoke_e2e.sh

Autonomous (system does):
- Starts all compose services and waits for health where possible.
- Verifies infra endpoints and backend health.
- Exercises HiL request path (if backend is up).
- Enforces scope: no external execution unless ACCEPT_SCOPE=1 and explicit TARGET.
- Prints container statuses and hints for logs.

Notes:
- TheHive may require first-time UI setup; complete admin onboarding if prompted.
- For production, replace dev tokens/passwords and disable Vault dev mode.
