#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.backend.src.core.tool_registry_catalog import list_catalog_entries  # noqa: E402
from apps.backend.src.core.helpers import workflow_output_root  # noqa: E402


def _run_verify(command: list[str]) -> tuple[bool, str]:
    if not command:
        return False, "no verification command configured"
    if command[0] == "python" and shutil.which("python") is None and shutil.which("python3"):
        command = ["python3", *command[1:]]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
        )
        success = completed.returncode == 0
        output = (completed.stdout or completed.stderr or "").strip()
        return success, output[:400]
    except FileNotFoundError:
        return False, f"binary not found: {command[0]}"
    except Exception as exc:  # pragma: no cover - defensive
        return False, str(exc)


def main() -> int:
    report: list[dict] = []
    failures = 0
    for entry in list_catalog_entries(enabled_only=False):
        if entry.execution_mode == "docker":
            docker_ok = shutil.which("docker") is not None
            success = docker_ok
            output = (
                f"docker available; runtime image {entry.container_image or 'not configured'}"
                if docker_ok
                else "docker not available"
            )
        else:
            success, output = _run_verify(entry.install_verification_cmd)
        record = {
            "tool": entry.name,
            "execution_mode": entry.execution_mode,
            "enabled_by_default": entry.enabled_by_default,
            "ok": success,
            "verify_cmd": entry.install_verification_cmd,
            "output": output,
        }
        if not success and entry.enabled_by_default:
            failures += 1
        report.append(record)
        mark = "OK" if success else "MISSING"
        print(f"[{mark:<7}] {entry.name}")

    out_path = workflow_output_root() / "reports" / "tool_install_verification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote verification report: {out_path}")
    if failures:
        print(f"Enabled-tool verification failures: {failures}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
