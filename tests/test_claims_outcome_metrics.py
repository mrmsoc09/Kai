from __future__ import annotations

from scripts.run_benchmarks import compute_metrics


def test_compute_metrics_includes_outcome_indicators():
    payload = {
        "reports_submitted": 20,
        "reports_accepted": 5,
        "gross_payout_usd": 2000,
        "operating_cost_usd": 500,
    }
    metrics = compute_metrics(payload)
    assert metrics["accepted_rate"] == 0.25
    assert metrics["payout_efficiency"] == 3.0
