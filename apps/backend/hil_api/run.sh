#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
export PYTHONPATH="$SCRIPT_DIR/..:$PYTHONPATH"
if [ -f "$SCRIPT_DIR/.env" ]; then export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs); fi
uvicorn k1.apps.backend.hil_api.app:app --host 0.0.0.0 --port 8080 --reload
