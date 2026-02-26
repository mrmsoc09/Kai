from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping, Sequence


def time_weight_factor(ts: datetime | None, now: datetime | None = None) -> float:
    """
    Apply a simple recency weight:
      - < 7 days: 1.1x
      - 7–30 days: 1.0x
      - > 30 days: 0.8x
    """
    if ts is None:
        return 1.0
    if now is None:
        now = datetime.now(timezone.utc)
    age = now - ts
    if age <= timedelta(days=7):
        return 1.1
    if age <= timedelta(days=30):
        return 1.0
    return 0.8


def _normalize(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def calculate_reproducibility(
    evidence: Sequence[Mapping],
    now: datetime | None = None,
) -> float:
    """
    Evidence-driven reproducibility score in [0, 1].
    Inputs are lightweight mappings (e.g., ORM rows) that contain:
      - kind (str)
      - uri (str)
      - created_at (datetime, optional)
    Scoring:
      - Base score increases with evidence count (log-like)
      - Diversity bonus for distinct kinds
      - Recency weight applied per item
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if not evidence:
        return 0.0

    kinds = set()
    total = 0.0
    for ev in evidence:
        kinds.add(ev.get("kind") or "")
        created_at = _normalize(ev.get("created_at"))
        total += time_weight_factor(created_at, now=now)

    count = len(evidence)
    diversity_bonus = min(len(kinds) * 0.05, 0.15)  # cap bonus
    base = min(0.15 + (0.2 * (count ** 0.5)), 0.7)  # saturate base
    weighted = (total / count) * base
    score = min(1.0, max(0.0, weighted + diversity_bonus))
    return round(score, 4)


def generate_feedback(score: float) -> str:
    if score >= 0.9:
        return "Highly reproducible - Ready for approval"
    if score >= 0.75:
        return "Generally reproducible - Minor clarification needed"
    if score >= 0.5:
        return "Partially reproducible - Additional evidence recommended"
    return "Not reproducible - Provide detailed steps"

