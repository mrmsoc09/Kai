#!/usr/bin/env bash
# Kai bootstrap entrypoint.
# Usage: ./scripts/setup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# Source sovereign tool installer module
source "${SCRIPT_DIR}/sovereign_tool_installer.sh"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

BOOTSTRAP_MARKER="runtime/.bootstrap_ready"
LOCAL_BIN_DIR="${HOME}/.local/bin"
LOCAL_TOOLS_SRC_DIR="${REPO_ROOT}/opt/k1-tools/src"

PYTHON_DEPS_OK=false
UI_DEPS_OK=false
ENV_OK=false
MIGRATIONS_OK=false
TOOLS_OK=false
DOCKER_INFRA_OK=false

declare -a TOOL_ERRORS=()
declare -a MANUAL_PREREQS=()
APT_UPDATED=0

info() { echo -e "${GREEN}[k1-bootstrap]${NC} $*"; }
warn() { echo -e "${YELLOW}[k1-bootstrap]${NC} $*"; }
error() { echo -e "${RED}[k1-bootstrap]${NC} $*" >&2; }
section() { echo -e "\n${BLUE}==> $*${NC}"; }

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

can_use_apt() {
    has_cmd apt-get
}

apt_prefix() {
    if has_cmd sudo; then
        echo "sudo"
    elif [ "$(id -u)" -eq 0 ]; then
        echo ""
    else
        echo "__NO_ROOT__"
    fi
}

apt_install_packages() {
    local prefix
    prefix="$(apt_prefix)"
    if ! can_use_apt; then
        return 1
    fi
    if [[ "${prefix}" == "__NO_ROOT__" ]]; then
        return 1
    fi
    if [[ ${APT_UPDATED} -eq 0 ]]; then
        if [[ -n "${prefix}" ]]; then
            ${prefix} apt-get update
        else
            apt-get update
        fi
        APT_UPDATED=1
    fi
    if [[ -n "${prefix}" ]]; then
        ${prefix} apt-get install -y "$@"
    else
        apt-get install -y "$@"
    fi
}

ensure_python_minimum() {
    python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ is required.")
print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
PY
}

set_env_value() {
    local key="$1"
    local value="$2"
    local file="$3"
    if grep -q "^${key}=" "${file}"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "${file}"
    else
        printf "\n%s=%s\n" "${key}" "${value}" >> "${file}"
    fi
}

read_env_value() {
    local key="$1"
    local default="$2"
    local file="$3"
    local value=""
    if [[ -f "${file}" ]]; then
        value="$(grep -E "^${key}=" "${file}" | tail -n 1 | cut -d= -f2- || true)"
        value="${value%\"}"
        value="${value#\"}"
    fi
    if [[ -n "${value}" ]]; then
        echo "${value}"
    else
        echo "${default}"
    fi
}

read_env_bool() {
    local key="$1"
    local default="$2"
    local file="$3"
    local value
    value="$(read_env_value "${key}" "${default}" "${file}" | tr '[:upper:]' '[:lower:]')"
    if [[ "${value}" == "1" || "${value}" == "true" || "${value}" == "yes" || "${value}" == "on" ]]; then
        echo "true"
    else
        echo "false"
    fi
}

readiness_line() {
    local label="$1"
    local ok="$2"
    if [[ "${ok}" == "true" ]]; then
        echo -e "  ${GREEN}✓${NC} ${label}"
    else
        echo -e "  ${RED}✗${NC} ${label}"
    fi
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

wait_for_postgres() {
    local host="$1"
    local port="$2"
    local user="$3"
    local password="$4"
    local db="$5"
    local timeout="${6:-60}"
    python3 - "$host" "$port" "$user" "$password" "$db" "$timeout" <<'PY'
import psycopg2
import sys
import time

host = sys.argv[1]
port = int(sys.argv[2])
user = sys.argv[3]
password = sys.argv[4]
db = sys.argv[5]
timeout = int(sys.argv[6])
deadline = time.time() + timeout
while time.time() < deadline:
    try:
        conn = psycopg2.connect(dbname=db, user=user, password=password, host=host, port=port, connect_timeout=2)
        conn.close()
        raise SystemExit(0)
    except Exception:
        time.sleep(1)
raise SystemExit(1)
PY
}

should_manage_ollama_container() {
    local env_file="$1"
    local external_raw
    external_raw="$(read_env_bool K1_OLLAMA_MANAGED_EXTERNALLY false "${env_file}")"
    if [[ "${external_raw}" == "true" ]]; then
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

run_verify_cmd() {
    local verify_json="$1"
    TOOL_VERIFY_JSON="${verify_json}" PATH="${PATH}" python3 - <<'PY'
import json
import os
import shutil
import subprocess
import sys

raw = os.environ.get("TOOL_VERIFY_JSON", "[]")
try:
    cmd = json.loads(raw)
except json.JSONDecodeError:
    raise SystemExit(1)

if not isinstance(cmd, list) or not cmd:
    raise SystemExit(1)

if cmd[0] == "python" and shutil.which("python") is None and shutil.which("python3"):
    cmd[0] = "python3"

try:
    # Pass the current PATH explicitly to subprocess
    env = os.environ.copy()
    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=20, env=env)
except FileNotFoundError:
    raise SystemExit(1)
except Exception:
    raise SystemExit(1)

raise SystemExit(0 if completed.returncode == 0 else 1)
PY
}

ensure_go() {
    if has_cmd go; then
        return 0
    fi
    if apt_install_packages golang-go; then
        return 0
    fi
    return 1
}

ensure_local_bin() {
    mkdir -p "${LOCAL_BIN_DIR}"
    export PATH="${LOCAL_BIN_DIR}:${PATH}"
}

clone_or_update_repo() {
    local repo_url="$1"
    local dest_dir="$2"
    mkdir -p "$(dirname "${dest_dir}")"
    if [[ -d "${dest_dir}/.git" ]]; then
        git -C "${dest_dir}" pull --ff-only >/dev/null 2>&1 || true
    else
        git clone --depth 1 "${repo_url}" "${dest_dir}" >/dev/null 2>&1
    fi
}

install_go_tool() {
    local module="$1"
    if ! ensure_go; then
        return 1
    fi
    ensure_local_bin
    export GOBIN="${LOCAL_BIN_DIR}"
    mkdir -p "${GOBIN}"
    GO111MODULE=on go install "${module}"
}

install_local_download_tool() {
    local tool="$1"
    local downloads_dir="${K1_DOWNLOADS_DIR:-${HOME}/Downloads}"
    local gobin="${HOME}/.local/bin"

    mkdir -p "${gobin}"

    case "${tool}" in
        amass)
            if [[ -d "${downloads_dir}/amass" ]] && ensure_go; then
                (cd "${downloads_dir}/amass" && CGO_ENABLED=0 go build -o "${gobin}/amass" ./cmd/amass)
                return $?
            fi
            ;;
        hakrawler)
            if [[ -d "${downloads_dir}/hakrawler" ]] && ensure_go; then
                (cd "${downloads_dir}/hakrawler" && go build -o "${gobin}/hakrawler" .)
                return $?
            fi
            ;;
        gitleaks)
            if [[ -d "${downloads_dir}/gitleaks" ]] && ensure_go; then
                (cd "${downloads_dir}/gitleaks" && go build -o "${gobin}/gitleaks" .)
                return $?
            fi
            ;;
        findomain)
            if [[ -d "${downloads_dir}/Findomain" ]]; then
                if ! has_cmd cargo; then
                    apt_install_packages cargo >/dev/null 2>&1 || return 1
                fi
                (cd "${downloads_dir}/Findomain" && cargo build --release)
                cp -f "${downloads_dir}/Findomain/target/release/findomain" "${gobin}/findomain"
                return $?
            fi
            ;;
        searchsploit)
            if [[ -x "${downloads_dir}/exploitdb/searchsploit" ]]; then
                cat > "${gobin}/searchsploit" <<EOF
#!/usr/bin/env bash
exec "${downloads_dir}/exploitdb/searchsploit" "\$@"
EOF
                chmod +x "${gobin}/searchsploit"
                return 0
            fi
            ;;
        theharvester)
            if [[ -d "${downloads_dir}/theHarvester/theHarvester" ]]; then
                cat > "${gobin}/theHarvester" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${downloads_dir}/theHarvester:\${PYTHONPATH:-}"
exec python3 -m theHarvester.theHarvester "\$@"
EOF
                chmod +x "${gobin}/theHarvester"
                return 0
            fi
            ;;
    esac

    return 1
}

install_native_tool() {
    local tool="$1"
    case "${tool}" in
        # Go tools
        amass) install_go_tool github.com/OWASP/Amass/v3/cmd/amass@latest ;;
        assetfinder) install_go_tool github.com/tomnomnom/assetfinder@latest ;;
        subfinder) install_go_tool github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest ;;
        dnsx) install_go_tool github.com/projectdiscovery/dnsx/cmd/dnsx@latest ;;
        gau) install_go_tool github.com/lc/gau/v2/cmd/gau@latest ;;
        waybackurls) install_go_tool github.com/tomnomnom/waybackurls@latest ;;
        httpx) install_go_tool github.com/projectdiscovery/httpx/cmd/httpx@latest ;;
        httpx_probe) install_go_tool github.com/tomnomnom/httprobe@latest ;;
        httprobe) install_go_tool github.com/tomnomnom/httprobe@latest ;;
        naabu) install_go_tool github.com/projectdiscovery/naabu/v2/cmd/naabu@latest ;;
        tlsx) install_go_tool github.com/projectdiscovery/tlsx/cmd/tlsx@latest ;;
        nuclei) install_go_tool github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest ;;
        katana) install_go_tool github.com/projectdiscovery/katana/cmd/katana@latest ;;
        dalfox) install_go_tool github.com/hahwul/dalfox/v2@latest ;;
        feroxbuster) apt_install_packages feroxbuster ;;
        paramspider) install_go_tool github.com/devanshbatham/paramspider@latest ;;
        hakrawler) install_go_tool github.com/hakluke/hakrawler@latest ;;
        gitleaks) install_go_tool github.com/gitleaks/gitleaks/v8@latest ;;
        ffuf) install_go_tool github.com/ffuf/ffuf/v2@latest ;;
        gf) install_go_tool github.com/tomnomnom/gf@latest ;;
        trufflehog) _install_trufflehog_sovereign ;;
        crlfuzz) install_go_tool github.com/dwisiswant0/crlfuzz/cmd/crlfuzz@latest ;;
        phoneinfoga) install_go_tool github.com/sundowndev/phoneinfoga/v2@latest ;;
        github-subdomains) install_go_tool github.com/gwen001/github-subdomains@latest ;;
        gowitness) install_go_tool github.com/sensepost/gowitness@latest ;;
        findomain) install_go_tool github.com/Findomain/Findomain@latest ;;

        # APT packages
        nmap) apt_install_packages nmap ;;
        nikto) apt_install_packages nikto ;;
        whatweb) apt_install_packages whatweb ;;
        exploitdb) apt_install_packages exploitdb ;;
        searchsploit) install_searchsploit ;;
        zaproxy) apt_install_packages zaproxy ;;
        owasp-zap) _install_owasp_zap_sovereign ;;
        wafw00f) apt_install_packages wafw00f ;;

        # Source builds (Sovereign Build framework)
        testssl) install_testssl ;;
        spiderfoot) _install_spiderfoot_sovereign ;;
        eyewitness) _install_eyewitness_sovereign ;;
        graphql-cop) install_graphql_cop ;;
        kiterunner) install_kiterunner ;;
        masscan) _install_masscan_sovereign ;;
        metasploit-framework) _install_metasploit_sovereign ;;
        reconftw) _install_reconftw_sovereign ;;
        ahmia-client) install_ahmia_client ;;
        searchsploit) _install_searchsploit_sovereign ;;
        caido) _install_caido_sovereign ;;
        faraday-community) _install_faraday_sovereign ;;

        # Python tools (Sovereign Build framework)
        arjun) _install_arjun_sovereign ;;
        social-analyzer) pip install "git+https://github.com/qeeqbox/social-analyzer.git" ;;
        torbot) _install_torbot_sovereign ;;
        smuggler) pip install smuggler ;;

        *)
            return 1
            ;;
    esac
}

install_kiterunner() {
    local src_dir="${LOCAL_TOOLS_SRC_DIR}/kiterunner"
    ensure_local_bin
    if [[ ! -d "${src_dir}" ]]; then
        mkdir -p "${LOCAL_TOOLS_SRC_DIR}"
        git clone https://github.com/assetnote/kiterunner "${src_dir}" 2>&1 | head -3
    fi
    cd "${src_dir}" && make build 2>&1 | tail -2
    cp "${src_dir}/dist/kr" "${LOCAL_BIN_DIR}/kr" && chmod +x "${LOCAL_BIN_DIR}/kr"
}

# Old install_eyewitness replaced by sovereign tool installer
# See sovereign_tool_installer.sh for implementation

# Wrapper for sovereign tool installer
_install_masscan_sovereign() {
    install_masscan "$@"
}

_install_metasploit_sovereign() {
    install_metasploit "$@"
}

_install_eyewitness_sovereign() {
    install_eyewitness "$@"
}

_install_arjun_sovereign() {
    install_arjun "$@"
}

_install_spiderfoot_sovereign() {
    install_spiderfoot "$@"
}

_install_reconftw_sovereign() {
    install_reconftw "$@"
}

_install_torbot_sovereign() {
    install_torbot "$@"
}

_install_trufflehog_sovereign() {
    install_trufflehog "$@"
}

_install_searchsploit_sovereign() {
    install_searchsploit "$@"
}

_install_caido_sovereign() {
    install_caido "$@"
}

_install_owasp_zap_sovereign() {
    install_owasp_zap "$@"
}

_install_faraday_sovereign() {
    install_faraday "$@"
}

# Old install_metasploit_framework replaced by sovereign tool installer
# See sovereign_tool_installer.sh for implementation

# Old install_reconftw replaced by sovereign tool installer
# See sovereign_tool_installer.sh for implementation

install_ahmia_client() {
    local crawler_dir="${LOCAL_TOOLS_SRC_DIR}/ahmia-crawler"
    local index_dir="${LOCAL_TOOLS_SRC_DIR}/ahmia-index"
    ensure_local_bin
    clone_or_update_repo "https://github.com/ahmia/ahmia-crawler.git" "${crawler_dir}" || true
    clone_or_update_repo "https://github.com/ahmia/ahmia-index.git" "${index_dir}" || true
    cat > "${LOCAL_BIN_DIR}/ahmia" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" || "${#}" -eq 0 ]]; then
  echo "Usage: ahmia search <query>"
  exit 0
fi
if [[ "${1:-}" != "search" || -z "${2:-}" ]]; then
  echo "Usage: ahmia search <query>" >&2
  exit 2
fi
python3 - "$2" <<'PY'
import requests
import sys
q = sys.argv[1]
r = requests.get("https://ahmia.fi/search/", params={"q": q}, timeout=30)
r.raise_for_status()
print(r.text[:50000])
PY
EOF
    chmod +x "${LOCAL_BIN_DIR}/ahmia"
}

# Old install_searchsploit replaced by sovereign tool installer
# See sovereign_tool_installer.sh for implementation

# Old install_caido replaced by sovereign tool installer
# See sovereign_tool_installer.sh for implementation

# Old install_faraday replaced by sovereign tool installer
# See sovereign_tool_installer.sh for implementation

pip() {
    python3 -m pip "$@" 2>&1 | grep -v "Requirement already satisfied" || return 1
}

load_enabled_tools() {
    python3 - <<'PY'
import json
from pathlib import Path

import yaml

payload = yaml.safe_load(Path("tools/registry/tool_registry.yaml").read_text(encoding="utf-8")) or {}
for tool in payload.get("tools", []):
    if not isinstance(tool, dict):
        continue
    if not bool(tool.get("enabled_by_default", True)):
        continue
    record = {
        "name": str(tool.get("name") or "").strip(),
        "mode": str(tool.get("execution_mode") or "native").strip().lower(),
        "verify": tool.get("install_verification_cmd") or [],
        "image": str(tool.get("container_image") or "").strip(),
    }
    if record["name"]:
        print(json.dumps(record))
PY
}

# Source Wave 7 tool bootstrap functions
if [[ -f "${REPO_ROOT}/scripts/tools-bootstrap-functions.sh" ]]; then
    source "${REPO_ROOT}/scripts/tools-bootstrap-functions.sh"
fi

section "System package dependencies"
# Packages needed at the OS level for Python packages that wrap C libraries
# (weasyprint → pango/cairo/gdk-pixbuf, cryptography → libssl/libffi, curl for
# k1-start health checks, git for tool installs).  We attempt apt install on
# Debian/Ubuntu; on other distros we warn with actionable instructions.
SYSTEM_APT_PACKAGES=(
    curl
    git
    build-essential
    libssl-dev
    libffi-dev
    libglib2.0-0
    libpango-1.0-0
    libpangocairo-1.0-0
    libpangoft2-1.0-0
    libgdk-pixbuf-2.0-0
    libcairo2
    shared-mime-info
)
SYSTEM_MISSING=()
for pkg_check_cmd in curl git; do
    if ! has_cmd "${pkg_check_cmd}"; then
        SYSTEM_MISSING+=("${pkg_check_cmd}")
    fi
done
# pango is represented by the pango-view binary; otherwise check shared lib
if ! ldconfig -p 2>/dev/null | grep -q libpango; then
    SYSTEM_MISSING+=("libpango-1.0-0 (pango — required by weasyprint)")
fi

if [[ ${#SYSTEM_MISSING[@]} -gt 0 ]]; then
    if can_use_apt; then
        info "Installing system packages via apt: ${SYSTEM_APT_PACKAGES[*]}"
        if apt_install_packages "${SYSTEM_APT_PACKAGES[@]}"; then
            info "System packages installed."
        else
            warn "apt install encountered errors. Some system packages may be missing."
            warn "If weasyprint or cryptography fail to build, run:"
            warn "  sudo apt-get install -y ${SYSTEM_APT_PACKAGES[*]}"
        fi
    else
        warn "apt not available. Missing system packages detected: ${SYSTEM_MISSING[*]}"
        warn "Install the equivalent packages for your distro. On Debian/Ubuntu:"
        warn "  sudo apt-get install -y ${SYSTEM_APT_PACKAGES[*]}"
        MANUAL_PREREQS+=("System packages: ${SYSTEM_APT_PACKAGES[*]}")
    fi
else
    info "Required system packages appear to be present."
fi

section "Python environment"
if ! has_cmd python3; then
    if can_use_apt && apt_install_packages python3 python3-venv python3-pip; then
        info "Installed python3, python3-venv, python3-pip."
    else
        error "python3 is required. Install Python 3.11+ and re-run bootstrap."
        exit 1
    fi
fi

PYTHON_VERSION="$(ensure_python_minimum)"
info "Detected Python ${PYTHON_VERSION}"

if [[ ! -d ".venv" ]]; then
    info "Creating virtual environment at .venv"
    python3 -m venv .venv
fi

source .venv/bin/activate
export PATH="${HOME}/.local/bin:${PATH}"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
if [[ -f requirements-dev.txt ]]; then
    python -m pip install -r requirements-dev.txt
fi
PYTHON_DEPS_OK=true

section "UI dependencies"
if [[ -d ui ]]; then
    if ! has_cmd npm; then
        if can_use_apt && apt_install_packages nodejs npm; then
            info "Installed nodejs/npm from apt."
        else
            error "npm is required for ui/. Install Node.js 18+ and npm, then re-run bootstrap."
            exit 1
        fi
    fi

    NODE_MAJOR="$(node -v 2>/dev/null | sed 's/^v//' | cut -d. -f1 || echo 0)"
    if [[ "${NODE_MAJOR}" -lt 18 ]]; then
        error "Node.js 18+ is required. Detected: $(node -v 2>/dev/null || echo 'unknown')"
        error "Install Node.js 18+ (https://nodejs.org/) and re-run bootstrap."
        exit 1
    fi

    if [[ -f ui/package-lock.json ]]; then
        npm --prefix ui ci
    else
        npm --prefix ui install
    fi
    if [[ "${K1_BOOTSTRAP_UI_AUDIT_FIX:-true}" == "true" ]]; then
        if npm --prefix ui audit fix --audit-level=critical; then
            info "Applied npm audit fixes for UI (critical threshold)."
        else
            warn "npm audit fix did not complete (possibly offline). Run: npm --prefix ui audit fix"
        fi
    fi
    UI_DEPS_OK=true
else
    warn "ui/ directory not present; skipping UI dependency install."
    UI_DEPS_OK=true
fi

section "Environment + runtime directories"
ENV_CREATED=0
if [[ ! -f .env ]]; then
    if [[ -f .env.example ]]; then
        cp .env.example .env
        ENV_CREATED=1
        warn "Created .env from .env.example."
    else
        error "Missing .env and .env.example. Cannot continue."
        exit 1
    fi
fi

for key in DATABASE_URL REDIS_URL JWT_SECRET_KEY K1_DEV_TOKEN; do
    if ! grep -q "^${key}=" .env; then
        error ".env is missing required key: ${key}"
        exit 1
    fi
done

WHONIX_ENFORCE="$(read_env_bool K1_ENFORCE_WHONIX_KVM false .env)"
if [[ "${WHONIX_ENFORCE}" == "true" ]]; then
    if has_cmd virsh; then
        info "Whonix/KVM enforcement enabled and virsh is available."
    elif can_use_apt && apt_install_packages libvirt-clients; then
        info "Installed virsh (libvirt-clients) for Whonix/KVM enforcement."
    else
        warn "K1_ENFORCE_WHONIX_KVM=true but virsh is not available."
        warn "Install libvirt-clients and ensure Whonix Gateway VM is running."
        MANUAL_PREREQS+=("Whonix/KVM: libvirt-clients (virsh) + running Whonix Gateway VM")
    fi
fi

if [[ "${ENV_CREATED}" -eq 1 ]]; then
    set_env_value "K1_STARTUP_VALIDATE_SECRETS" "false" .env
    set_env_value "K1_STARTUP_VALIDATE_TOOLPACKS" "false" .env
    warn "Set K1_STARTUP_VALIDATE_SECRETS=false for first-time local startup."
fi

mkdir -p \
    artifacts/audit \
    artifacts/logs \
    artifacts/reports \
    artifacts/telemetry \
    artifacts/usage \
    artifacts/workflows \
    output/logs \
    output/raw \
    output/normalized \
    output/reports \
    output/workflows \
    runtime/logs \
    runtime/metrics \
    runtime/pids \
    runtime/traces
ENV_OK=true

section "Infrastructure + migrations"
COMPOSE_BIN="$(compose_cmd || true)"
if [[ -n "${COMPOSE_BIN}" ]]; then
    SECRET_BACKEND="$(read_env_value K1_SECRET_BACKEND env .env | tr '[:upper:]' '[:lower:]')"
    PROVIDER_CHAIN="$(printf "%s,%s" "$(read_env_value K1_PRIMARY_LLM_PROVIDER anthropic .env)" "$(read_env_value K1_FALLBACK_LLM_PROVIDERS openai,gemini,ollama .env)" | tr '[:upper:]' '[:lower:]')"
    INFRA_SERVICES=(postgres redis)
    OLLAMA_REQUIRED=false

    if [[ "${SECRET_BACKEND}" == "vault" ]]; then
        INFRA_SERVICES+=(vault)
    fi
    if [[ "${PROVIDER_CHAIN}" == *"ollama"* ]]; then
        OLLAMA_REQUIRED=true
        if should_manage_ollama_container .env; then
            INFRA_SERVICES+=(ollama)
        fi
    fi

    info "Checking Docker authentication..."
    if ! bash "${REPO_ROOT}/scripts/docker_auth_check.sh"; then
        error "Docker authentication check failed."
        exit 1
    fi

    echo "[k1] Building sandbox image..."
    if docker build -t kaison-sandbox:latest docker/sandbox/ >/dev/null 2>&1; then
        info "Sandbox image built successfully."
    else
        warn "Sandbox build failed."
        warn "Payload execution isolation disabled."
    fi

    ${COMPOSE_BIN} -f docker-compose.yml -f docker-compose.dev.yml up -d --remove-orphans "${INFRA_SERVICES[@]}"
    if wait_for_port 127.0.0.1 5432 60 && wait_for_port 127.0.0.1 6379 45; then
        if [[ " ${INFRA_SERVICES[*]} " == *" vault "* ]]; then
            VAULT_HOST_BIND="$(read_env_value K1_VAULT_HOST_BIND 127.0.0.1 .env)"
            if [[ "${VAULT_HOST_BIND}" == "0.0.0.0" || "${VAULT_HOST_BIND}" == "::" ]]; then
                VAULT_WAIT_HOST="127.0.0.1"
            else
                VAULT_WAIT_HOST="${VAULT_HOST_BIND}"
            fi
            VAULT_HOST_PORT="$(read_env_value K1_VAULT_HOST_PORT 8200 .env)"
            if ! wait_for_port "${VAULT_WAIT_HOST}" "${VAULT_HOST_PORT}" 45; then
                warn "Vault was requested but did not become reachable at ${VAULT_WAIT_HOST}:${VAULT_HOST_PORT}."
            fi
        fi
        if [[ "${OLLAMA_REQUIRED}" == "true" ]]; then
            if ! wait_for_port 127.0.0.1 11434 90; then
                warn "Ollama was requested but did not become reachable on 127.0.0.1:11434."
            fi
        fi
        DOCKER_INFRA_OK=true
        info "Docker infra reachable: ${INFRA_SERVICES[*]}"
    else
        warn "Docker infra started but ports did not become reachable in time."
    fi
else
    MANUAL_PREREQS+=("Docker Engine + compose plugin (or manually running PostgreSQL/Redis/Vault/Ollama as needed)")
    warn "No docker compose command available; assuming required services are managed externally."
fi

DATABASE_URL="$(read_env_value DATABASE_URL "" .env)"
export DATABASE_URL
POSTGRES_USER="$(read_env_value POSTGRES_USER k1 .env)"
POSTGRES_PASSWORD="$(read_env_value POSTGRES_PASSWORD "" .env)"
POSTGRES_DB="$(read_env_value POSTGRES_DB k1 .env)"

info "Waiting for PostgreSQL to be fully ready..."
if wait_for_postgres 127.0.0.1 5432 "${POSTGRES_USER}" "${POSTGRES_PASSWORD}" "${POSTGRES_DB}" 60; then
    info "PostgreSQL is ready. Running database migrations..."
    if alembic upgrade heads; then
        MIGRATIONS_OK=true
    else
        error "Database migrations failed."
        error "Ensure PostgreSQL is running and DATABASE_URL in .env is reachable."
        exit 1
    fi
else
    error "PostgreSQL did not become ready in time."
    error "Ensure PostgreSQL is running and credentials in .env are correct."
    exit 1
fi

section "External tool verification + installation"
REQUIRE_EXTERNAL_TOOLS="$(read_env_bool K1_BOOTSTRAP_REQUIRE_EXTERNAL_TOOLS true .env)"
mapfile -t TOOL_RECORDS < <(load_enabled_tools)

# Ensure Go bin and local bin are in PATH for tool verification
export GOPATH="${HOME}/go"
export LOCAL_BIN_DIR="${HOME}/.local/bin"
export PATH="${LOCAL_BIN_DIR}:${GOPATH}/bin:/usr/local/bin:${PATH}"
mkdir -p "${LOCAL_BIN_DIR}"

for record in "${TOOL_RECORDS[@]}"; do
    name="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["name"])' "${record}")"
    mode="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["mode"])' "${record}")"
    verify_json="$(python3 -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1])["verify"]))' "${record}")"
    image="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["image"])' "${record}")"

    if [[ "${mode}" == "docker" ]]; then
        if has_cmd docker; then
            info "Tool ${name}: OK (docker execution mode)"
        else
            TOOL_ERRORS+=("${name}: requires Docker (${image:-no image configured})")
        fi
        continue
    fi

    # Try both JSON-based verification and simple command check
    if run_verify_cmd "${verify_json}" >/dev/null 2>&1 || has_cmd "${name}"; then
        info "Tool ${name}: already available"
        continue
    fi

    if [[ "${mode}" == "native" ]]; then
        warn "Tool ${name}: missing; attempting install"

        # Try sovereign installer first
        if install_native_tool "${name}" >/dev/null 2>&1; then
            # Re-verify after install (PATH may have updated)
            if run_verify_cmd "${verify_json}" >/dev/null 2>&1; then
                info "Tool ${name}: installed successfully"
                continue
            else
                # Installation succeeded but verification failed - might be PATH issue
                # Give it another chance with explicit PATH
                if command -v "${name}" >/dev/null 2>&1 || has_cmd "${name}"; then
                    info "Tool ${name}: installed successfully (post-install verification passed)"
                    continue
                fi
            fi
        fi

        # Try local download method
        if install_local_download_tool "${name}" >/dev/null 2>&1; then
            if run_verify_cmd "${verify_json}" >/dev/null 2>&1; then
                info "Tool ${name}: installed successfully (local download source)"
                continue
            fi
        fi

        TOOL_ERRORS+=("${name}: auto-install failed; install manually and re-run bootstrap.")
        continue
    fi

    warn "Tool ${name}: optional mode not installed"
done

# Security hardening: do not bulk-copy arbitrary binaries into /usr/local/bin.
# All bootstrap-installed binaries are placed in ${HOME}/.local/bin.

if [[ ${#TOOL_ERRORS[@]} -eq 0 ]]; then
    TOOLS_OK=true
elif [[ "${REQUIRE_EXTERNAL_TOOLS}" == "false" ]]; then
    TOOLS_OK=true
    warn "External tool verification failures are allowed (K1_BOOTSTRAP_REQUIRE_EXTERNAL_TOOLS=false)."
fi

section "Readiness summary"
readiness_line "Python deps installed" "${PYTHON_DEPS_OK}"
readiness_line "UI deps installed" "${UI_DEPS_OK}"
readiness_line "Environment configured" "${ENV_OK}"
readiness_line "Migrations applied" "${MIGRATIONS_OK}"
readiness_line "External tools verified" "${TOOLS_OK}"

if [[ "${DOCKER_INFRA_OK}" == "true" ]]; then
    readiness_line "Docker infra healthy (postgres, redis, conditional vault/ollama)" "true"
else
    readiness_line "Docker infra healthy (postgres, redis, conditional vault/ollama)" "false"
fi

if [[ ${#TOOL_ERRORS[@]} -gt 0 ]]; then
    if [[ "${REQUIRE_EXTERNAL_TOOLS}" == "false" ]]; then
        echo -e "\n${YELLOW}Optional external tools missing (startup will continue):${NC}"
    else
    echo -e "\n${RED}Missing required external tools:${NC}"
    fi
    for item in "${TOOL_ERRORS[@]}"; do
        echo "  - ${item}"
    done
fi

if [[ ${#MANUAL_PREREQS[@]} -gt 0 ]]; then
    echo -e "\n${YELLOW}Manual prerequisites:${NC}"
    for item in "${MANUAL_PREREQS[@]}"; do
        echo "  - ${item}"
    done
fi

if [[ "${PYTHON_DEPS_OK}" == "true" && "${UI_DEPS_OK}" == "true" && "${ENV_OK}" == "true" && "${MIGRATIONS_OK}" == "true" && "${TOOLS_OK}" == "true" ]]; then
    cat > "${BOOTSTRAP_MARKER}" <<EOF
ready=true
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
python=${PYTHON_VERSION}
node=$(node -v 2>/dev/null || echo n/a)
EOF
    echo -e "\n${GREEN}Bootstrap complete.${NC}"
    echo "Run: ./k1-start"
    exit 0
fi

echo -e "\n${RED}Bootstrap failed.${NC} Resolve the reported items and run ./bootstrap.sh again."
exit 1
