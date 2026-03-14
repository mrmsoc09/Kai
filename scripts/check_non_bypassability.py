#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTERS_DIR = ROOT / "apps" / "backend" / "src" / "routers"

ALLOWED_TOOL_EXECUTE_FILES = {
    Path("apps/backend/src/worker/celery_app.py"),
    Path("apps/backend/src/routers/tools.py"),
    Path("apps/backend/src/core/tool_adapters/base_adapter.py"),
}
REQUIRED_GATE_FILES = {
    Path("apps/backend/src/worker/celery_app.py"),
    Path("apps/backend/src/core/tool_runner.py"),
    Path("apps/backend/src/routers/tools.py"),
}

TOOL_EXEC_RE = re.compile(r"\btool\.execute\(")
SUBPROCESS_RE = re.compile(r"\b(subprocess\.(run|Popen)|os\.system)\(")


def _read(rel_path: Path) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def main() -> int:
    violations: list[str] = []

    # Every critical execution path must include mandatory gate enforcement.
    for rel in REQUIRED_GATE_FILES:
        text = _read(rel)
        if "enforce_authorization_gates(" not in text and "enforce_authorization_gates_async(" not in text:
            violations.append(f"{rel}:missing enforce_authorization_gates()")
        if "scope_validator" not in _read(Path("apps/backend/src/core/authorization_gate.py")):
            violations.append("apps/backend/src/core/authorization_gate.py:missing scope_validator()")
        if "authorization_certificate_check" not in _read(Path("apps/backend/src/core/authorization_gate.py")):
            violations.append("apps/backend/src/core/authorization_gate.py:missing authorization_certificate_check()")

    # Direct tool.execute must be constrained to approved execution modules.
    for py_file in ROOT.glob("apps/backend/src/**/*.py"):
        rel = py_file.relative_to(ROOT)
        text = py_file.read_text(encoding="utf-8")
        if TOOL_EXEC_RE.search(text) and rel not in ALLOWED_TOOL_EXECUTE_FILES:
            violations.append(f"{rel}:direct tool.execute call outside allowed execution modules")

    # Router layer must not spawn shell commands directly.
    for py_file in ROUTERS_DIR.glob("*.py"):
        rel = py_file.relative_to(ROOT)
        text = py_file.read_text(encoding="utf-8")
        if SUBPROCESS_RE.search(text):
            violations.append(f"{rel}:direct subprocess/os.system usage in router layer")

    if violations:
        print("non-bypassability check failed:")
        for item in sorted(set(violations)):
            print(item)
        return 1

    print("non-bypassability check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
