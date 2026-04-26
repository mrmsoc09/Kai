#!/usr/bin/env bash
set -euo pipefail

if ! command -v amass >/dev/null 2>&1; then
  echo '{"status":"error","reason":"amass not installed"}'
  exit 1
fi

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  echo '{"status":"error","reason":"target required"}'
  exit 1
fi

OUT_DIR="${ARTIFACT_DIR:-artifacts/${RUN_ID:-local}/amass}"
mkdir -p "$OUT_DIR"

amass enum -d "$TARGET" -o "$OUT_DIR/result.txt" >/dev/null 2>&1 || {
  echo '{"status":"error","reason":"amass failed"}'
  exit 1
}

SHA=$(sha256sum "$OUT_DIR/result.txt" | awk '{print $1}')
echo "{\"status\":\"ok\",\"artifact\":\"$OUT_DIR/result.txt\",\"sha256\":\"$SHA\"}"
