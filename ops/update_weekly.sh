#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[weekly-update] validating claims registry"
python3 scripts/validate_claims.py

echo "[weekly-update] running deterministic benchmark + claims gate"
python3 scripts/run_benchmarks.py --verify-claims

echo "[weekly-update] checking toolpack adapter compatibility"
python3 scripts/check_toolpack_adapter_compat.py

echo "[weekly-update] checking unmanaged secret reads"
python3 scripts/check_unmanaged_secrets.py

echo "[weekly-update] checking non-bypassability gates"
python3 scripts/check_non_bypassability.py

echo "[weekly-update] completed"
