"""
Kai execution benchmark and profiling utilities.

This module is intentionally lightweight:
- aggregates mission runtime metrics into substrate comparison summaries
- persists a bounded benchmark artifact history
- derives a selector performance profile for deterministic optimization inputs
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_DEFAULT_BENCHMARK_PATH = Path("artifacts/benchmarks/latest.json")
_MAX_RECORDS = 250


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


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    idx = (len(sorted_values) - 1) * percentile
    lower = int(math.floor(idx))
    upper = int(math.ceil(idx))
    if lower == upper:
        return float(sorted_values[lower])
    weight = idx - lower
    return float(sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight)


def mission_benchmark_record_from_state(
    *,
    mission_id: str,
    workflow_id: str,
    program_id: str,
    execution_mode: str,
    terminal_status: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Build a compact benchmark record from a mission state snapshot."""
    metrics = state.get("runtime_metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}

    selector_artifacts = state.get("selector_policy_artifacts", [])
    selected_substrate = ""
    fallback_substrate = ""
    if isinstance(selector_artifacts, list) and selector_artifacts:
        latest = selector_artifacts[-1] if isinstance(selector_artifacts[-1], dict) else {}
        selected_substrate = str(latest.get("selected_substrate") or "")
        fallback_substrate = str(latest.get("fallback_substrate") or "")

    stage_timings = metrics.get("stage_timings", [])
    if not isinstance(stage_timings, list):
        stage_timings = []

    tool_timings = metrics.get("tool_timings", [])
    if not isinstance(tool_timings, list):
        tool_timings = []

    stage_durations = [
        _safe_float(row.get("duration_ms"), 0.0)
        for row in stage_timings
        if isinstance(row, dict)
    ]
    tool_durations = [
        _safe_float(row.get("duration_ms"), 0.0)
        for row in tool_timings
        if isinstance(row, dict)
    ]

    total_mission_ms = _safe_float(metrics.get("total_mission_ms"), 0.0)
    if total_mission_ms <= 0.0 and stage_durations:
        total_mission_ms = float(sum(stage_durations))

    stage_count = _safe_int(metrics.get("stage_count"), len(stage_timings))
    tool_invocations = _safe_int(metrics.get("tool_invocations"), len(tool_timings))

    success = terminal_status == "completed" and not state.get("error")
    retry_count = _safe_int(metrics.get("tool_retry_count"), 0)

    return {
        "mission_id": mission_id,
        "workflow_id": workflow_id,
        "program_id": program_id,
        "execution_mode": execution_mode,
        "selected_substrate": selected_substrate,
        "fallback_substrate": fallback_substrate,
        "terminal_status": terminal_status,
        "success": bool(success),
        "error": str(state.get("error") or ""),
        "total_mission_ms": round(total_mission_ms, 2),
        "stage_count": stage_count,
        "avg_stage_ms": round(sum(stage_durations) / max(1, len(stage_durations)), 2),
        "p95_stage_ms": round(_percentile(sorted(stage_durations), 0.95), 2),
        "tool_invocations": tool_invocations,
        "avg_tool_ms": round(sum(tool_durations) / max(1, len(tool_durations)), 2),
        "tool_failure_rate": round(_safe_float(metrics.get("tool_failure_rate"), 0.0), 4),
        "retry_frequency": round(retry_count / max(1, tool_invocations), 4),
        "model_calls": _safe_int(metrics.get("model_calls"), 0),
        "total_tokens": _safe_int(metrics.get("total_tokens"), 0),
        "estimated_cost_cents": round(_safe_float(metrics.get("estimated_cost_cents"), 0.0), 4),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def summarize_benchmark_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate benchmark records into per-substrate and scenario summaries."""
    by_substrate: dict[str, list[dict[str, Any]]] = {}
    scenario_bins: dict[str, list[dict[str, Any]]] = {
        "simple": [],
        "multi_stage": [],
        "parallel": [],
    }

    for record in records:
        substrate = str(record.get("selected_substrate") or "UNKNOWN")
        by_substrate.setdefault(substrate, []).append(record)

        stage_count = _safe_int(record.get("stage_count"), 0)
        if stage_count <= 2:
            scenario_bins["simple"].append(record)
        else:
            scenario_bins["multi_stage"].append(record)

        # Parallel marker: explicit mode or many tool calls in short mission.
        if (
            str(record.get("execution_mode") or "").lower() == "parallel"
            or (_safe_int(record.get("tool_invocations"), 0) >= 2 and _safe_float(record.get("total_mission_ms"), 0.0) > 0)
        ):
            scenario_bins["parallel"].append(record)

    substrate_summary: dict[str, dict[str, Any]] = {}
    for substrate, rows in by_substrate.items():
        latencies = sorted(_safe_float(r.get("total_mission_ms"), 0.0) for r in rows)
        failures = [r for r in rows if not bool(r.get("success"))]
        retries = [_safe_float(r.get("retry_frequency"), 0.0) for r in rows]
        substrate_summary[substrate] = {
            "runs": len(rows),
            "success_rate": round((len(rows) - len(failures)) / max(1, len(rows)), 4),
            "failure_rate": round(len(failures) / max(1, len(rows)), 4),
            "avg_total_mission_ms": round(sum(latencies) / max(1, len(latencies)), 2),
            "p95_total_mission_ms": round(_percentile(latencies, 0.95), 2),
            "avg_retry_frequency": round(sum(retries) / max(1, len(retries)), 4),
            "avg_tool_failure_rate": round(
                sum(_safe_float(r.get("tool_failure_rate"), 0.0) for r in rows) / max(1, len(rows)),
                4,
            ),
            "total_tokens": sum(_safe_int(r.get("total_tokens"), 0) for r in rows),
            "estimated_cost_cents": round(sum(_safe_float(r.get("estimated_cost_cents"), 0.0) for r in rows), 4),
        }

    scenario_summary: dict[str, dict[str, Any]] = {}
    for name, rows in scenario_bins.items():
        latencies = [_safe_float(r.get("total_mission_ms"), 0.0) for r in rows]
        scenario_summary[name] = {
            "runs": len(rows),
            "avg_total_mission_ms": round(sum(latencies) / max(1, len(latencies)), 2),
            "success_rate": round(
                sum(1 for r in rows if bool(r.get("success"))) / max(1, len(rows)),
                4,
            ),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_runs": len(records),
        "substrates": substrate_summary,
        "scenarios": scenario_summary,
    }


def build_selector_performance_profile(summary: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Build deterministic selector performance profile from benchmark summary."""
    substrates = summary.get("substrates", {})
    if not isinstance(substrates, dict):
        return {}

    profile: dict[str, dict[str, float]] = {}
    for substrate, metrics in substrates.items():
        if not isinstance(metrics, dict):
            continue
        profile[str(substrate)] = {
            "failure_rate": round(_safe_float(metrics.get("failure_rate"), 0.0), 4),
            "p95_latency_ms": round(_safe_float(metrics.get("p95_total_mission_ms"), 0.0), 2),
            "retry_frequency": round(_safe_float(metrics.get("avg_retry_frequency"), 0.0), 4),
        }
    return profile


def persist_benchmark_run(
    record: dict[str, Any],
    *,
    path: Path | str = _DEFAULT_BENCHMARK_PATH,
    max_records: int = _MAX_RECORDS,
) -> dict[str, Any]:
    """
    Append benchmark record to artifact file and return refreshed payload.

    Any parse/write error falls back to returning an in-memory payload.
    """
    benchmark_path = Path(path)
    existing_records: list[dict[str, Any]] = []

    if benchmark_path.exists():
        try:
            payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
            existing = payload.get("records", []) if isinstance(payload, dict) else []
            if isinstance(existing, list):
                existing_records = [row for row in existing if isinstance(row, dict)]
        except Exception:
            existing_records = []

    existing_records.append(dict(record))
    if max_records > 0 and len(existing_records) > max_records:
        existing_records = existing_records[-max_records:]

    summary = summarize_benchmark_records(existing_records)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "records": existing_records,
        "summary": summary,
        "selector_performance_profile": build_selector_performance_profile(summary),
    }

    try:
        benchmark_path.parent.mkdir(parents=True, exist_ok=True)
        benchmark_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        # Non-fatal by design; benchmarking cannot block execution.
        pass

    return output


def load_benchmark_payload(path: Path | str = _DEFAULT_BENCHMARK_PATH) -> dict[str, Any]:
    benchmark_path = Path(path)
    if not benchmark_path.exists():
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "records": [],
            "summary": summarize_benchmark_records([]),
            "selector_performance_profile": {},
        }

    try:
        payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "records": [],
        "summary": summarize_benchmark_records([]),
        "selector_performance_profile": {},
    }
