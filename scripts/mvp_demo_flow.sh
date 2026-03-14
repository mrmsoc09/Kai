#!/usr/bin/env bash
set -euo pipefail

API_URL="${K1_API_URL:-http://localhost:8080}"
PAYLOAD_PATH="${1:-config/mvp_program_example.json}"
TEMPLATE="${MVP_TEMPLATE:-workflow_recon_surface_map}"

if ! command -v jq >/dev/null 2>&1; then
  echo "[mvp] jq is required for demo flow output parsing" >&2
  exit 2
fi

echo "[mvp] checking backend readiness: ${API_URL}/healthz"
curl -fsS "${API_URL}/healthz" >/dev/null

AUTH_HEADER=()
if [[ -n "${K1_API_TOKEN:-}" ]]; then
  AUTH_HEADER=(-H "Authorization: Bearer ${K1_API_TOKEN}")
elif [[ -n "${K1_DEV_TOKEN:-}" ]]; then
  echo "[mvp] bootstrapping API access token from /auth/login"
  ACCESS_TOKEN="$(curl -fsS -X POST "${API_URL}/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"token\":\"${K1_DEV_TOKEN}\"}" | jq -r '.access_token // empty')"
  if [[ -z "${ACCESS_TOKEN}" ]]; then
    echo "[mvp] unable to bootstrap access token; set K1_API_TOKEN or valid K1_DEV_TOKEN" >&2
    exit 2
  fi
  AUTH_HEADER=(-H "Authorization: Bearer ${ACCESS_TOKEN}")
else
  echo "[mvp] missing auth configuration; set K1_API_TOKEN or K1_DEV_TOKEN" >&2
  exit 2
fi

echo "[mvp] applying demo seed"
python3 scripts/seed_mvp_demo.py \
  --api-url "${API_URL}" \
  --payload "${PAYLOAD_PATH}" \
  --template "${TEMPLATE}" \
  --apply \
  --trigger-run \
  --create-case-from-first-alert

echo "[mvp] fetching summary surfaces"
curl -fsS "${AUTH_HEADER[@]}" "${API_URL}/api/v1/bug-bounty/programs" | jq 'length'
curl -fsS "${AUTH_HEADER[@]}" "${API_URL}/api/v1/bug-bounty/candidates?limit=20" | jq 'length'
curl -fsS "${AUTH_HEADER[@]}" "${API_URL}/api/v1/bug-bounty/alerts?limit=20" | jq 'length'
curl -fsS "${AUTH_HEADER[@]}" "${API_URL}/api/v1/bug-bounty/cases?limit=20" | jq 'length'
curl -fsS "${AUTH_HEADER[@]}" "${API_URL}/api/v1/bug-bounty/phase7/opportunity-rankings?limit=20" | jq 'length'

echo "[mvp] demo flow completed"
