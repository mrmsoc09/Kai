from __future__ import annotations

from pathlib import Path
import json
import subprocess


def test_benchmark_runner_deterministic_output(tmp_path):
    out1 = tmp_path / "run1.json"
    out2 = tmp_path / "run2.json"

    cmd1 = ["python3", "scripts/run_benchmarks.py", "--verify-claims", "--output", str(out1)]
    cmd2 = ["python3", "scripts/run_benchmarks.py", "--verify-claims", "--output", str(out2)]

    r1 = subprocess.run(cmd1, capture_output=True, text=True, check=False)
    r2 = subprocess.run(cmd2, capture_output=True, text=True, check=False)

    assert r1.returncode == 0, r1.stdout + r1.stderr
    assert r2.returncode == 0, r2.stdout + r2.stderr

    j1 = json.loads(out1.read_text(encoding="utf-8"))
    j2 = json.loads(out2.read_text(encoding="utf-8"))

    assert j1 == j2
    assert j1["failed_claims"] == 0
