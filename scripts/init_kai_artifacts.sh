#!/usr/bin/env bash
set -euo pipefail

STORAGE_ROOT="${KAI_STORAGE_ROOT:-/srv/kai}"
ARTIFACTS_ROOT="${K1_ARTIFACTS_HOST_ROOT:-${STORAGE_ROOT}/artifacts}"
OUTPUT_ROOT="${K1_WORKFLOW_OUTPUT_ROOT:-${STORAGE_ROOT}/output}"
ARTIFACT_UID="${K1_ARTIFACTS_UID:-}"
ARTIFACT_GID="${K1_ARTIFACTS_GID:-}"

ARTIFACT_DIRS=(
  "audit"
  "usage"
  "telemetry"
  "workflows"
  "dork_runs"
  "reports"
  "submissions"
  "logs"
  "evidence"
  "cache"
  "knowledge"
  "decision"
  "reflection"
  "scan_configs"
  "api_key_allocations"
  "impact_validation"
  "api_intelligence"
  "vulnerability_intelligence"
  "comms"
)

OUTPUT_DIRS=(
  "logs"
  "audits"
  "health"
  "raw"
  "raw/workflows"
  "slow_mem"
)

DOCKER_DIRS=(
  "docker/postgres"
  "docker/redis"
  "docker/qdrant"
  "docker/frontend-node_modules"
)

echo "[init-kai-artifacts] Preparing storage root ${STORAGE_ROOT}"
mkdir -p "${ARTIFACTS_ROOT}"
mkdir -p "${OUTPUT_ROOT}"

for dir_name in "${ARTIFACT_DIRS[@]}"; do
  mkdir -p "${ARTIFACTS_ROOT}/${dir_name}"
done

for dir_name in "${OUTPUT_DIRS[@]}"; do
  mkdir -p "${OUTPUT_ROOT}/${dir_name}"
done

for dir_name in "${DOCKER_DIRS[@]}"; do
  mkdir -p "${STORAGE_ROOT}/${dir_name}"
done

# Use broad write permissions because tool containers run as different UIDs.
chmod 0755 "${ARTIFACTS_ROOT}"
chmod 0755 "${OUTPUT_ROOT}"
chmod 0777 "${ARTIFACTS_ROOT}"/* "${OUTPUT_ROOT}"/* "${STORAGE_ROOT}"/docker/* 2>/dev/null || true

if [[ -n "${ARTIFACT_UID}" && -n "${ARTIFACT_GID}" ]]; then
  chown -R "${ARTIFACT_UID}:${ARTIFACT_GID}" "${ARTIFACTS_ROOT}"
  chown -R "${ARTIFACT_UID}:${ARTIFACT_GID}" "${OUTPUT_ROOT}"
fi

echo "[init-kai-artifacts] Done"
