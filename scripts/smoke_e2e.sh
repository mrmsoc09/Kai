#!/usr/bin/env bash
set -euo pipefail
echo "[legacy] scripts/smoke_e2e.sh is a compatibility path."
echo "[legacy] prefer scripts/frontend_smoke.sh and scripts/mvp_demo_flow.sh for MVP validation."
API_BASE="${API_BASE:-http://localhost:8080}"
TARGET="${TARGET:-}"
# Infra checks
check(){ name="$1"; url="$2"; echo "[CHECK] $name -> $url"; if curl -skf "$url" >/dev/null 2>&1; then echo " OK"; else echo " FAIL"; fi }
check Postgres http://localhost:5432 || true
check Qdrant http://localhost:6333/readyz || true
check Redis http://localhost:6379 || true
check Vault "http://localhost:8200/v1/sys/health?standbyok=true&perfstandbyok=true" || true
check Elasticsearch http://localhost:9200 || true
check TheHive http://localhost:9000 || true
check Frontend http://localhost:8081 || true
# Backend health (best effort)
if curl -skf "$API_BASE/healthz" >/dev/null 2>&1; then echo "Backend health OK"; else echo "Backend health endpoint not reachable (continuing)"; fi
# HiL roundtrip (best effort)
if command -v jq >/dev/null 2>&1; then
  R=$(curl -sk -X POST "$API_BASE/findings" -H 'Content-Type: application/json' -d '{"title":"smoke finding","severity":"low","summary":"infra smoke","status":"draft"}' || true)
  ID=$(echo "$R" | jq -r '.id // .finding_id // empty')
  if [[ -n "${ID:-}" ]]; then
    echo "Created finding: $ID"
    curl -sk -X POST "$API_BASE/hil/findings" -H 'Content-Type: application/json' -d "{\"finding_id\":\"$ID\"}" >/dev/null || true
  fi
fi
# Scope guard
if [[ -n "${TARGET}" ]]; then
  if [[ "${ACCEPT_SCOPE:-0}" != "1" ]]; then
    echo "Refusing to touch target without ACCEPT_SCOPE=1"; exit 4
  fi
  echo "[SCOPE-ENFORCED] Planner would run against: $TARGET"
fi
# Show compose status
COMPOSE_FILE="$(cd "$(dirname "$0")/../.." && pwd)/k1/deploy/docker-compose.dev.yml"
docker compose -f "$COMPOSE_FILE" ps
