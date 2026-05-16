#!/usr/bin/env bash
set -euo pipefail

ARTIFACTS_ROOT="${K1_ARTIFACTS_HOST_ROOT:-/var/kai-artifacts}"
ARTIFACT_UID="${K1_ARTIFACTS_UID:-}"
ARTIFACT_GID="${K1_ARTIFACTS_GID:-}"

TOOL_DIRS=(
  "nmap-output"
  "nuclei-output"
  "gitleaks-output"
  "burp-cache"
  "cache"
)

echo "[init-kai-artifacts] Preparing ${ARTIFACTS_ROOT}"
mkdir -p "${ARTIFACTS_ROOT}"

for dir_name in "${TOOL_DIRS[@]}"; do
  mkdir -p "${ARTIFACTS_ROOT}/${dir_name}"
done

# Use broad write permissions because tool containers run as different UIDs.
chmod 0755 "${ARTIFACTS_ROOT}"
chmod 0777 "${ARTIFACTS_ROOT}"/*

if [[ -n "${ARTIFACT_UID}" && -n "${ARTIFACT_GID}" ]]; then
  chown -R "${ARTIFACT_UID}:${ARTIFACT_GID}" "${ARTIFACTS_ROOT}"
fi

echo "[init-kai-artifacts] Done"
