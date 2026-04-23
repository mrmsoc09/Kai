#!/usr/bin/env bash
# setup_kai_dual_env.sh
# Idempotent dual-environment setup:
# - Keep /home/k1-admin/Kai as development workspace
# - Maintain a runnable copy on external storage
# - Keep runtime-generated data/logs on external storage

set -Eeuo pipefail

SOURCE_REPO="${SOURCE_REPO:-/home/k1-admin/Kai}"
RUNTIME_MOUNT="${RUNTIME_MOUNT:-/mnt/kai-runtime}"
RUNTIME_REPO="${RUNTIME_REPO:-${RUNTIME_MOUNT}/apps/Kai-runtime}"
STATE_DIR="${STATE_DIR:-${RUNTIME_MOUNT}/state}"
SCRIPT_DIR="${SCRIPT_DIR:-${RUNTIME_MOUNT}/scripts}"
SYNC_LOG="${SYNC_LOG:-${STATE_DIR}/runtime_sync.log}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_UI_DEPS="${INSTALL_UI_DEPS:-true}"
INSTALL_DEV_DEPS="${INSTALL_DEV_DEPS:-false}"

log() {
  mkdir -p "${STATE_DIR}"
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "${SYNC_LOG}"
}

fail() {
  echo "[ERROR] $*" >&2
  exit 1
}

require_prereqs() {
  command -v rsync >/dev/null 2>&1 || fail "rsync is required."
  command -v "${PYTHON_BIN}" >/dev/null 2>&1 || fail "${PYTHON_BIN} is required."
}

require_mount_rw() {
  mountpoint -q "${RUNTIME_MOUNT}" || fail "External mount not found at ${RUNTIME_MOUNT}."
  if [[ ! -w "${RUNTIME_MOUNT}" ]]; then
    findmnt "${RUNTIME_MOUNT}" || true
    fail "${RUNTIME_MOUNT} is not writable. Remount it read-write, then rerun this script."
  fi
}

create_layout() {
  mkdir -p \
    "${RUNTIME_MOUNT}/apps" \
    "${RUNTIME_MOUNT}/data" \
    "${RUNTIME_MOUNT}/db" \
    "${RUNTIME_MOUNT}/docker" \
    "${RUNTIME_MOUNT}/logs" \
    "${RUNTIME_MOUNT}/scans" \
    "${RUNTIME_MOUNT}/secrets" \
    "${STATE_DIR}" \
    "${SCRIPT_DIR}" \
    "${RUNTIME_REPO}" \
    "${RUNTIME_REPO}/runtime/db/postgres" \
    "${RUNTIME_REPO}/runtime/logs" \
    "${RUNTIME_REPO}/runtime/pids" \
    "${RUNTIME_REPO}/artifacts" \
    "${RUNTIME_REPO}/output" \
    "${RUNTIME_REPO}/outputs"
}

create_excludes() {
  EXCLUDE_FILE="${STATE_DIR}/rsync-excludes.txt"
  cat > "${EXCLUDE_FILE}" <<'EOF'
.git/
.venv/
venv/
node_modules/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.mypy_cache/
.cache/
.env
.env.*
artifacts/
output/
outputs/
logs/
runtime/logs/
runtime/pids/
runtime/db/
EOF
}

sync_repo() {
  log "Syncing source repo to runtime repo"
  rsync -a --delete \
    --exclude-from="${EXCLUDE_FILE}" \
    "${SOURCE_REPO}/" \
    "${RUNTIME_REPO}/"
}

set_env_value() {
  local key="$1"
  local value="$2"
  local env_file="$3"
  if grep -q "^${key}=" "${env_file}" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${env_file}"
  else
    printf "%s=%s\n" "${key}" "${value}" >> "${env_file}"
  fi
}

ensure_runtime_env() {
  if [[ -f "${RUNTIME_REPO}/.env" ]]; then
    log "Keeping existing runtime .env"
  elif [[ -f "${SOURCE_REPO}/.env" ]]; then
    log "Copying source .env to runtime .env"
    cp "${SOURCE_REPO}/.env" "${RUNTIME_REPO}/.env"
  elif [[ -f "${SOURCE_REPO}/env.example" ]]; then
    log "No source .env found, bootstrapping runtime .env from env.example"
    cp "${SOURCE_REPO}/env.example" "${RUNTIME_REPO}/.env"
  else
    fail "No .env or env.example available to initialize runtime environment."
  fi

  # Keep runtime-generated records explicitly rooted in the runtime repo copy.
  set_env_value "K1_ARTIFACTS_ROOT" "artifacts" "${RUNTIME_REPO}/.env"
  set_env_value "K1_FINDINGS_STATUS_LOG" "output/logs/finding_status.jsonl" "${RUNTIME_REPO}/.env"
}

patch_compose_for_external_pg_data() {
  local compose_file="${RUNTIME_REPO}/docker-compose.yml"
  [[ -f "${compose_file}" ]] || fail "Missing ${compose_file}"

  if grep -q './runtime/db/postgres:/var/lib/postgresql/data' "${compose_file}"; then
    log "PostgreSQL persistence already patched to runtime/db/postgres"
    return 0
  fi

  if grep -q 'postgres_data:/var/lib/postgresql/data' "${compose_file}"; then
    log "Patching docker-compose.yml so PostgreSQL data persists on external drive"
    sed -i \
      's|postgres_data:/var/lib/postgresql/data|./runtime/db/postgres:/var/lib/postgresql/data|g' \
      "${compose_file}"
    return 0
  fi

  log "No postgres_data volume mapping found to patch; leaving docker-compose.yml unchanged"
}

rebuild_runtime_venv() {
  log "Building runtime virtual environment in external repo"
  rm -rf "${RUNTIME_REPO}/.venv"
  "${PYTHON_BIN}" -m venv "${RUNTIME_REPO}/.venv"
  # shellcheck disable=SC1091
  source "${RUNTIME_REPO}/.venv/bin/activate"
  python -m pip install --upgrade pip setuptools wheel

  local runtime_req_file
  runtime_req_file="${RUNTIME_REPO}/runtime/.requirements.runtime.txt"
  # requirements.txt currently contains developer/test tooling pins.
  # For runtime deployment we exclude those packages to avoid resolver conflicts
  # and keep the external environment focused on executable platform deps.
  grep -Ev '^(pytest==|pytest-cov==|pytest-asyncio==|black==|ruff==|mypy==|isort==)' \
    "${RUNTIME_REPO}/requirements.txt" > "${runtime_req_file}"

  python -m pip install -r "${runtime_req_file}"

  local normalized_dev
  normalized_dev="$(echo "${INSTALL_DEV_DEPS}" | tr '[:upper:]' '[:lower:]')"
  if [[ "${normalized_dev}" == "1" || "${normalized_dev}" == "true" || "${normalized_dev}" == "yes" ]]; then
    if [[ -f "${RUNTIME_REPO}/requirements-dev.txt" ]]; then
      log "Attempting optional dev dependency installation"
      if ! python -m pip install -r "${RUNTIME_REPO}/requirements-dev.txt"; then
        log "Dev dependency installation failed; runtime setup continues without dev tooling"
      fi
    fi
  else
    log "Skipping dev dependency installation (INSTALL_DEV_DEPS=${INSTALL_DEV_DEPS})"
  fi
}

ensure_bootstrap_marker() {
  if [[ ! -f "${RUNTIME_REPO}/runtime/.bootstrap_ready" ]]; then
    log "Creating runtime bootstrap marker"
    date -u +"%Y-%m-%dT%H:%M:%SZ" > "${RUNTIME_REPO}/runtime/.bootstrap_ready"
  fi
}

install_ui_dependencies() {
  local normalized
  normalized="$(echo "${INSTALL_UI_DEPS}" | tr '[:upper:]' '[:lower:]')"
  if [[ "${normalized}" != "1" && "${normalized}" != "true" && "${normalized}" != "yes" ]]; then
    log "Skipping UI dependency installation (INSTALL_UI_DEPS=${INSTALL_UI_DEPS})"
    return 0
  fi

  if [[ -f "${RUNTIME_REPO}/ui/package.json" ]] && command -v npm >/dev/null 2>&1; then
    log "Installing runtime UI dependencies"
    npm --prefix "${RUNTIME_REPO}/ui" install
  else
    log "Skipping UI dependency installation (ui/package.json or npm not found)"
  fi
}

write_helper_scripts() {
  cat > "${SCRIPT_DIR}/sync-kai-runtime.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
"${SOURCE_REPO}/scripts/setup_kai_dual_env.sh"
EOF

  cat > "${SCRIPT_DIR}/run-kai-runtime.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "${RUNTIME_REPO}"
exec ./k1-start
EOF

  cat > "${SCRIPT_DIR}/stop-kai-runtime.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "${RUNTIME_REPO}"
exec ./k1-stop
EOF

  cat > "${SCRIPT_DIR}/shell-kai-runtime.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "${RUNTIME_REPO}"
exec bash
EOF

  chmod +x "${SCRIPT_DIR}/"*.sh
}

print_summary() {
  cat <<EOF

Kai dual-environment setup complete.

DEV repo:
  ${SOURCE_REPO}

RUNTIME repo (external SSD):
  ${RUNTIME_REPO}

Runtime helpers:
  ${SCRIPT_DIR}/sync-kai-runtime.sh
  ${SCRIPT_DIR}/run-kai-runtime.sh
  ${SCRIPT_DIR}/stop-kai-runtime.sh
  ${SCRIPT_DIR}/shell-kai-runtime.sh

Runtime data/log roots (all on external SSD through runtime repo path):
  ${RUNTIME_REPO}/artifacts
  ${RUNTIME_REPO}/output
  ${RUNTIME_REPO}/outputs
  ${RUNTIME_REPO}/runtime/logs
  ${RUNTIME_REPO}/runtime/db/postgres
EOF
}

main() {
  require_prereqs
  [[ -d "${SOURCE_REPO}" ]] || fail "Source repo not found: ${SOURCE_REPO}"
  require_mount_rw
  create_layout
  create_excludes
  sync_repo
  ensure_runtime_env
  patch_compose_for_external_pg_data
  rebuild_runtime_venv
  ensure_bootstrap_marker
  install_ui_dependencies
  write_helper_scripts
  log "Dual environment setup finished successfully"
  print_summary
}

main "$@"
