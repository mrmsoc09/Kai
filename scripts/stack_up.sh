#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/k1/deploy/docker-compose.dev.yml"
if ! command -v docker >/dev/null 2>&1; then echo "Docker not installed" >&2; exit 2; fi
if ! docker compose version >/dev/null 2>&1; then echo "docker compose plugin missing" >&2; exit 3; fi
cd "$PROJECT_ROOT"
set -x
docker compose -f "$COMPOSE_FILE" up -d --pull always --force-recreate
set +x
# Basic readiness checks
wait_http(){ url="$1"; name="$2"; max=${3:-180}; echo "Waiting for $name at $url"; for i in $(seq 1 "$max"); do curl -skf "$url" >/dev/null 2>&1 && { echo "$name up"; return 0; }; sleep 1; done; echo "Timeout $name" >&2; return 1; }
wait_tcp(){ port="$1"; name="$2"; max=${3:-180}; echo "Waiting for $name port $port"; for i in $(seq 1 "$max"); do nc -z 127.0.0.1 "$port" >/dev/null 2>&1 && { echo "$name up"; return 0; }; sleep 1; done; echo "Timeout $name" >&2; return 1; }
wait_tcp 5432 Postgres 120 || true
wait_http http://localhost:6333/readyz Qdrant 120 || true
wait_tcp 6379 Redis 120 || true
wait_http "http://localhost:8200/v1/sys/health?standbyok=true&perfstandbyok=true" Vault 180 || true
wait_http http://localhost:9200 Elasticsearch 180 || true
wait_tcp 9042 Cassandra 240 || true
wait_http http://localhost:9000 TheHive 300 || true
wait_http http://localhost:8080/healthz Backend 180 || true
wait_http http://localhost:8081 Frontend 180 || true

echo "Stack up complete. Run k1/scripts/smoke_e2e.sh next."
