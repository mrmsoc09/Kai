from __future__ import annotations

from pathlib import Path

import yaml

from scripts import k1_health_check


def test_run_health_check_uses_registry_and_reports(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "tools" / "registry").mkdir(parents=True)
    (tmp_path / "apps" / "backend" / "src" / "config").mkdir(parents=True)
    (tmp_path / "apps" / "backend" / "src" / "config" / "network_env.sh").write_text(
        "#!/usr/bin/env bash\n",
        encoding="utf-8",
    )
    (tmp_path / "wordlists" / "content").mkdir(parents=True)

    registry = {
        "tools": [
            {
                "name": "python3-check",
                "binary_path": "python3",
                "install_verification_cmd": ["python3", "--version"],
            }
        ]
    }
    (tmp_path / "tools" / "registry" / "tool_registry.yaml").write_text(
        yaml.safe_dump(registry),
        encoding="utf-8",
    )

    monkeypatch.setattr(k1_health_check, "_repo_root", lambda: tmp_path)
    report = k1_health_check.run_health_check(verify_commands=False)

    assert report["tool_count"] == 1
    assert report["checks_passed"] >= 1
    assert any(c["name"] == "path:network_env" and c["ok"] for c in report["checks"])

