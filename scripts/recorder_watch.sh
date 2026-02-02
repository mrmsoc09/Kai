#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
LOG="$ROOT/artifacts/logs/recorder_watch.out"
mkdir -p "$(dirname "$LOG")"
python3 "$ROOT/apps/recorder/daemon.py" >>"$LOG" 2>&1
