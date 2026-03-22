#!/usr/bin/env bash
# =============================================================================
# Kai Production Deployment Script
# Builds and starts the K1 stack using the production Docker Compose file.
#
# Required .env.prod variables:
#   POSTGRES_PASSWORD   — strong random password
#   REDIS_PASSWORD      — strong random password (optional)
#   JWT_SECRET_KEY      — cryptographically random, min 32 chars
#   K1_DEV_TOKEN        — operator access token (set to empty in prod if unused)
#   CORS_ALLOWED_ORIGINS — comma-separated allowed origins
#   ANTHROPIC_API_KEY   — (or another LLM provider key)
#
# Usage:
#   ./scripts/deploy-prod.sh                     # deploy / upgrade
#   ./scripts/deploy-prod.sh --env .env.staging  # custom env file
#   ./scripts/deploy-prod.sh --down              # stop production stack
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.prod.yml"
ENV_FILE="${REPO_ROOT}/.env.prod"

cd "${REPO_ROOT}"

# -- Color helpers ------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[K1-PROD]${NC} $*"; }
warn()  { echo -e "${YELLOW}[K1-PROD]${NC} $*"; }
error() { echo -e "${RED}[K1-PROD]${NC} $*" >&2; }

compose_cmd() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "docker compose"
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
    return 0
  fi
  return 1
}

# -- Parse args ---------------------------------------------------------------
DOWN=false
for arg in "$@"; do
  case "$arg" in
    --down)      DOWN=true ;;
    --env)       shift; ENV_FILE="$1" ;;
    --help|-h)
      echo "Usage: $0 [--down] [--env <env-file>]"
      exit 0 ;;
  esac
done

# -- Sanity checks ------------------------------------------------------------
if ! command -v docker &>/dev/null; then
  error "docker not found."
  exit 1
fi
COMPOSE_BIN="$(compose_cmd || true)"
if [[ -z "${COMPOSE_BIN}" ]]; then
  error "Neither 'docker compose' nor 'docker-compose' is available."
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  error "Production env file not found: ${ENV_FILE}"
  error "Create it with the required variables listed in this script's header."
  exit 1
fi

# -- Down mode ----------------------------------------------------------------
if ${DOWN}; then
  info "Stopping production stack..."
  ${COMPOSE_BIN} -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" down
  info "Production stack stopped."
  exit 0
fi

# -- Validate required secrets ------------------------------------------------
REQUIRED_VARS=(POSTGRES_PASSWORD JWT_SECRET_KEY CORS_ALLOWED_ORIGINS)
MISSING=()
while IFS='=' read -r key val; do
  [[ "$key" =~ ^# ]] && continue
  [[ -z "$key" ]] && continue
  export "$key=${val}"
done < "${ENV_FILE}"

for var in "${REQUIRED_VARS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    MISSING+=("$var")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  error "Missing required variables in ${ENV_FILE}: ${MISSING[*]}"
  exit 1
fi

# Warn if JWT secret is too short
JWT_LEN=${#JWT_SECRET_KEY}
if [[ $JWT_LEN -lt 32 ]]; then
  error "JWT_SECRET_KEY must be at least 32 characters. Got $JWT_LEN."
  exit 1
fi

# Warn on insecure defaults
if [[ "${JWT_SECRET_KEY}" == "super-secret-jwt-key" ]]; then
  error "JWT_SECRET_KEY is set to the insecure default. Generate a new secret."
  exit 1
fi

# -- Ensure artifact directories ----------------------------------------------
mkdir -p artifacts/audit artifacts/usage artifacts/telemetry \
         artifacts/workflows artifacts/dork_runs output/logs
info "Artifact directories ready."

# -- Pull images (if registry is set) -----------------------------------------
# docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" pull

# -- Build images -------------------------------------------------------------
info "Building production images..."
${COMPOSE_BIN} -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" build \
  --build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --no-cache

# -- Deploy -------------------------------------------------------------------
info "Deploying production stack..."
${COMPOSE_BIN} -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d --remove-orphans

# -- Wait for health ----------------------------------------------------------
info "Waiting for backend health..."
MAX_WAIT=90
ELAPSED=0
BACKEND_PORT=8080
until curl -sf "http://localhost:${BACKEND_PORT}/health" >/dev/null 2>&1; do
  if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    error "Backend did not become healthy after ${MAX_WAIT}s."
    ${COMPOSE_BIN} -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" logs backend --tail=50
    exit 1
  fi
  sleep 3
  ELAPSED=$((ELAPSED + 3))
done

info "Production deployment complete!"
echo ""
echo "  Stack:        ${COMPOSE_BIN} -f docker-compose.prod.yml ps"
echo "  Logs:         ${COMPOSE_BIN} -f docker-compose.prod.yml logs -f"
echo "  Health:       curl http://localhost:${BACKEND_PORT}/health"
echo "  Metrics:      curl http://localhost:${BACKEND_PORT}/metrics"
echo ""
warn "Reminder: Ensure Vault is unsealed and tool credentials are loaded."
warn "Run: ${COMPOSE_BIN} -f docker-compose.prod.yml logs vault  to verify."
