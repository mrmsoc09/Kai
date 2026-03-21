#!/bin/bash
# Kai Platform Stop
# Usage: ./scripts/k1-stop.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}[*] Stopping Kai Platform Services...${NC}"

# 1. Stop API Server
if [ -f "runtime/api.pid" ]; then
    PID=$(cat runtime/api.pid)
    echo -e "${YELLOW}[*] Stopping API (PID: $PID)...${NC}"
    kill $PID 2>/dev/null || echo -e "${RED}[!] Could not kill API. Check if running.${NC}"
    rm runtime/api.pid
else
    echo -e "${GREEN}[+] API PID file not found. Assuming stopped.${NC}"
fi

# 2. Stop Celery Worker
if [ -f "runtime/worker.pid" ]; then
    PID=$(cat runtime/worker.pid)
    echo -e "${YELLOW}[*] Stopping Worker (PID: $PID)...${NC}"
    kill $PID 2>/dev/null || echo -e "${RED}[!] Could not kill Worker. Check if running.${NC}"
    rm runtime/worker.pid
else
    echo -e "${GREEN}[+] Worker PID file not found. Assuming stopped.${NC}"
fi

# Optional cleanup: kill any orphaned python/celery processes if PID files were missing?
# Probably safer not to, unless explicitly requested.

echo -e "${GREEN}[+] Services Stopped.${NC}"
