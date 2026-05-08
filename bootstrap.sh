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

###############################################################################
# Helper Functions
###############################################################################

log() {
    echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $1" | tee -a "$INSTALL_LOG"
}

success() {
    echo -e "${GREEN}[✓]${NC} $1" | tee -a "$INSTALL_LOG"
}

warn() {
    echo -e "${YELLOW}[!]${NC} $1" | tee -a "$INSTALL_LOG"
}

error() {
    echo -e "${RED}[✗]${NC} $1" | tee -a "$INSTALL_LOG"
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
    if ! command -v docker-compose &> /dev/null; then
        log "docker-compose not found. Attempting to install..."
        install_docker_compose
    else
        success "docker-compose is installed."
    fi
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

    # Create log directory
    mkdir -p "$(dirname "$INSTALL_LOG")"

    log "Starting Docker environment setup..."

    # Check and install Docker
    check_docker_installed

    # Check and install docker-compose
    check_docker_compose_installed

    log "Building Docker images for Kai services and tools..."
    # Navigate to the project root where docker-compose.yml is located
    (cd "$SCRIPT_DIR" && docker-compose build) || error "Failed to build Docker images. Check logs."
    success "Docker images built."

    log "Bringing up Kai services..."
    (cd "$SCRIPT_DIR" && docker-compose up -d) || error "Failed to bring up Docker services. Check logs."
    success "Kai services are up and running."

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  BOOTSTRAP SUMMARY"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    success "Kai Docker environment setup complete!"
    echo ""
    echo "Run 'docker-compose ps' in ${SCRIPT_DIR} to see running containers."
    echo "You may need to log out and back in for Docker group changes to take effect."
    echo ""
    echo "Log saved to: $INSTALL_LOG"
}

# Run main
main "$@"
