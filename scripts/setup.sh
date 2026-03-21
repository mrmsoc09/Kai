#!/bin/bash
# Kai Platform Setup
# Usage: ./scripts/setup.sh

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}[+] Starting Kai Platform Setup...${NC}"

# 1. Check Python Version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[!] Python 3 is not installed.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}[+] Detected Python version: $PYTHON_VERSION${NC}"

# 2. Create Virtual Environment
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}[*] Creating virtual environment (.venv)...${NC}"
    python3 -m venv .venv
else
    echo -e "${GREEN}[+] Virtual environment exists.${NC}"
fi

# Activate venv for subsequent commands
source .venv/bin/activate

# 3. Install Dependencies
echo -e "${YELLOW}[*] Installing dependencies...${NC}"
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo -e "${RED}[!] requirements.txt not found!${NC}"
    exit 1
fi

if [ -f "requirements-dev.txt" ]; then
    echo -e "${YELLOW}[*] Installing dev dependencies...${NC}"
    pip install -r requirements-dev.txt
fi

# 4. Environment Configuration
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}[*] .env not found. Creating from .env.example...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}[+] Created .env file. PLEASE EDIT IT with your credentials.${NC}"
    else
        echo -e "${RED}[!] .env.example not found!${NC}"
    fi
else
    echo -e "${GREEN}[+] .env file exists.${NC}"
fi

# 5. Prepare Directories
echo -e "${YELLOW}[*] Creating artifact directories...${NC}"
mkdir -p output/logs output/raw output/normalized output/reports output/workflows
mkdir -p runtime/logs runtime/metrics runtime/traces

# 6. Database Migrations
echo -e "${YELLOW}[*] Running database migrations...${NC}"
# Check if alembic is installed in venv
if command -v alembic &> /dev/null; then
    alembic upgrade head
    echo -e "${GREEN}[+] Migrations complete.${NC}"
else
    echo -e "${RED}[!] Alembic not found in path. Ensure requirements are installed.${NC}"
fi

echo -e "${GREEN}[+] Setup Complete!${NC}"
echo -e "You can now start the platform with: ${YELLOW}./scripts/k1-start.sh${NC}"
