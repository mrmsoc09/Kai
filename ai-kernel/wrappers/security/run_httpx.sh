#!/usr/bin/env bash
set -euo pipefail

if ! command -v httpx >/dev/null 2>&1; then
  echo '{"status":"error","reason":"httpx not installed"}'
  exit 1
fi

INPUT="${1:-}"
if [ -z "$INPUT" ]; then
  echo '{"status":"error","reason":"input domain/URL required"}'
  exit 1
fi

OUT_DIR="${ARTIFACT_DIR:-artifacts/${RUN_ID:-local}/httpx}"
mkdir -p "$OUT_DIR"

echo "$INPUT" | httpx -silent -status-code -title -json -o "$OUT_DIR/result.json" || {
  echo '{"status":"error","reason":"httpx failed"}'
  exit 1
}

SHA=$(sha256sum "$OUT_DIR/result.json" | awk '{print $1}')
echo "{\"status\":\"ok\",\"artifact\":\"$OUT_DIR/result.json\",\"sha256\":\"$SHA\"}"
