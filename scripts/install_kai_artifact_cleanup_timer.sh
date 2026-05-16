#!/usr/bin/env bash
set -euo pipefail

SYSTEMD_DIR="/etc/systemd/system"
DEFAULTS_FILE="/etc/default/kai-artifact-cleanup"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../deploy/systemd" && pwd)"

if [[ "${EUID}" -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi

${SUDO} install -m 0644 "${SRC_DIR}/kai-artifact-cleanup.service" "${SYSTEMD_DIR}/kai-artifact-cleanup.service"
${SUDO} install -m 0644 "${SRC_DIR}/kai-artifact-cleanup.timer" "${SYSTEMD_DIR}/kai-artifact-cleanup.timer"

if [[ ! -f "${DEFAULTS_FILE}" ]]; then
  ${SUDO} install -m 0644 "${SRC_DIR}/kai-artifact-cleanup.env" "${DEFAULTS_FILE}"
fi

${SUDO} systemctl daemon-reload
${SUDO} systemctl enable --now kai-artifact-cleanup.timer
${SUDO} systemctl status kai-artifact-cleanup.timer --no-pager
