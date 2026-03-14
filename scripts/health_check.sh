#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8080}"

echo "Checking ${BACKEND_URL}/healthz"
curl -fsS "${BACKEND_URL}/healthz" | jq .

echo "Checking tool catalog endpoint"
curl -fsS "${BACKEND_URL}/api/v1/tools/catalog/list?enabled_only=true" | jq '.success, .data.count'

echo "Health check completed."
