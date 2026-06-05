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
        sudo systemctl start docker || error "Failed to start Docker daemon."
        sudo systemctl enable docker || error "Failed to enable Docker to start on boot."
        success "Docker daemon started."
    else
        success "Docker daemon is running."
    fi

    # Add current user to docker group to run docker commands without sudo
    if ! groups | grep -q "docker"; then
        log "Adding current user to 'docker' group. You may need to log out and back in for this to take effect."
        sudo usermod -aG docker "$USER"
    fi
}

install_docker() {
    log "Installing Docker (via official convenience script)..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    success "Docker installed."
}

check_docker_compose_installed() {
    if docker compose version &> /dev/null; then
        COMPOSE_CMD=(docker compose)
        COMPOSE_DISPLAY_CMD="docker compose"
        success "docker compose is installed."
        return
    fi

    if command -v docker-compose &> /dev/null; then
        COMPOSE_CMD=(docker-compose)
        COMPOSE_DISPLAY_CMD="docker-compose"
        success "docker-compose is installed."
        return
    fi

    log "Docker Compose not found. Attempting to install legacy docker-compose..."
    install_docker_compose
    COMPOSE_CMD=(docker-compose)
    COMPOSE_DISPLAY_CMD="docker-compose"
}

install_docker_compose() {
    log "Installing docker-compose..."
    # This is the recommended way to install standalone docker-compose v1.x
    # The new 'docker compose' (v2) is part of Docker Desktop or a separate plugin.
    # Given the Python TypeError, we stick to standalone v1.x here if possible.
    sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    success "docker-compose installed."

    # NOTE: If 'docker compose' (v2) is desired and 'docker-compose' (v1) gives Python TypeError, 
    # user needs to install Docker Desktop or the Docker Compose plugin separately.
    warn "If 'docker-compose' (v1.x) experiences Python TypeErrors, consider installing 'docker compose' (v2) as a Docker plugin. See Docker documentation for details."
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

    log "Building Docker images for Kai services and tools..."
    if ! run_compose build; then
        fatal "Failed to build Docker images. Check logs."
    fi
    success "Docker images built."

    log "Bringing up Kai services..."
    if ! run_compose up -d; then
        fatal "Failed to bring up Docker services. Check logs."
    fi
    success "Kai services are up and running."

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  BOOTSTRAP SUMMARY"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    success "Kai Docker environment setup complete!"
    echo ""
    echo "Run '${COMPOSE_DISPLAY_CMD} ps' in ${SCRIPT_DIR} to see running containers."
    echo "You may need to log out and back in for Docker group changes to take effect."
    echo ""
    echo "Log saved to: $INSTALL_LOG"
}

# Run main
main "$@"
