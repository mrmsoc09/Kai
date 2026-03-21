#!/usr/bin/env bash
# Kai runtime start.
# Usage: ./scripts/k1-start.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

BOOTSTRAP_MARKER="runtime/.bootstrap_ready"
BACKEND_PID_FILE="runtime/pids/backend.pid"
WORKER_PID_FILE="runtime/pids/worker.pid"
UI_PID_FILE="runtime/pids/ui.pid"
BACKEND_LOG="runtime/logs/backend.log"
WORKER_LOG="runtime/logs/worker.log"
UI_LOG="runtime/logs/ui.log"

info() { echo -e "${GREEN}[k1-start]${NC} $*"; }
warn() { echo -e "${YELLOW}[k1-start]${NC} $*"; }
error() { echo -e "${RED}[k1-start]${NC} $*" >&2; }

has_cmd() {
    command -v "$1" >/dev/null 2>&1
}

read_env_value() {
    local key="$1"
    local default="$2"
    local value=""
    if [[ -f .env ]]; then
        value="$(grep -E "^${key}=" .env | tail -n 1 | cut -d= -f2- || true)"
        value="${value%\"}"
        value="${value#\"}"
    fi
    if [[ -n "${value}" ]]; then
        echo "${value}"
    else
        echo "${default}"
    fi
}

pid_is_running() {
    local pid="$1"
    kill -0 "${pid}" >/dev/null 2>&1
}

start_service() {
    local name="$1"
    local pid_file="$2"
    local log_file="$3"
    shift 3

    if [[ -f "${pid_file}" ]]; then
        local existing_pid
        existing_pid="$(cat "${pid_file}")"
        if [[ -n "${existing_pid}" ]] && pid_is_running "${existing_pid}"; then
            info "${name} already running (PID ${existing_pid})."
            return 0
        fi
        warn "Removing stale PID file for ${name} (${pid_file})."
        rm -f "${pid_file}"
    fi

    info "Starting ${name}..."
    nohup "$@" >"${log_file}" 2>&1 &
    local new_pid=$!
    echo "${new_pid}" > "${pid_file}"
    sleep 1
    if ! pid_is_running "${new_pid}"; then
        error "${name} failed to start. See ${log_file}"
        tail -n 40 "${log_file}" || true
        return 1
    fi
    info "${name} started (PID ${new_pid})."
}

wait_for_http() {
    local url="$1"
    local timeout="${2:-60}"
    local elapsed=0
    until curl -fsS "${url}" >/dev/null 2>&1; do
        sleep 2
        elapsed=$((elapsed + 2))
        if [[ "${elapsed}" -ge "${timeout}" ]]; then
            return 1
        fi
    done
    return 0
}

wait_for_port() {
    local host="$1"
    local port="$2"
    local timeout="${3:-45}"
    python3 - "$host" "$port" "$timeout" <<'PY'
import socket
import sys
import time

host = sys.argv[1]
port = int(sys.argv[2])
timeout = int(sys.argv[3])
deadline = time.time() + timeout
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            raise SystemExit(0)
    except OSError:
        time.sleep(1)
raise SystemExit(1)
PY
}

if [[ ! -f "${BOOTSTRAP_MARKER}" ]]; then
    error "Bootstrap marker not found (${BOOTSTRAP_MARKER})."
    error "Run ./bootstrap.sh before starting Kai."
    exit 1
fi

if [[ ! -d .venv ]]; then
    error "Missing .venv. Run ./bootstrap.sh first."
    exit 1
fi

if [[ ! -f .env ]]; then
    error "Missing .env. Run ./bootstrap.sh first."
    exit 1
fi

source .venv/bin/activate
export PATH="${HOME}/.local/bin:${PATH}"
mkdir -p runtime/logs runtime/pids

BACKEND_HOST="$(read_env_value BACKEND_HOST 0.0.0.0)"
BACKEND_PORT="$(read_env_value BACKEND_PORT 8080)"
FRONTEND_URL="$(read_env_value FRONTEND_URL http://localhost:8081)"
UI_PORT="$(FRONTEND_URL="${FRONTEND_URL}" python3 -c 'import os,urllib.parse; print(urllib.parse.urlparse(os.environ["FRONTEND_URL"]).port or 8081)')"

if has_cmd docker && docker compose version >/dev/null 2>&1; then
    info "Ensuring PostgreSQL and Redis are running..."
    docker compose -f docker-compose.yml up -d postgres redis
    wait_for_port 127.0.0.1 5432 60 || {
        error "PostgreSQL did not become reachable."
        exit 1
    }
    wait_for_port 127.0.0.1 6379 45 || {
        error "Redis did not become reachable."
        exit 1
    }
else
    warn "docker compose not available; expecting external PostgreSQL/Redis."
fi

info "Applying database migrations (idempotent)..."
alembic upgrade head

start_service "Backend API" "${BACKEND_PID_FILE}" "${BACKEND_LOG}" \
    python -m uvicorn apps.backend.src.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}"

if ! wait_for_http "http://127.0.0.1:${BACKEND_PORT}/health" 75; then
    error "Backend health check failed."
    exit 1
fi

start_service "Celery worker" "${WORKER_PID_FILE}" "${WORKER_LOG}" \
    celery -A apps.backend.src.worker.celery_app:celery_app worker -Q tools,intrusive --loglevel=info

if [[ -d ui ]]; then
    if ! has_cmd npm; then
        error "npm is missing. Re-run ./bootstrap.sh."
        exit 1
    fi
    start_service "Operator UI" "${UI_PID_FILE}" "${UI_LOG}" \
        npm --prefix ui run dev -- --host 0.0.0.0 --port "${UI_PORT}"
else
    warn "ui/ directory not present; skipping UI startup."
fi

echo -e "\n${GREEN}Kai services started.${NC}"
echo "  Backend API:   http://localhost:${BACKEND_PORT}"
echo "  API Docs:      http://localhost:${BACKEND_PORT}/docs"
echo "  Operator UI:   ${FRONTEND_URL}"
echo "  Logs:          runtime/logs/"
echo "  Stop command:  ./k1-stop"
