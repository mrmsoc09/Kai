#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

log() {
  printf '[phoneinfoga-deprecate] %s\n' "$*"
}

exists() {
  command -v "$1" >/dev/null 2>&1
}

remove_phoneinfoga_binaries() {
  local candidates=(
    "$(command -v phoneinfoga 2>/dev/null || true)"
    "/usr/local/bin/phoneinfoga"
    "/usr/bin/phoneinfoga"
    "$HOME/go/bin/phoneinfoga"
    "$HOME/.local/bin/phoneinfoga"
  )

  for bin in "${candidates[@]}"; do
    if [[ -n "$bin" && -e "$bin" ]]; then
      log "Removing binary: $bin"
      rm -f "$bin" || true
    fi
  done
}

remove_phoneinfoga_packages() {
  if exists pip; then
    log "Uninstalling PhoneInfoga python package via pip (if present)"
    pip uninstall -y phoneinfoga >/dev/null 2>&1 || true
  fi

  if exists pip3; then
    log "Uninstalling PhoneInfoga python package via pip3 (if present)"
    pip3 uninstall -y phoneinfoga >/dev/null 2>&1 || true
  fi

  if exists go; then
    log "Removing PhoneInfoga Go install cache and binary (if present)"
    rm -rf "$HOME/go/pkg/mod"/*phoneinfoga* >/dev/null 2>&1 || true
    rm -f "$HOME/go/bin/phoneinfoga" >/dev/null 2>&1 || true
  fi

  if exists apt-get; then
    log "Attempting apt removal for phoneinfoga package (if present)"
    sudo apt-get remove -y phoneinfoga >/dev/null 2>&1 || true
    sudo apt-get autoremove -y >/dev/null 2>&1 || true
  fi

  if exists brew; then
    log "Attempting Homebrew removal for phoneinfoga formula (if present)"
    brew uninstall phoneinfoga >/dev/null 2>&1 || true
  fi
}

remove_phoneinfoga_containers() {
  if ! exists docker; then
    return
  fi

  log "Removing phoneinfoga Docker containers/images (if present)"

  mapfile -t containers < <(docker ps -a --format '{{.ID}} {{.Image}} {{.Names}}' | awk 'tolower($0) ~ /phoneinfoga/ {print $1}')
  for cid in "${containers[@]:-}"; do
    if [[ -n "$cid" ]]; then
      docker rm -f "$cid" >/dev/null 2>&1 || true
    fi
  done

  mapfile -t images < <(docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | awk 'tolower($1) ~ /phoneinfoga/ {print $2}')
  for iid in "${images[@]:-}"; do
    if [[ -n "$iid" ]]; then
      docker rmi -f "$iid" >/dev/null 2>&1 || true
    fi
  done
}

scrub_repository_references() {
  log "Scrubbing phoneinfoga references from registry and Praison topology/config"

  ROOT_DIR_ENV="$ROOT_DIR" python - <<'PY'
from __future__ import annotations

import os
import re
from pathlib import Path

root = Path(os.environ["ROOT_DIR_ENV"])
targets = [
    root / "apps/backend/src/agents/tools/__init__.py",
    root / "orchestration/praison/agents.yaml",
    root / "apps/backend/src/config/agents.yaml",
]

pattern = re.compile(r"phoneinfoga", re.IGNORECASE)

for path in targets:
    if not path.exists():
        continue

    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()
    kept: list[str] = []

    for line in lines:
        if pattern.search(line):
            continue
        kept.append(line)

    updated = "\n".join(kept).rstrip() + "\n"
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        print(f"updated:{path}")
PY
}

main() {
  log "Starting PhoneInfoga deprecation workflow"
  remove_phoneinfoga_packages
  remove_phoneinfoga_binaries
  remove_phoneinfoga_containers
  scrub_repository_references
  log "PhoneInfoga deprecation workflow completed"
}

main "$@"
