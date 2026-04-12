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

is_container_running() {
    local name="$1"
    has_cmd docker || return 1
    docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "${name}"
}

compose_cmd() {
    if has_cmd docker && docker compose version >/dev/null 2>&1; then
        echo "docker compose"
        return 0
    fi
    if has_cmd docker-compose; then
        echo "docker-compose"
        return 0
    fi
    return 1
}

cleanup_compose_stale_containers() {
    local service="$1"
    local canonical="k1_${service}"
    docker rm -f "${canonical}" >/dev/null 2>&1 || true
    while IFS= read -r container_name; do
        [[ -z "${container_name}" ]] && continue
        if [[ "${container_name}" == *_k1_"${service}" ]]; then
            docker rm -f "${container_name}" >/dev/null 2>&1 || true
        fi
    done < <(docker ps -a --format '{{.Names}}' 2>/dev/null || true)
}

compose_up_with_retry() {
    local compose_bin="$1"
    shift
    local services=("$@")
    local output=""
    if output="$(${compose_bin} -f docker-compose.yml up -d "${services[@]}" 2>&1)"; then
        [[ -n "${output}" ]] && echo "${output}"
        return 0
    fi

    echo "${output}" >&2
    if [[ "${output}" == *"ContainerConfig"* ]]; then
        warn "Detected docker-compose recreate bug (ContainerConfig). Cleaning stale containers and retrying once."
        for service in "${services[@]}"; do
            cleanup_compose_stale_containers "${service}"
        done
        ${compose_bin} -f docker-compose.yml up -d "${services[@]}"
        return $?
    fi

    return 1
}

read_env_value() {
    local key="$1"
    local default="$2"
    local value=""
    if [[ -n "${!key:-}" ]]; then
        echo "${!key}"
        return 0
    fi
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

env_truthy() {
    local raw="${1:-}"
    raw="$(echo "${raw}" | tr '[:upper:]' '[:lower:]')"
    [[ "${raw}" == "1" || "${raw}" == "true" || "${raw}" == "yes" || "${raw}" == "on" ]]
}

should_manage_ollama_container() {
    local external_raw
    external_raw="$(read_env_value K1_OLLAMA_MANAGED_EXTERNALLY false)"
    if env_truthy "${external_raw}"; then
        info "K1_OLLAMA_MANAGED_EXTERNALLY=true; using external Ollama on 127.0.0.1:11434."
        return 1
    fi

    if wait_for_port 127.0.0.1 11434 1; then
        if is_container_running "k1_ollama"; then
            return 0
        fi
        warn "Detected existing Ollama listener on 127.0.0.1:11434 (non-k1_ollama). Using external Ollama."
        return 1
    fi

    return 0
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

csv_contains() {
    local needle="$1"
    local csv="$2"
    local item=""
    IFS=',' read -r -a items <<< "${csv}"
    for item in "${items[@]}"; do
        item="$(echo "${item}" | xargs)"
        if [[ -n "${item}" && "${item}" == "${needle}" ]]; then
            return 0
        fi
    done
    return 1
}

detect_active_interface() {
    local check_ip
    check_ip="$(read_env_value K1_VPN_CHECK_IP 1.1.1.1)"
    if has_cmd ip; then
        ip -o route get "${check_ip}" 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i=="dev") {print $(i+1); exit}}'
        return 0
    fi
    return 1
}

verify_vpn_interface() {
    local active_iface
    active_iface="$(read_env_value K1_ACTIVE_VPN_INTERFACE "")"
    if [[ -z "${active_iface}" ]]; then
        active_iface="$(detect_active_interface || true)"
    fi
    if [[ -z "${active_iface}" ]]; then
        error "Unable to detect active egress interface for sovereign network validation."
        return 1
    fi

    local allowed_ifaces vpn_bridge_iface
    allowed_ifaces="$(read_env_value K1_VPN_ALLOWED_INTERFACES "tun0,wg0")"
    vpn_bridge_iface="$(read_env_value K1_VPN_BRIDGE_INTERFACE "")"
    if [[ -n "${vpn_bridge_iface}" ]]; then
        allowed_ifaces="${allowed_ifaces},${vpn_bridge_iface}"
    fi

    if ! csv_contains "${active_iface}" "${allowed_ifaces}"; then
        error "Active interface '${active_iface}' is not an allowed sovereign tunnel interface (${allowed_ifaces})."
        return 1
    fi

    if has_cmd ip && ! ip link show "${active_iface}" 2>/dev/null | grep -q "state UP"; then
        error "Tunnel interface '${active_iface}' is not UP."
        return 1
    fi

    info "Sovereign VPN interface verified: ${active_iface}"
    return 0
}

verify_ip_leak_protection() {
    if ! has_cmd curl; then
        error "curl is required for sovereign IP leak validation."
        return 1
    fi

    local ip_api public_ip local_isp_cidrs
    ip_api="$(read_env_value K1_EGRESS_IP_API "https://ipinfo.io/ip")"
    public_ip="$(curl -fsS --max-time 10 "${ip_api}" | tr -d '[:space:]' || true)"
    if [[ -z "${public_ip}" ]]; then
        error "Unable to resolve external egress IP from ${ip_api}."
        return 1
    fi

    local_isp_cidrs="$(read_env_value K1_LOCAL_ISP_CIDRS "")"
    if [[ -z "${local_isp_cidrs}" ]]; then
        error "K1_LOCAL_ISP_CIDRS is empty; cannot enforce IP leak protection."
        return 1
    fi

    local check_rc=0
    python3 - "${public_ip}" "${local_isp_cidrs}" <<'PY'
import ipaddress
import sys

ip_text = sys.argv[1]
cidrs = [c.strip() for c in sys.argv[2].split(",") if c.strip()]
try:
    ip_obj = ipaddress.ip_address(ip_text)
except ValueError:
    raise SystemExit(2)

for cidr in cidrs:
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        continue
    if ip_obj in network:
        raise SystemExit(1)

raise SystemExit(0)
PY
    check_rc=$?
    if [[ "${check_rc}" -eq 0 ]]; then
        info "Sovereign egress IP check passed: ${public_ip}"
        return 0
    fi

    if [[ "${check_rc}" -eq 2 ]]; then
        error "Public IP '${public_ip}' returned by ${ip_api} is not a valid IP address."
        return 1
    fi

    error "Egress IP ${public_ip} falls within configured local ISP CIDRs (${local_isp_cidrs})."
    return 1
}

verify_proxy_tunnel() {
    local use_proxies
    use_proxies="$(read_env_value K1_USE_PROXIES false)"
    if ! env_truthy "${use_proxies}"; then
        return 0
    fi

    if ! has_cmd curl; then
        error "curl is required for proxy tunnel verification."
        return 1
    fi

    local proxy_url health_url timeout_s
    proxy_url="$(read_env_value K1_RESIDENTIAL_PROXY_URL "")"
    if [[ -z "${proxy_url}" ]]; then
        proxy_url="$(read_env_value HTTPS_PROXY "")"
    fi
    if [[ -z "${proxy_url}" ]]; then
        proxy_url="$(read_env_value HTTP_PROXY "")"
    fi
    if [[ -z "${proxy_url}" ]]; then
        error "K1_USE_PROXIES=true but no proxy URL configured (K1_RESIDENTIAL_PROXY_URL/HTTPS_PROXY/HTTP_PROXY)."
        return 1
    fi

    health_url="$(read_env_value K1_PROXY_HEALTHCHECK_URL "https://example.com")"
    timeout_s="$(read_env_value K1_PROXY_HEAD_TIMEOUT_SECONDS 10)"
    if ! curl -fsSI --max-time "${timeout_s}" --proxy "${proxy_url}" "${health_url}" >/dev/null 2>&1; then
        error "Residential proxy tunnel HEAD check failed (${health_url})."
        return 1
    fi

    info "Sovereign proxy tunnel verified."
    return 0
}

verify_sovereign_network() {
    local enforce
    enforce="$(read_env_value K1_ENFORCE_SOVEREIGN_NETWORK true)"
    if ! env_truthy "${enforce}"; then
        error "K1_ENFORCE_SOVEREIGN_NETWORK=false is not allowed in tunnel-first mode."
        error "CRITICAL: Sovereign Network Layer not detected. Aborting to prevent IP leak."
        return 1
    fi

    info "Validating Sovereign Network Layer..."
    verify_vpn_interface || {
        error "CRITICAL: Sovereign Network Layer not detected. Aborting to prevent IP leak."
        return 1
    }
    verify_ip_leak_protection || {
        error "CRITICAL: Sovereign Network Layer not detected. Aborting to prevent IP leak."
        return 1
    }
    verify_proxy_tunnel || {
        error "CRITICAL: Sovereign Network Layer not detected. Aborting to prevent IP leak."
        return 1
    }
    info "Sovereign Network Layer: UP"
    return 0
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
# Keep virtualenv binaries ahead of user-local binaries (e.g. celery).
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    export PATH="${VIRTUAL_ENV}/bin:${HOME}/.local/bin:${PATH}"
else
    export PATH="${HOME}/.local/bin:${PATH}"
fi
# Export .env so backend/worker inherit DATABASE_URL, REDIS_URL, VAULT_ADDR, etc.
set -a
# shellcheck disable=SC1091
source .env
set +a

NETWORK_ENV_SH="${REPO_ROOT}/apps/backend/src/config/network_env.sh"
if [[ -f "${NETWORK_ENV_SH}" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${NETWORK_ENV_SH}"
    set +a
fi

mkdir -p runtime/logs runtime/pids

verify_sovereign_network || exit 1

BACKEND_HOST="$(read_env_value BACKEND_HOST 0.0.0.0)"
BACKEND_PORT="$(read_env_value BACKEND_PORT 8080)"
FRONTEND_URL="$(read_env_value FRONTEND_URL http://localhost:8081)"
UI_PORT="$(FRONTEND_URL="${FRONTEND_URL}" python3 -c 'import os,urllib.parse; print(urllib.parse.urlparse(os.environ["FRONTEND_URL"]).port or 8081)')"
VAULT_HOST_BIND="$(read_env_value K1_VAULT_HOST_BIND 127.0.0.1)"
if [[ "${VAULT_HOST_BIND}" == "0.0.0.0" || "${VAULT_HOST_BIND}" == "::" ]]; then
    VAULT_WAIT_HOST="127.0.0.1"
else
    VAULT_WAIT_HOST="${VAULT_HOST_BIND}"
fi
VAULT_HOST_PORT="$(read_env_value K1_VAULT_HOST_PORT 8200)"

COMPOSE_BIN="$(compose_cmd || true)"
START_VAULT=false
START_OLLAMA=false
OLLAMA_REQUIRED=false
if [[ -n "${COMPOSE_BIN}" ]]; then
    SECRET_BACKEND="$(read_env_value K1_SECRET_BACKEND env | tr '[:upper:]' '[:lower:]')"
    PROVIDER_CHAIN="$(printf "%s,%s" "$(read_env_value K1_PRIMARY_LLM_PROVIDER anthropic)" "$(read_env_value K1_FALLBACK_LLM_PROVIDERS openai,gemini,ollama)" | tr '[:upper:]' '[:lower:]')"
    INFRA_SERVICES=(postgres redis)
    if [[ "${SECRET_BACKEND}" == "vault" ]]; then
        INFRA_SERVICES+=(vault)
        START_VAULT=true
    fi
    if [[ "${PROVIDER_CHAIN}" == *"ollama"* ]]; then
        OLLAMA_REQUIRED=true
        if should_manage_ollama_container; then
            INFRA_SERVICES+=(ollama)
            START_OLLAMA=true
        fi
    fi

    info "Checking Docker authentication..."
    if ! bash "${REPO_ROOT}/scripts/docker_auth_check.sh"; then
        error "Docker authentication check failed."
        exit 1
    fi

    info "Ensuring infrastructure services are running: ${INFRA_SERVICES[*]}"
    compose_up_with_retry "${COMPOSE_BIN}" "${INFRA_SERVICES[@]}"
    wait_for_port 127.0.0.1 5432 60 || {
        error "PostgreSQL did not become reachable."
        exit 1
    }
    wait_for_port 127.0.0.1 6379 45 || {
        error "Redis did not become reachable."
        exit 1
    }
    if [[ "${START_VAULT}" == "true" ]]; then
        wait_for_port "${VAULT_WAIT_HOST}" "${VAULT_HOST_PORT}" 45 || {
            error "Vault did not become reachable."
            exit 1
        }
    fi
    if [[ "${OLLAMA_REQUIRED}" == "true" ]]; then
        wait_for_port 127.0.0.1 11434 90 || {
            error "Ollama did not become reachable."
            exit 1
        }
        if [[ -x "${REPO_ROOT}/scripts/ensure_ollama_models.sh" ]]; then
            if ! "${REPO_ROOT}/scripts/ensure_ollama_models.sh"; then
                warn "Ollama model sync reported an issue. Continue startup and inspect logs."
            fi
        fi
    fi
else
    warn "No docker compose command available; expecting external PostgreSQL/Redis."
fi

info "Applying database migrations (idempotent)..."
alembic upgrade heads

start_service "Backend API" "${BACKEND_PID_FILE}" "${BACKEND_LOG}" \
    python -m uvicorn apps.backend.src.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}"

if ! wait_for_http "http://127.0.0.1:${BACKEND_PORT}/health" 75; then
    error "Backend health check failed."
    exit 1
fi

start_service "Celery worker" "${WORKER_PID_FILE}" "${WORKER_LOG}" \
    python -m celery -A apps.backend.src.worker.celery_app:celery_app worker -Q tools,intrusive --loglevel=info

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
