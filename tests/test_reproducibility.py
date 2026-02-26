from datetime import datetime, timedelta, timezone

from apps.backend.src.core.reproducibility_scorer import (
    calculate_reproducibility,
    generate_feedback,
    time_weight_factor,
)


def test_time_weight_factor_thresholds():
    now = datetime.now(timezone.utc)
    assert time_weight_factor(now - timedelta(days=1), now=now) == 1.1
    assert time_weight_factor(now - timedelta(days=10), now=now) == 1.0
    assert time_weight_factor(now - timedelta(days=40), now=now) == 0.8


def test_calculate_reproducibility_empty():
    assert calculate_reproducibility([]) == 0.0


def test_calculate_reproducibility_diversity_and_count():
    now = datetime.now(timezone.utc)
    evidence = [
        {"kind": "screenshot", "uri": "a", "created_at": now},
        {"kind": "http_trace", "uri": "b", "created_at": now - timedelta(days=5)},
        {"kind": "poc", "uri": "c", "created_at": now - timedelta(days=35)},
    ]
    score = calculate_reproducibility(evidence, now=now)
    assert 0.5 < score <= 1.0


def test_generate_feedback_tiers():
    assert generate_feedback(0.95).startswith("Highly reproducible")
    assert generate_feedback(0.8).startswith("Generally reproducible")
    assert generate_feedback(0.6).startswith("Partially reproducible")
    assert generate_feedback(0.3).startswith("Not reproducible")

