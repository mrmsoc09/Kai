from __future__ import annotations

import json
from pathlib import Path

from apps.backend.src.core.governance_readiness import build_governance_readiness_report


def test_governance_readiness_happy_path(tmp_path: Path):
    claims = tmp_path / "claims.yaml"
    claims.write_text(
        "claims:\n"
        "  - id: c1\n"
        "    metric: coverage\n"
        "    threshold: 0.5\n"
        "    benchmark_scenario: demo\n"
        "    validation_condition: test\n",
        encoding="utf-8",
    )
    benchmark = tmp_path / "latest.json"
    benchmark.write_text(json.dumps({"total_claims": 1, "failed_claims": 0}), encoding="utf-8")

    report = build_governance_readiness_report(
        claims_path=str(claims),
        benchmark_path=str(benchmark),
    )
    assert report["components"]["claims_registry"]["ok"] is True
    assert report["components"]["benchmark_summary"]["ok"] is True


def test_governance_readiness_missing_claims_not_ready(tmp_path: Path):
    benchmark = tmp_path / "latest.json"
    benchmark.write_text(json.dumps({"total_claims": 1, "failed_claims": 0}), encoding="utf-8")

    report = build_governance_readiness_report(
        claims_path=str(tmp_path / "missing.yaml"),
        benchmark_path=str(benchmark),
    )
    assert report["ok"] is False
