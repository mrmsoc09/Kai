"""
Bounded selector learning utilities for Kai.

Design constraints:
- deterministic and reviewable computations only
- recommendation-first (no hidden hard rule changes)
- confidence, sample-size, and staleness guardrails
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


_DEFAULT_MIN_SAMPLES = 3
_DEFAULT_STALE_AFTER_DAYS = 14
_DEFAULT_MIN_CONFIDENCE = 0.65


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _parse_ts(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        # datetime.fromisoformat handles offsets; normalize Z suffix.
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def derive_scenario_type(
    *,
    execution_mode: str,
    stage_count: int,
    workflow_complexity: str,
    requires_specialist_decomposition: bool,
    requires_protocol_bridge: bool,
) -> str:
    mode = str(execution_mode or "").strip().lower()
    complexity = str(workflow_complexity or "").strip().lower()
    if requires_specialist_decomposition:
        return "specialist"
    if requires_protocol_bridge:
        return "interop"
    if mode == "parallel":
        return "parallel"
    if complexity == "low" and stage_count <= 2:
        return "simple"
    if stage_count >= 3 or complexity == "high":
        return "multi_stage"
    return "general"


def derive_determinism_requirement(needs_resume: bool, telemetry_required: str = "standard") -> str:
    if bool(needs_resume):
        return "high"
    if str(telemetry_required or "").strip().lower() == "strict":
        return "elevated"
    return "standard"


def make_adaptive_profile_key(
    *,
    scenario_type: str,
    stage_type: str,
    workflow_complexity: str,
    determinism_requirement: str,
) -> str:
    return "|".join(
        [
            str(scenario_type or "general").strip().lower() or "general",
            str(stage_type or "mission").strip().lower() or "mission",
            str(workflow_complexity or "medium").strip().lower() or "medium",
            str(determinism_requirement or "standard").strip().lower() or "standard",
        ]
    )


def _score_substrate(metrics: Mapping[str, Any]) -> float:
    """
    Lower is better.

    Score prioritizes reliability over latency.
    """
    failure_rate = _safe_float(metrics.get("failure_rate"), 0.0)
    retry_frequency = _safe_float(metrics.get("retry_frequency"), 0.0)
    p95_latency_ms = _safe_float(metrics.get("p95_latency_ms"), 0.0)
    return (failure_rate * 100.0) + (retry_frequency * 40.0) + (p95_latency_ms / 1000.0)


def _aggregate_substrate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = sorted(_safe_float(r.get("total_mission_ms"), 0.0) for r in rows)
    retries = [_safe_float(r.get("retry_frequency"), 0.0) for r in rows]
    failures = [r for r in rows if not bool(r.get("success"))]
    avg_latency = sum(latencies) / max(1, len(latencies))
    p95_idx = min(len(latencies) - 1, int(round((len(latencies) - 1) * 0.95))) if latencies else 0
    p95_latency = latencies[p95_idx] if latencies else 0.0
    return {
        "runs": len(rows),
        "failure_rate": round(len(failures) / max(1, len(rows)), 4),
        "retry_frequency": round(sum(retries) / max(1, len(retries)), 4),
        "avg_latency_ms": round(avg_latency, 2),
        "p95_latency_ms": round(p95_latency, 2),
    }


def build_adaptive_performance_profiles(
    records: list[dict[str, Any]],
    *,
    min_samples: int = _DEFAULT_MIN_SAMPLES,
    stale_after_days: int = _DEFAULT_STALE_AFTER_DAYS,
    min_confidence: float = _DEFAULT_MIN_CONFIDENCE,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Build rolling adaptive profiles keyed by scenario/stage/complexity/determinism.

    Profiles are recommendation-oriented and include data quality metadata.
    """
    now_utc = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    grouped: dict[str, list[dict[str, Any]]] = {}

    for record in records:
        if not isinstance(record, dict):
            continue
        key = str(record.get("adaptive_profile_key") or "").strip().lower()
        if not key:
            key = make_adaptive_profile_key(
                scenario_type=str(record.get("scenario_type") or "general"),
                stage_type=str(record.get("stage_type") or "mission"),
                workflow_complexity=str(record.get("workflow_complexity") or "medium"),
                determinism_requirement=str(record.get("determinism_requirement") or "standard"),
            )
        grouped.setdefault(key, []).append(record)

    profiles: dict[str, dict[str, Any]] = {}
    for key, rows in grouped.items():
        by_substrate: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            substrate = str(row.get("selected_substrate") or "UNKNOWN").strip().upper() or "UNKNOWN"
            by_substrate.setdefault(substrate, []).append(row)

        substrate_metrics: dict[str, dict[str, Any]] = {
            substrate: _aggregate_substrate(items)
            for substrate, items in by_substrate.items()
        }

        total_runs = len(rows)
        latest_seen = max(
            (ts for ts in (_parse_ts(r.get("created_at")) for r in rows) if ts is not None),
            default=None,
        )
        stale = False
        age_days = 10_000
        if latest_seen is not None:
            age_days = max(0, int((now_utc - latest_seen).total_seconds() // 86400))
            stale = (now_utc - latest_seen) > timedelta(days=max(1, stale_after_days))

        sample_score = min(1.0, total_runs / max(float(min_samples * 2), 1.0))
        freshness_score = 0.0 if stale else max(0.0, 1.0 - (age_days / max(float(stale_after_days), 1.0)))
        confidence = round((0.7 * sample_score) + (0.3 * freshness_score), 4)

        recommended_substrate = ""
        rationale = "insufficient_data"
        if substrate_metrics:
            best = min(substrate_metrics.items(), key=lambda item: _score_substrate(item[1]))
            recommended_substrate = best[0]
            rationale = (
                f"best_score_substrate={best[0]} "
                f"failure_rate={best[1].get('failure_rate', 0.0)} "
                f"retry_frequency={best[1].get('retry_frequency', 0.0)} "
                f"p95_latency_ms={best[1].get('p95_latency_ms', 0.0)}"
            )

        usable = bool(
            total_runs >= max(1, min_samples)
            and not stale
            and confidence >= float(min_confidence)
            and recommended_substrate
        )

        scenario_type, stage_type, workflow_complexity, determinism_requirement = (
            key.split("|", 3) + ["general", "mission", "medium", "standard"]
        )[:4]

        profiles[key] = {
            "profile_key": key,
            "scenario_type": scenario_type,
            "stage_type": stage_type,
            "workflow_complexity": workflow_complexity,
            "determinism_requirement": determinism_requirement,
            "sample_count": total_runs,
            "confidence": confidence,
            "stale": stale,
            "age_days": age_days,
            "usable": usable,
            "recommended_substrate": recommended_substrate if usable else "",
            "recommendation_rationale": rationale,
            "substrate_metrics": substrate_metrics,
            "quality": {
                "min_samples_required": int(min_samples),
                "min_confidence_required": float(min_confidence),
                "stale_after_days": int(stale_after_days),
                "sample_score": round(sample_score, 4),
                "freshness_score": round(freshness_score, 4),
            },
        }

    return profiles


def build_selector_learning_recommendations(
    adaptive_profiles: Mapping[str, Any],
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    for key, raw_profile in adaptive_profiles.items():
        if not isinstance(raw_profile, Mapping):
            continue
        recommendations.append({
            "profile_key": str(key),
            "usable": bool(raw_profile.get("usable", False)),
            "confidence": _safe_float(raw_profile.get("confidence"), 0.0),
            "sample_count": _safe_int(raw_profile.get("sample_count"), 0),
            "recommended_substrate": str(raw_profile.get("recommended_substrate") or ""),
            "stale": bool(raw_profile.get("stale", False)),
            "rationale": str(raw_profile.get("recommendation_rationale") or ""),
            "mode": "recommendation",
        })
    recommendations.sort(key=lambda row: (row["usable"], row["confidence"], row["sample_count"]), reverse=True)
    return recommendations


def select_adaptive_profile_for_inputs(
    adaptive_profiles: Mapping[str, Any] | None,
    selector_inputs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(adaptive_profiles, Mapping) or not isinstance(selector_inputs, Mapping):
        return {}

    scenario_type = derive_scenario_type(
        execution_mode=str(selector_inputs.get("execution_mode") or ""),
        stage_count=_safe_int(selector_inputs.get("stage_count"), 0),
        workflow_complexity=str(selector_inputs.get("workflow_complexity") or "medium"),
        requires_specialist_decomposition=bool(selector_inputs.get("requires_specialist_decomposition", False)),
        requires_protocol_bridge=bool(selector_inputs.get("requires_protocol_bridge", False)),
    )
    stage_type = str(selector_inputs.get("stage_id") or selector_inputs.get("phase") or "mission").strip().lower()
    complexity = str(selector_inputs.get("workflow_complexity") or "medium").strip().lower()
    determinism = derive_determinism_requirement(
        bool(selector_inputs.get("needs_resume", True)),
        telemetry_required=str(selector_inputs.get("telemetry_required") or "standard"),
    )
    profile_key = make_adaptive_profile_key(
        scenario_type=scenario_type,
        stage_type=stage_type,
        workflow_complexity=complexity,
        determinism_requirement=determinism,
    )
    profile = adaptive_profiles.get(profile_key)
    if isinstance(profile, Mapping):
        out = dict(profile)
        out.setdefault("profile_key", profile_key)
        return out

    # Fallback to same context with generalized stage.
    fallback_key = make_adaptive_profile_key(
        scenario_type=scenario_type,
        stage_type="mission",
        workflow_complexity=complexity,
        determinism_requirement=determinism,
    )
    profile = adaptive_profiles.get(fallback_key)
    if isinstance(profile, Mapping):
        out = dict(profile)
        out.setdefault("profile_key", fallback_key)
        out["fallback_match"] = True
        return out

    return {}
