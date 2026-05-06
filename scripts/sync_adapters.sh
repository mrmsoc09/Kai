#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

sync_dir() {
  src="$1"
  dst="$2"
  mkdir -p "$dst"
  rsync -a --delete "$src/" "$dst/"
}

sync_dir "$ROOT/ai_kernel/governance/hooks" "$ROOT/adapters/gemini/.gemini/hooks"
sync_dir "$ROOT/ai_kernel/skills" "$ROOT/adapters/gemini/.gemini/skills"
sync_dir "$ROOT/ai_kernel/governance/hooks" "$ROOT/adapters/claude/.claude/hooks"
sync_dir "$ROOT/ai_kernel/skills" "$ROOT/adapters/claude/.claude/skills"
sync_dir "$ROOT/ai_kernel/skills" "$ROOT/adapters/codex/skills"

echo "adapter sync complete"
