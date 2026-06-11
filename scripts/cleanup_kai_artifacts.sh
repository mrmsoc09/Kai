#!/usr/bin/env bash
set -euo pipefail

ARTIFACTS_ROOT="${K1_ARTIFACTS_HOST_ROOT:-${KAI_STORAGE_ROOT:-/srv/kai}/artifacts}"
RETENTION_DAYS="${K1_ARTIFACT_RETENTION_DAYS:-14}"
MAX_BYTES_PER_TOOL="${K1_ARTIFACT_MAX_BYTES_PER_TOOL:-107374182400}"

TOOL_DIRS=(
  "nmap-output"
  "nuclei-output"
  "gitleaks-output"
  "burp-cache"
)

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

dir_size_bytes() {
  local target_dir="$1"
  if [[ ! -d "${target_dir}" ]]; then
    echo 0
    return
  fi
  du -sb "${target_dir}" 2>/dev/null | awk '{print $1}'
}

purge_old_files() {
  local target_dir="$1"
  find "${target_dir}" -type f -mtime "+${RETENTION_DAYS}" -print -delete 2>/dev/null || true
  find "${target_dir}" -type d -empty -delete 2>/dev/null || true
}

enforce_quota() {
  local target_dir="$1"
  local current_size
  current_size="$(dir_size_bytes "${target_dir}")"

  while [[ "${current_size}" -gt "${MAX_BYTES_PER_TOOL}" ]]; do
    local oldest_file
    oldest_file="$(
      find "${target_dir}" -type f -printf '%T@ %p\n' 2>/dev/null \
      | sort -n \
      | head -n 1 \
      | cut -d' ' -f2-
    )"

    if [[ -z "${oldest_file}" ]]; then
      break
    fi

    rm -f -- "${oldest_file}"
    log "quota-delete ${oldest_file}"
    current_size="$(dir_size_bytes "${target_dir}")"
  done
}

main() {
  log "cleanup-start root=${ARTIFACTS_ROOT} retention_days=${RETENTION_DAYS} max_bytes=${MAX_BYTES_PER_TOOL}"

  for tool_dir in "${TOOL_DIRS[@]}"; do
    local local_dir="${ARTIFACTS_ROOT}/${tool_dir}"
    if [[ ! -d "${local_dir}" ]]; then
      log "skip-missing ${local_dir}"
      continue
    fi

    purge_old_files "${local_dir}"
    enforce_quota "${local_dir}"
    log "cleanup-complete ${local_dir} size_bytes=$(dir_size_bytes "${local_dir}")"
  done

  log "cleanup-finished"
}

main "$@"
