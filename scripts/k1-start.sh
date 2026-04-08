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

run_virsh() {
    local uri
    uri="$(read_env_value K1_WHONIX_LIBVIRT_URI "")"
    if [[ -n "${uri}" ]]; then
        virsh -c "${uri}" "$@"
    else
        virsh "$@"
    fi
}

validate_whonix_kvm_proxy() {
    local enforce
    enforce="$(read_env_value K1_ENFORCE_WHONIX_KVM false)"
    if ! env_truthy "${enforce}"; then
        return 0
    fi

    if ! has_cmd virsh; then
        error "Whonix/KVM enforcement is enabled but 'virsh' is not installed."
        error "Install libvirt/virsh, start the Whonix Gateway VM, then retry."
        return 1
    fi

    local vm_names_csv
    vm_names_csv="$(read_env_value K1_WHONIX_VM_NAMES "whonix-gateway,Whonix-Gateway,whonix_gateway")"
    IFS=',' read -r -a vm_candidates <<< "${vm_names_csv}"
    local running_vm=""
    local configured_uri
    configured_uri="$(read_env_value K1_WHONIX_LIBVIRT_URI "")"
    local active_uri=""
    local uri
    local -a uri_candidates
    uri_candidates=()
    if [[ -n "${configured_uri}" ]]; then
        uri_candidates+=("${configured_uri}")
    fi
    if [[ "${configured_uri}" != "qemu:///system" ]]; then
        uri_candidates+=("qemu:///system")
    fi
    if [[ "${configured_uri}" != "qemu:///session" ]]; then
        uri_candidates+=("qemu:///session")
    fi

    for uri in "${uri_candidates[@]}"; do
        virsh -c "${uri}" list --all >/dev/null 2>&1 || continue
        for vm in "${vm_candidates[@]}"; do
            vm="$(echo "${vm}" | xargs)"
            [[ -z "${vm}" ]] && continue
            state="$(virsh -c "${uri}" domstate "${vm}" 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)"
            if [[ "${state}" == *"running"* ]]; then
                running_vm="${vm}"
                active_uri="${uri}"
                break
            fi
        done
        [[ -n "${running_vm}" ]] && break
    done

    if [[ -z "${running_vm}" ]]; then
        error "Whonix/KVM enforcement is enabled but no configured Whonix VM is running."
        error "Checked VMs: ${vm_names_csv}"
        if [[ -n "${configured_uri}" ]]; then
            error "Using libvirt URI: ${configured_uri}"
        fi
        return 1
    fi

    if [[ -n "${active_uri}" && -n "${configured_uri}" && "${active_uri}" != "${configured_uri}" ]]; then
        warn "Configured libvirt URI ${configured_uri} does not contain a running Whonix VM; using ${active_uri}."
        configured_uri="${active_uri}"
    fi

    local proxy_url proxy_host proxy_port
    proxy_url="$(read_env_value HTTPS_PROXY "")"
    if [[ -z "${proxy_url}" ]]; then
        proxy_url="$(read_env_value HTTP_PROXY "")"
    fi
    if [[ -z "${proxy_url}" ]]; then
        proxy_host="$(read_env_value K1_WHONIX_PROXY_HOST 127.0.0.1)"
        proxy_port="$(read_env_value K1_WHONIX_PROXY_PORT 9050)"
    else
        proxy_host="$(PROXY_URL="${proxy_url}" python3 -c 'import os, urllib.parse; u = urllib.parse.urlparse(os.environ["PROXY_URL"]); print(u.hostname or "")')"
        proxy_port="$(PROXY_URL="${proxy_url}" python3 -c 'import os, urllib.parse; u = urllib.parse.urlparse(os.environ["PROXY_URL"]); print(u.port or (443 if u.scheme == "https" else 80))')"
    fi

    if [[ -z "${proxy_host}" || -z "${proxy_port}" ]]; then
        error "Unable to resolve Whonix proxy host/port from HTTP_PROXY/HTTPS_PROXY."
        return 1
    fi

    if ! wait_for_port "${proxy_host}" "${proxy_port}" 12; then
        error "Whonix proxy ${proxy_host}:${proxy_port} is not reachable."
        error "Ensure Whonix Gateway is running in KVM and proxy listener is active."
        return 1
    fi

    if [[ -n "${configured_uri}" ]]; then
        info "Whonix/KVM proxy enforcement passed (uri=${configured_uri}, vm=${running_vm}, proxy=${proxy_host}:${proxy_port})."
    else
        info "Whonix/KVM proxy enforcement passed (vm=${running_vm}, proxy=${proxy_host}:${proxy_port})."
    fi
}

ensure_whonix_kvm_proxy() {
    local enforce
    enforce="$(read_env_value K1_ENFORCE_WHONIX_KVM false)"
    if ! env_truthy "${enforce}"; then
        return 0
    fi

    if validate_whonix_kvm_proxy; then
        return 0
    fi

    if [[ -x "${REPO_ROOT}/scripts/setup_whonix_kvm.sh" ]]; then
        warn "Whonix proxy check failed; attempting auto-setup via scripts/setup_whonix_kvm.sh"
        if ! "${REPO_ROOT}/scripts/setup_whonix_kvm.sh"; then
            error "Automatic Whonix setup failed."
            return 1
        fi
        # Reload .env because setup_whonix_kvm.sh may update URI/VM/proxy vars.
        set -a
        # shellcheck disable=SC1091
        source .env
        set +a
        validate_whonix_kvm_proxy
        return $?
    fi

    error "Whonix enforcement failed and setup helper script is unavailable."
    return 1
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
mkdir -p runtime/logs runtime/pids

ensure_whonix_kvm_proxy || exit 1

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
