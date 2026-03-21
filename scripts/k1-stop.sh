#!/usr/bin/env bash
# Kai runtime stop.
# Usage: ./scripts/k1-stop.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[k1-stop]${NC} $*"; }
warn() { echo -e "${YELLOW}[k1-stop]${NC} $*"; }
error() { echo -e "${RED}[k1-stop]${NC} $*" >&2; }

stop_service() {
    local name="$1"
    local pid_file="$2"

    if [[ ! -f "${pid_file}" ]]; then
        info "${name}: not running (no PID file)."
        return 0
    fi

    local pid
    pid="$(cat "${pid_file}")"
    if [[ -z "${pid}" ]]; then
        rm -f "${pid_file}"
        warn "${name}: removed empty PID file."
        return 0
    fi

    if kill -0 "${pid}" >/dev/null 2>&1; then
        info "Stopping ${name} (PID ${pid})..."
        kill "${pid}" >/dev/null 2>&1 || true
        for _ in $(seq 1 10); do
            if ! kill -0 "${pid}" >/dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        if kill -0 "${pid}" >/dev/null 2>&1; then
            warn "${name} did not stop gracefully; sending SIGKILL."
            kill -9 "${pid}" >/dev/null 2>&1 || true
        fi
    else
        warn "${name}: PID ${pid} is not running; cleaning stale PID file."
    fi

    rm -f "${pid_file}"
}

mkdir -p runtime/pids

stop_service "Operator UI" "runtime/pids/ui.pid"
stop_service "Celery worker" "runtime/pids/worker.pid"
stop_service "Backend API" "runtime/pids/backend.pid"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    info "Stopping docker infrastructure services (postgres, redis)..."
    docker compose -f docker-compose.yml stop postgres redis >/dev/null 2>&1 || true
else
    warn "docker compose not available; skipped postgres/redis stop."
fi

echo -e "${GREEN}Kai services stopped.${NC}"
