from __future__ import annotations

import json
from pathlib import Path

from apps.backend.src.core.auth import ROLE_VIEWER, create_access_token
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


def test_governance_benchmark_intelligence_endpoint_returns_summary(client, monkeypatch):
    monkeypatch.setattr(
        "apps.backend.src.routers.governance.build_benchmark_intelligence_report",
        lambda include_recent=20: {
            "total_runs": 3,
            "latency_distribution": {"p95_ms": 120.0},
            "adaptive_selector_influence": {"applied_count": 1},
            "include_recent": include_recent,
        },
    )
    response = client.get("/governance/benchmark-intelligence?include_recent=250")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_runs"] == 3
    # endpoint clamps include_recent to keep retrieval bounded
    assert payload["include_recent"] == 100


def test_governance_benchmark_intelligence_probe_attaches_parallel_result(client, monkeypatch):
    async def _fake_parallel_probe(**_kwargs):
        return {"record": {"execution_mode": "parallel", "tool_invocations": 3}}

    monkeypatch.setattr(
        "apps.backend.src.routers.governance.run_parallel_execution_benchmark_scenario",
        _fake_parallel_probe,
    )
    monkeypatch.setattr(
        "apps.backend.src.routers.governance.build_benchmark_intelligence_report",
        lambda include_recent=20: {"total_runs": 0, "include_recent": include_recent},
    )
    response = client.get("/governance/benchmark-intelligence?run_parallel_probe=true")
    assert response.status_code == 200
    payload = response.json()
    assert "parallel_probe" in payload
    assert payload["parallel_probe"]["record"]["execution_mode"] == "parallel"
    assert payload["query_policy"]["probe_allowed"] is True


def test_governance_benchmark_probe_requires_operator_or_admin(client) -> None:
    viewer_token = create_access_token(subject="viewer-only", roles=[ROLE_VIEWER])
    response = client.get(
        "/governance/benchmark-intelligence?run_parallel_probe=true",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "benchmark_probe_forbidden_requires_operator_or_admin"
