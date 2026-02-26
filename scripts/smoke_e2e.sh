#!/usr/bin/env bash
set -euo pipefail
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
\n# HiL end-to-end (best-effort, requires backend)\nUSER_KEY=${USER_API_KEY:-user_secret_key_default}\nADMIN_KEY=${ADMIN_API_KEY:-admin_secret_key_default}\nCREATE_PAYLOAD='{"program":"google_vrp","asset":"scope","title":"smoke finding","description":"infra smoke","severity":"LOW"}'\nCF=$(curl -sk -X POST "$API_BASE/findings/" -H "X-API-Key: $USER_KEY" -H 'Content-Type: application/json' -d "$CREATE_PAYLOAD" || true)\nFID=$(echo "$CF" | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*"\([^"]\+\)".*/\1/p')\nif [ -n "$FID" ]; then\n  echo "Created finding: $FID"\n  # Add minimal evidence with fake sha (32 bytes hex)\n  curl -sk -X POST "$API_BASE/findings/$FID/evidence" -H "X-API-Key: $USER_KEY" -H 'Content-Type: application/json' \\\n    -d '{"kind":"http_trace","uri":"file:///artifacts/trace1.json","sha256_hex":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}' >/dev/null || true\n  # Request HiL\n  curl -sk -X POST "$API_BASE/hil/findings/$FID/request" -H "X-API-Key: $USER_KEY" -H 'Content-Type: application/json' -d '{"notes":"smoke"}' >/dev/null || true\n  # Approve HiL (admin)\n  curl -sk -X POST "$API_BASE/hil/findings/$FID/approve" -H "X-API-Key: $ADMIN_KEY" -H 'Content-Type: application/json' \\\n    -d '{"checklist": {"repro_steps":true,"http_traces_or_logs":true,"poc_or_screencap":true,"scope_confirmation":true,"impact_rationale":true}}' >/dev/null || true\n  # Submit (will call TheHive; may fail if API key not set)\n  curl -sk -X POST "$API_BASE/hil/findings/$FID/submit" -H "X-API-Key: $USER_KEY" -H 'Content-Type: application/json' \\\n    -d '{"report_content_hash_hex":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}' || true\nfi\n
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
