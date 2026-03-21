#!/bin/bash
# Kai Platform Start
# Usage: ./scripts/k1-start.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if setup has run
if [ ! -d ".venv" ]; then
    echo -e "${RED}[!] Virtual environment not found. Please run ./scripts/setup.sh first.${NC}"
    exit 1
fi

source .venv/bin/activate

# Ensure runtime directory exists
mkdir -p runtime

echo -e "${GREEN}[+] Starting Kai Platform Services...${NC}"

# 1. Start API Server
if [ -f "runtime/api.pid" ]; then
    echo -e "${YELLOW}[!] API seems to be running (PID file exists). check runtime/api.pid${NC}"
else
    echo -e "${YELLOW}[*] Starting API Server (port 8080)...${NC}"
    nohup python3 -m uvicorn apps.backend.src.main:app --host 0.0.0.0 --port 8080 > runtime/logs/api.log 2>&1 &
    echo $! > runtime/api.pid
    echo -e "${GREEN}[+] API started (PID: $(cat runtime/api.pid))${NC}"
fi

# 2. Start Celery Worker
if [ -f "runtime/worker.pid" ]; then
    echo -e "${YELLOW}[!] Worker seems to be running (PID file exists). check runtime/worker.pid${NC}"
else
    echo -e "${YELLOW}[*] Starting Celery Worker...${NC}"
    nohup celery -A apps.backend.src.worker.celery_app.celery_app worker -Q tools,intrusive --loglevel=info > runtime/logs/worker.log 2>&1 &
    echo $! > runtime/worker.pid
    echo -e "${GREEN}[+] Worker started (PID: $(cat runtime/worker.pid))${NC}"
fi

# 3. Frontend Operator (Optional/Check)
# We won't start the frontend here as it's nodejs and usually run separately or dev mode.
# But we can print instructions.

echo -e "\n${GREEN}[SUCCESS] Platform is running!${NC}"
echo -e "----------------------------------------"
echo -e "API Endpoint:   http://localhost:8080"
echo -e "API Docs:       http://localhost:8080/docs"
echo -e "Logs:           runtime/logs/"
echo -e "Stop with:      ./scripts/k1-stop.sh"
echo -e "----------------------------------------"
