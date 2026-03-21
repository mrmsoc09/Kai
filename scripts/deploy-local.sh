#!/usr/bin/env bash
# =============================================================================
# Kai Local Deployment Script
# Starts the full K1 stack using Docker Compose (developer mode).
#
# Usage:
#   ./scripts/deploy-local.sh              # start everything
#   ./scripts/deploy-local.sh --rebuild    # force rebuild images
#   ./scripts/deploy-local.sh --down       # stop and remove containers
#   ./scripts/deploy-local.sh --logs       # tail all logs
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.yml"
ENV_FILE="${REPO_ROOT}/.env"

cd "${REPO_ROOT}"

# -- Color helpers ------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[K1]${NC} $*"; }
warn()  { echo -e "${YELLOW}[K1]${NC} $*"; }
error() { echo -e "${RED}[K1]${NC} $*" >&2; }

# -- Parse args ---------------------------------------------------------------
REBUILD=false
DOWN=false
SHOW_LOGS=false
for arg in "$@"; do
  case "$arg" in
    --rebuild) REBUILD=true ;;
    --down)    DOWN=true ;;
    --logs)    SHOW_LOGS=true ;;
    --help|-h)
      echo "Usage: $0 [--rebuild] [--down] [--logs]"
      exit 0 ;;
    *)
      error "Unknown argument: $arg"; exit 1 ;;
  esac
done

# -- Sanity checks ------------------------------------------------------------
if ! command -v docker &>/dev/null; then
  error "docker not found. Install Docker Desktop or Docker Engine."
  exit 1
fi
if ! docker compose version &>/dev/null 2>&1; then
  error "docker compose (v2) not found. Upgrade Docker or install the plugin."
  exit 1
fi

# -- Down mode ----------------------------------------------------------------
if ${DOWN}; then
  info "Stopping K1 local stack..."
  docker compose -f "${COMPOSE_FILE}" down --remove-orphans
  info "Stack stopped."
  exit 0
fi

# -- Logs mode ----------------------------------------------------------------
if ${SHOW_LOGS}; then
  docker compose -f "${COMPOSE_FILE}" logs -f --tail=100
  exit 0
fi

# -- Env setup ----------------------------------------------------------------
if [[ ! -f "${ENV_FILE}" ]]; then
  warn ".env not found. Running setup wizard..."
  if [[ -f "${REPO_ROOT}/configure_k1.py" ]]; then
    python3 "${REPO_ROOT}/configure_k1.py"
  else
    warn "No configure_k1.py found. Copy .env.example to .env and edit it."
    if [[ -f "${REPO_ROOT}/.env.example" ]]; then
      cp "${REPO_ROOT}/.env.example" "${ENV_FILE}"
      warn "Copied .env.example to .env — edit it before running again."
      exit 1
    fi
  fi
fi

# Load .env (for display only — docker compose reads it automatically)
if [[ -f "${ENV_FILE}" ]]; then
  info "Loading .env from ${ENV_FILE}"
fi

# -- Validate critical vars ---------------------------------------------------
MISSING_VARS=()
for var in JWT_SECRET_KEY K1_DEV_TOKEN; do
  if [[ -z "${!var:-}" ]]; then
    # Try loading from .env file
    val=$(grep -E "^${var}=" "${ENV_FILE}" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
    if [[ -z "${val}" ]]; then
      MISSING_VARS+=("${var}")
    fi
  fi
done
if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
  warn "Missing env vars: ${MISSING_VARS[*]}"
  warn "These will use insecure defaults in development. Set them in .env for production."
fi

# -- Ensure artifact dirs exist -----------------------------------------------
mkdir -p artifacts/audit artifacts/usage artifacts/telemetry \
         artifacts/workflows artifacts/dork_runs output/logs
info "Artifact directories ready."

# -- Build and start ----------------------------------------------------------
BUILD_FLAGS=""
if ${REBUILD}; then
  BUILD_FLAGS="--build --force-recreate"
  info "Rebuilding images..."
fi

info "Starting K1 local stack (docker compose)..."
docker compose -f "${COMPOSE_FILE}" up -d ${BUILD_FLAGS}

# -- Wait for backend health --------------------------------------------------
info "Waiting for backend health check..."
MAX_WAIT=60
ELAPSED=0
until curl -sf http://localhost:8080/health >/dev/null 2>&1; do
  if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    error "Backend did not become healthy after ${MAX_WAIT}s."
    docker compose -f "${COMPOSE_FILE}" logs backend --tail=30
    exit 1
  fi
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done

info "K1 stack is up!"
echo ""
echo "  Backend API:  http://localhost:8080"
echo "  Frontend UI:  http://localhost:8081"
echo "  API Docs:     http://localhost:8080/docs"
echo "  Metrics:      http://localhost:8080/metrics"
echo ""
echo "  docker compose logs -f     # follow all logs"
echo "  docker compose ps          # check service status"
echo "  ./scripts/deploy-local.sh --down   # stop stack"
