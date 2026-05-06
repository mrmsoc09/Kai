#!/usr/bin/env python3
"""Export shared skills into adapter views."""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "ai_kernel" / "skills"


def export(target: Path):
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILLS, target, dirs_exist_ok=True)


def main():
    export(ROOT / "adapters/gemini/.gemini/skills")
    export(ROOT / "adapters/claude/.claude/skills")
    export(ROOT / "adapters/codex/skills")
    print("skill views exported")


if __name__ == "__main__":
    main()
