#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

import yaml


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_registry(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tools = payload.get("tools")
    return tools if isinstance(tools, list) else []


def _check_binaries(tools: list[dict[str, Any]], verify_commands: bool) -> list[CheckResult]:
    results: list[CheckResult] = []
    seen: set[str] = set()
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        binary = str(tool.get("binary_path") or "").strip()
        if not binary or binary in seen:
            continue
        seen.add(binary)

        found = shutil.which(binary)
        if found:
            detail = found
            ok = True
        else:
            detail = "binary_not_found_in_PATH"
            ok = False
        results.append(CheckResult(name=f"binary:{binary}", ok=ok, detail=detail))

        if verify_commands:
            cmd = tool.get("install_verification_cmd")
            if isinstance(cmd, list) and cmd and all(isinstance(x, str) and x for x in cmd):
                try:
                    proc = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,
                    )
                    cmd_ok = proc.returncode == 0
                    out = (proc.stdout or proc.stderr or "").strip().splitlines()
                    preview = out[0][:160] if out else f"exit_code={proc.returncode}"
                    results.append(
                        CheckResult(
                            name=f"verify:{cmd[0]}",
                            ok=cmd_ok,
                            detail=preview,
                        )
                    )
                except Exception as exc:
                    results.append(
                        CheckResult(
                            name=f"verify:{cmd[0]}",
                            ok=False,
                            detail=f"verification_error:{exc}",
                        )
                    )
    return results


def _check_paths(repo_root: Path) -> list[CheckResult]:
    nvme_root = Path(os.getenv("K1_NVME_ROOT", "/mnt/nvme")).expanduser()
    kiterunner_dir = os.getenv("K1_KITERUNNER_WORDLIST_DIR", "").strip()
    wordlist_candidates = [
        repo_root / "wordlists" / "content",
        nvme_root / "k1-wordlists",
        Path(kiterunner_dir).expanduser() if kiterunner_dir else None,
    ]
    results: list[CheckResult] = []

    network_env = repo_root / "apps" / "backend" / "src" / "config" / "network_env.sh"
    results.append(
        CheckResult(
            name="path:network_env",
            ok=network_env.exists(),
            detail=str(network_env),
        )
    )

    for candidate in wordlist_candidates:
        if candidate is None:
            continue
        exists = candidate.exists()
        results.append(
            CheckResult(
                name=f"path:{candidate}",
                ok=exists,
                detail="exists" if exists else "missing",
            )
        )
    return results


def run_health_check(*, verify_commands: bool) -> dict[str, Any]:
    root = _repo_root()
    registry_path = root / "tools" / "registry" / "tool_registry.yaml"
    tools = _load_registry(registry_path)

    binary_checks = _check_binaries(tools, verify_commands=verify_commands)
    path_checks = _check_paths(root)
    all_checks = binary_checks + path_checks

    passed = sum(1 for item in all_checks if item.ok)
    failed = len(all_checks) - passed
    status = "healthy" if failed == 0 else "degraded"

    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry_path": str(registry_path),
        "tool_count": len(tools),
        "checks_passed": passed,
        "checks_failed": failed,
        "checks": [item.as_dict() for item in all_checks],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="K1 local binary/path health check")
    parser.add_argument(
        "--verify-commands",
        action="store_true",
        help="Run install_verification_cmd checks (slower)",
    )
    parser.add_argument(
        "--output",
        default="output/health/k1_health_check.json",
        help="Report output path",
    )
    args = parser.parse_args()

    report = run_health_check(verify_commands=args.verify_commands)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps({"status": report["status"], "output": str(output_path)}, indent=2))
    return 0 if report["checks_failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

