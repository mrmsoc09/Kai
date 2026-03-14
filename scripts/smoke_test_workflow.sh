#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-example.com}"
TEMPLATE="${2:-workflow_recon_surface_map}"

echo "Running dry-run smoke workflow (${TEMPLATE}) for ${TARGET}"
python3 scripts/run_workflow_local.py \
  --template "${TEMPLATE}" \
  --target "${TARGET}" \
  --dry-run \
  --safe-mode

echo "Running executable local workflow (${TEMPLATE}) for ${TARGET}"
python3 scripts/run_workflow_local.py \
  --template "${TEMPLATE}" \
  --target "${TARGET}" \
  --safe-mode

echo "Smoke workflow completed."
