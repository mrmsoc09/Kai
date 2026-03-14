#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/apps/frontend-operator"

echo "[frontend-smoke] build"
(cd "$FRONTEND_DIR" && npm run build)

echo "[frontend-smoke] route checks"
test -f "$FRONTEND_DIR/app/opportunities/page.tsx"
test -f "$FRONTEND_DIR/app/triage/page.tsx"
test -f "$FRONTEND_DIR/app/cases/page.tsx"

echo "[frontend-smoke] passed"
