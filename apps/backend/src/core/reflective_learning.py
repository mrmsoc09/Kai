from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path() -> Path:
    path = Path(os.getenv("K1_REFLECTIVE_STATE_PATH", "artifacts/learning/reflective_state.json")).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            json.dumps({"tactic_weights": {}, "outcomes": [], "change_log": []}, indent=2),
            encoding="utf-8",
        )
    return path


def _load() -> Dict[str, Any]:
    return json.loads(_state_path().read_text(encoding="utf-8"))


def _save(payload: Dict[str, Any]) -> None:
    _state_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")


@dataclass
class OutcomeRecord:
    run_id: str
    tactic_id: str
    outcome: str
    evidence_quality: float
    cost_cents: float
    latency_ms: float
    operator_feedback: str


def _bounded(value: float, low: float = 0.1, high: float = 2.0) -> float:
    return max(low, min(high, value))


def _adjustment_for_outcome(outcome: str) -> float:
    if outcome == "accepted":
        return 0.08
    if outcome == "rejected":
        return -0.06
    if outcome == "duplicate":
        return -0.09
    return 0.0


def record_outcome(record: OutcomeRecord) -> Dict[str, Any]:
    """
    Persist outcome and apply bounded tactic-weight updates with explicit change reasoning.
    """
    payload = _load()
    weights = dict(payload.get("tactic_weights") or {})
    old = float(weights.get(record.tactic_id, 1.0))

    quality_term = (float(record.evidence_quality) - 0.5) * 0.04
    efficiency_term = 0.0
    if record.cost_cents > 0:
        efficiency_term -= min(0.03, float(record.cost_cents) / 100000.0)
    if record.latency_ms > 0:
        efficiency_term -= min(0.03, float(record.latency_ms) / 1_000_000.0)
    delta = _adjustment_for_outcome(record.outcome) + quality_term + efficiency_term
    new = _bounded(old + delta)
    weights[record.tactic_id] = round(new, 4)

    outcome_row = {
        "timestamp": _now(),
        "run_id": record.run_id,
        "tactic_id": record.tactic_id,
        "outcome": record.outcome,
        "evidence_quality": float(record.evidence_quality),
        "cost_cents": float(record.cost_cents),
        "latency_ms": float(record.latency_ms),
        "operator_feedback": record.operator_feedback,
    }
    payload.setdefault("outcomes", []).append(outcome_row)
    payload["tactic_weights"] = weights

    change = {
        "timestamp": _now(),
        "run_id": record.run_id,
        "tactic_id": record.tactic_id,
        "old_weight": round(old, 4),
        "new_weight": round(new, 4),
        "delta": round(new - old, 4),
        "why_plan_changed": (
            f"outcome={record.outcome}, quality={record.evidence_quality:.2f}, "
            f"cost_cents={record.cost_cents:.0f}, latency_ms={record.latency_ms:.0f}"
        ),
    }
    payload.setdefault("change_log", []).append(change)
    _save(payload)
    return {"weights": weights, "change": change}


def summarize_reflection(limit: int = 20) -> Dict[str, Any]:
    payload = _load()
    outcomes = list(payload.get("outcomes") or [])[-limit:]
    changes = list(payload.get("change_log") or [])[-limit:]
    return {
        "tactic_weights": payload.get("tactic_weights") or {},
        "recent_outcomes": outcomes,
        "recent_changes": changes,
    }
