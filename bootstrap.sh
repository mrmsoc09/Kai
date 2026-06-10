#!/bin/bash
###############################################################################
# KAISONONE BOOTSTRAP SCRIPT (Docker-focused)
# Sets up Docker, docker-compose, and builds initial Kai platform images.
# Usage: ./bootstrap.sh
###############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_LOG="${SCRIPT_DIR}/output/logs/bootstrap.log"
COMPOSE_CMD=()
COMPOSE_DISPLAY_CMD=""
BOOTSTRAP_MODE="${KAI_BOOTSTRAP_MODE:-core}"
RUN_USER="${SUDO_USER:-$USER}"
CORE_SERVICES=(
    postgres
    redis
    qdrant
    orchestrator
    admin_gui
)

###############################################################################
# Helper Functions
###############################################################################

emit() {
    local line="$1"
    echo -e "$line"
    { printf '%b\n' "$line" >> "$INSTALL_LOG"; } 2>/dev/null || true
}

log() {
    emit "${BLUE}[$(date +%H:%M:%S)]${NC} $1"
}

success() {
    emit "${GREEN}[✓]${NC} $1"
}

warn() {
    emit "${YELLOW}[!]${NC} $1"
}

error() {
    emit "${RED}[✗]${NC} $1"
}

fatal() {
    error "$1"
    exit 1
}

run_root() {
    if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

prepare_log_path() {
    local log_dir owner group
    log_dir="$(dirname "$INSTALL_LOG")"
    mkdir -p "$log_dir"
    touch "$INSTALL_LOG" 2>/dev/null || true

    if [[ -n "${SUDO_USER:-}" ]]; then
        owner="$SUDO_USER"
        group="$(id -gn "$SUDO_USER" 2>/dev/null || true)"
        if [[ -n "$group" ]]; then
            chown "$owner:$group" "$log_dir" "$INSTALL_LOG" 2>/dev/null || true
        fi
    fi
}

load_env_file() {
    local env_file line key value
    env_file="$1"

    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line#"${line%%[![:space:]]*}"}"
        [[ -z "$line" || "${line:0:1}" == "#" ]] && continue

        if [[ "$line" == export\ * ]]; then
            line="${line#export }"
        fi

        [[ "$line" == *=* ]] || continue
        key="${line%%=*}"
        value="${line#*=}"

        if [[ "$value" =~ ^\".*\"$ || "$value" =~ ^\'.*\'$ ]]; then
            value="${value:1:${#value}-2}"
        fi

        export "$key=$value"
    done < "$env_file"
}

load_compose_env() {
    local env_file
    for env_file in "$SCRIPT_DIR/.env" "$SCRIPT_DIR/.env.vault"; do
        if [[ -f "$env_file" ]]; then
            load_env_file "$env_file"
        fi
    done
}

run_compose() {
    (
        cd "$SCRIPT_DIR"
        load_compose_env
        "${COMPOSE_CMD[@]}" "$@"
    )
}

check_docker_installed() {
    if ! command -v docker &> /dev/null; then
        log "Docker not found. Attempting to install..."
        install_docker
    else
        success "Docker is installed."
    fi

    if ! systemctl is-active --quiet docker; then
        log "Docker daemon not running. Attempting to start..."
        run_root systemctl start docker || error "Failed to start Docker daemon."
        run_root systemctl enable docker || error "Failed to enable Docker to start on boot."
        success "Docker daemon started."
    else
        success "Docker daemon is running."
    fi

    # Add current user to docker group to run docker commands without sudo
    if id -nG "$RUN_USER" 2>/dev/null | tr ' ' '\n' | grep -qx "docker"; then
        success "User '${RUN_USER}' is already in the docker group."
    else
        log "Adding '${RUN_USER}' to the 'docker' group. You may need to log out and back in for this to take effect."
        run_root usermod -aG docker "$RUN_USER"
    fi
}

install_docker() {
    log "Installing Docker (via official convenience script)..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    run_root sh get-docker.sh
    rm get-docker.sh
    success "Docker installed."
}

check_docker_compose_installed() {
    if docker compose version &> /dev/null; then
        COMPOSE_CMD=(docker compose)
        COMPOSE_DISPLAY_CMD="docker compose"
        success "docker compose (v2) is installed."
        return
    fi

    if command -v docker-compose &> /dev/null; then
        COMPOSE_CMD=(docker-compose)
        COMPOSE_DISPLAY_CMD="docker-compose"
        success "docker-compose (v1) is installed."
        return
    fi

    fatal "Docker Compose (v2) not found. Please ensure your Docker installation is up-to-date and includes the 'compose' plugin. You can often install or update Docker by running the Docker convenience script: 'curl -fsSL https://get.docker.com | sh'. Then, you may need to log out and back in, or restart your system, for changes to take effect."
}

compose_targets() {
    case "$BOOTSTRAP_MODE" in
        core)
            printf '%s\n' "${CORE_SERVICES[@]}"
            ;;
        full)
            return 0
            ;;
        *)
            fatal "Unsupported KAI_BOOTSTRAP_MODE='$BOOTSTRAP_MODE'. Expected 'core' or 'full'."
            ;;
    esac
}

###############################################################################
# Main Entry Point
###############################################################################

main() {
    echo "═══════════════════════════════════════════════════════════════"
    echo "  KAISONONE BOOTSTRAP - Docker Environment Setup"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    prepare_log_path

    log "Starting Docker environment setup..."

    # Check and install Docker
    check_docker_installed

    # Check and install docker-compose
    check_docker_compose_installed

    mapfile -t targets < <(compose_targets)
    if [[ "$BOOTSTRAP_MODE" == "core" ]]; then
        log "Bootstrapping core Kai stack only (mode=${BOOTSTRAP_MODE}): ${targets[*]}"
        if ! run_compose up -d --build "${targets[@]}"; then
            fatal "Failed to build and bring up core Docker services. Check logs."
        fi
        success "Core Kai services are up and running."
    else
        log "Building Docker images for the full Kai service fleet (mode=${BOOTSTRAP_MODE})..."
        if ! run_compose build; then
            fatal "Failed to build Docker images. Check logs."
        fi
        success "Docker images built."

        log "Bringing up Kai services..."
        if ! run_compose up -d; then
            fatal "Failed to bring up Docker services. Check logs."
        fi
        success "Kai services are up and running."
    fi

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  BOOTSTRAP SUMMARY"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    success "Kai Docker environment setup complete!"
    echo ""
    echo "Run '${COMPOSE_DISPLAY_CMD} ps' in ${SCRIPT_DIR} to see running containers."
    echo "You may need to log out and back in for Docker group changes to take effect."
    if [[ "$BOOTSTRAP_MODE" == "core" ]]; then
        echo "Optional tool containers were skipped. Run with 'KAI_BOOTSTRAP_MODE=full' to build the entire tool fleet."
    fi
    echo ""
    echo "Log saved to: $INSTALL_LOG"
}

# Run main
main "$@"
