#!/bin/bash

################################################################################
# Kaison K1 - Enterprise Bootstrap & System Preparation
# 
# Purpose: Prepare host environment and sync K1 Platform
# Repository: https://github.com/mrmsoc09/Kai.git
################################################################################

set -e

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

REPO_URL="https://github.com/mrmsoc09/Kai.git"
INSTALL_DIR="$HOME/Kai"

print_header() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║ $1${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}\n"
}

# 1. System Updates & VS Code Fix
print_header "1. UPDATING SYSTEM"
if [ -f /etc/apt/sources.list.d/vscode.list ]; then
    echo "Standardizing VS Code security keys..."
    sudo sed -i 's|/usr/share/keyrings/microsoft.gpg|/etc/apt/keyrings/packages.microsoft.gpg|g' /etc/apt/sources.list.d/vscode.list 2>/dev/null || true
fi
sudo apt update && sudo apt install -y python3 python3-pip git

# 2. Infrastructure Verification
print_header "2. VERIFYING DOCKER ENVIRONMENT"
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}⚠ Docker not found in PATH. Please ensure it is installed and your user is in the 'docker' group.${NC}"
else
    echo -e "${GREEN}✓ Docker detected: $(docker --version)${NC}"
fi

# 3. Repository Synchronization
print_header "3. SYNCHRONIZING REPOSITORY"
if [ ! -d "$INSTALL_DIR/.git" ]; then
    echo "Cloning Kaison K1 from $REPO_URL..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
else
    echo "Updating existing K1 installation..."
    git remote set-url origin "$REPO_URL"
    git pull origin main || echo "Already up to date."
fi

# 4. Final Permissions
print_header "4. CONFIGURING PERMISSIONS"
chmod +x k1

print_header "🎉 BOOTSTRAP COMPLETE!"
echo -e "${GREEN}System is ready for Kaison K1.${NC}"
echo -e "To launch the platform, run:"
echo -e "${BLUE}   ./k1 start${NC}"
echo ""
