#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

python3 - <<'PY'
from ai_kernel.governance.hooks import session_init, scope_guard, tool_filter, result_normalizer, quality_gate  # noqa
print("hooks import ok")
PY

echo "smoke tests passed"
