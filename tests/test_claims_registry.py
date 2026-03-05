from __future__ import annotations

from pathlib import Path
import subprocess


def test_claims_registry_validates():
    result = subprocess.run(
        ["python3", "scripts/validate_claims.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_claims_file_exists():
    assert Path("claims/claims.yaml").exists()
