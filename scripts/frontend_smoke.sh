#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/apps/frontend"

echo "[frontend-smoke] build"
(cd "$FRONTEND_DIR" && npm run build)

echo "[frontend-smoke] route checks"
grep -q "path='/opportunities'" "$FRONTEND_DIR/src/App.tsx"
grep -q "path='/workflows'" "$FRONTEND_DIR/src/App.tsx"
grep -q "path='/kpi'" "$FRONTEND_DIR/src/App.tsx"

echo "[frontend-smoke] passed"
