#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Checking required directories..."
for d in ai-kernel/governance/policies ai-kernel/governance/hooks ai-kernel/governance/schemas config/providers config/registry runtime; do
  [ -d "$ROOT/$d" ] || { echo "missing $d"; exit 1; }
done

echo "Validating YAML/JSON syntax..."
python3 - <<'PY'
import json, yaml, sys, glob, pathlib
root = pathlib.Path(".")
for path in glob.glob("**/*.yaml", recursive=True):
    with open(path, "r", encoding="utf-8") as f:
        yaml.safe_load(f)
for path in glob.glob("ai-kernel/governance/schemas/*.json"):
    with open(path, "r", encoding="utf-8") as f:
        json.load(f)
print("syntax ok")
PY

echo "validate_architecture: ok"
