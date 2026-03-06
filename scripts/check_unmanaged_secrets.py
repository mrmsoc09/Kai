#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_FILES = list(ROOT.glob("apps/backend/src/**/*.py"))

# These modules are the approved boundary for direct env secret reads.
ALLOW_FILES = {
    Path("apps/backend/src/core/secret_manager.py"),
    Path("apps/backend/src/core/hil_vault_client.py"),
}

SECRET_ENV_RE = re.compile(
    r"""(?P<call>os\.getenv|os\.environ\.get)\(\s*["'](?P<name>[A-Z0-9_]+)["']""",
)
SENSITIVE_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD", "_PASS")

# Non-secret env names that happen to include sensitive words.
SAFE_NAME_EXCEPTIONS = {
    "K1_REQUIRED_SECRETS",
}


def _is_sensitive(name: str) -> bool:
    if name in SAFE_NAME_EXCEPTIONS:
        return False
    return name.endswith(SENSITIVE_SUFFIXES)


def main() -> int:
    violations: list[str] = []
    for file_path in PYTHON_FILES:
        rel = file_path.relative_to(ROOT)
        if rel in ALLOW_FILES:
            continue

        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue

        for line_no, line in enumerate(lines, start=1):
            for match in SECRET_ENV_RE.finditer(line):
                name = match.group("name")
                if _is_sensitive(name):
                    violations.append(f"{rel}:{line_no} direct_env_secret_read:{name}")

    if violations:
        print("unmanaged secret reads detected:")
        for row in violations:
            print(row)
        return 1

    print("no unmanaged secret reads detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
