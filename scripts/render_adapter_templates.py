#!/usr/bin/env python3
"""Render shared templates into adapter directories."""

import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def copy_if_missing(src: Path, dst: Path):
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix == ".json":
        dst.write_text(json.dumps(json.loads(src.read_text()), indent=2), encoding="utf-8")
    else:
        shutil.copy(src, dst)


def main():
    templates = ROOT / "ai_kernel" / "templates"
    copy_if_missing(templates / "memory" / "GEMINI.template.md", ROOT / "adapters/gemini/.gemini/GEMINI.md")
    copy_if_missing(templates / "memory" / "CLAUDE.template.md", ROOT / "adapters/claude/.claude/CLAUDE.md")
    copy_if_missing(templates / "memory" / "AGENTS.template.md", ROOT / "adapters/codex/AGENTS.md")
    copy_if_missing(templates / "adapter" / "gemini.settings.template.json", ROOT / "adapters/gemini/.gemini/settings.json")
    copy_if_missing(templates / "adapter" / "claude.settings.template.json", ROOT / "adapters/claude/.claude/settings.json")
    print("adapter templates rendered (missing files only)")


if __name__ == "__main__":
    main()
