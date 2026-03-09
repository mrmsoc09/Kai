#!/usr/bin/env bash
set -euo pipefail

if ! command -v nuclei >/dev/null 2>&1; then
  echo '{"status":"error","reason":"nuclei not installed"}'
  exit 1
fi

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  echo '{"status":"error","reason":"target required"}'
  exit 1
fi

TEMPLATE_DIR="${NUCLEI_TEMPLATES:-/root/nuclei-templates}"
OUT_DIR="${ARTIFACT_DIR:-artifacts/${RUN_ID:-local}/nuclei}"
mkdir -p "$OUT_DIR"

echo "$TARGET" | nuclei -t "$TEMPLATE_DIR" -json -o "$OUT_DIR/result.json" || {
  echo '{"status":"error","reason":"nuclei failed"}'
  exit 1
}

SHA=$(sha256sum "$OUT_DIR/result.json" | awk '{print $1}')
echo "{\"status\":\"ok\",\"artifact\":\"$OUT_DIR/result.json\",\"sha256\":\"$SHA\"}"
