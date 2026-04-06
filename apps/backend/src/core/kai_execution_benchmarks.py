"""
Kai execution benchmark and profiling utilities.

This module is intentionally lightweight:
- aggregates mission runtime metrics into substrate comparison summaries
- persists a bounded benchmark artifact history
- derives a selector performance profile for deterministic optimization inputs
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apps.backend.src.core.kai_selector_learning import (
    build_adaptive_performance_profiles,
    build_selector_learning_recommendations,
    derive_determinism_requirement,
    derive_scenario_type,
    make_adaptive_profile_key,
)
from apps.backend.src.core.kai_execution_selector import select_execution_substrate


_DEFAULT_BENCHMARK_PATH = Path("artifacts/benchmarks/latest.json")
_MAX_RECORDS = 250
_DEFAULT_MAX_HISTORY_FILES = 30
_HISTORY_DIR_NAME = "history"


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


def _parse_iso_ts(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def _latest_selector_policy_artifact(selector_artifacts: Any) -> dict[str, Any]:
    """
    Return the latest execution selector artifact, skipping resolution-only rows.
    """
    if not isinstance(selector_artifacts, list):
        return {}
    for row in reversed(selector_artifacts):
        if not isinstance(row, dict):
            continue
        if row.get("type") == "execution_selector_policy":
            return row
    for row in reversed(selector_artifacts):
        if not isinstance(row, dict):
            continue
        if (
            "selected_substrate" in row
            or "fallback_substrate" in row
            or "selector_inputs" in row
            or "adaptive_change" in row
        ):
            return row
    return {}


def _history_dir(path: Path) -> Path:
    return path.parent / _HISTORY_DIR_NAME


def discover_benchmark_history_files(
    *,
    path: Path | str = _DEFAULT_BENCHMARK_PATH,
    max_files: int = _DEFAULT_MAX_HISTORY_FILES,
) -> list[Path]:
    benchmark_path = Path(path)
    history_dir = _history_dir(benchmark_path)
    if not history_dir.exists():
        return []
    files = [row for row in history_dir.glob("*.jsonl") if row.is_file()]
    files.sort(key=lambda row: row.name)
    if max_files > 0:
        files = files[-max_files:]
    return files


def _append_history_record(
    record: dict[str, Any],
    *,
    path: Path | str = _DEFAULT_BENCHMARK_PATH,
    max_history_files: int = _DEFAULT_MAX_HISTORY_FILES,
) -> None:
    benchmark_path = Path(path)
    history_dir = _history_dir(benchmark_path)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    target = history_dir / f"{stamp}.jsonl"
    try:
        history_dir.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
        if max_history_files > 0:
            files = discover_benchmark_history_files(path=path, max_files=0)
            if len(files) > max_history_files:
                for obsolete in files[: len(files) - max_history_files]:
                    try:
                        obsolete.unlink(missing_ok=True)
                    except Exception:
                        continue
    except Exception:
        # Non-fatal by design; history archival cannot block mission execution.
        pass


def query_benchmark_records(
    *,
    path: Path | str = _DEFAULT_BENCHMARK_PATH,
    include_latest: bool = True,
    include_history: bool = True,
    substrate: str = "",
    scenario_type: str = "",
    success: bool | None = None,
    created_after: str = "",
    created_before: str = "",
    limit: int = 200,
) -> list[dict[str, Any]]:
    benchmark_path = Path(path)
    collected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()

    def _record_key(record: dict[str, Any]) -> tuple[str, str, str, str, str]:
        return (
            str(record.get("mission_id") or ""),
            str(record.get("workflow_id") or ""),
            str(record.get("program_id") or ""),
            str(record.get("created_at") or ""),
            str(record.get("selected_substrate") or ""),
        )

    def _add(record: dict[str, Any]) -> None:
        key = _record_key(record)
        if key in seen:
            return
        seen.add(key)
        collected.append(record)

    if include_latest:
        payload = load_benchmark_payload(path=benchmark_path)
        records = payload.get("records", [])
        if isinstance(records, list):
            for row in records:
                if isinstance(row, dict):
                    _add(dict(row))

    if include_history:
        for history_file in discover_benchmark_history_files(path=benchmark_path):
            try:
                lines = history_file.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for line in lines:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if isinstance(row, dict):
                    _add(dict(row))

    normalized_substrate = str(substrate or "").strip().upper()
    normalized_scenario = str(scenario_type or "").strip().lower()
    after_ts = _parse_iso_ts(created_after)
    before_ts = _parse_iso_ts(created_before)

    filtered: list[dict[str, Any]] = []
    for row in collected:
        if normalized_substrate and str(row.get("selected_substrate") or "").strip().upper() != normalized_substrate:
            continue
        if normalized_scenario and str(row.get("scenario_type") or "").strip().lower() != normalized_scenario:
            continue
        if success is not None and bool(row.get("success")) is not bool(success):
            continue
        created = _parse_iso_ts(row.get("created_at"))
        if after_ts is not None and (created is None or created < after_ts):
            continue
        if before_ts is not None and (created is None or created > before_ts):
            continue
        filtered.append(row)

    filtered.sort(
        key=lambda row: _parse_iso_ts(row.get("created_at")) or datetime.fromtimestamp(0, tz=timezone.utc),
        reverse=True,
    )
    bounded_limit = max(1, min(int(limit), 1000))
    return filtered[:bounded_limit]


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
    actual_substrate = ""
    fallback_substrate = ""
    latest_selector_inputs: dict[str, Any] = {}
    latest_adaptive_change: dict[str, Any] = {}
    latest_divergence: dict[str, Any] = {}
    policy_events = state.get("policy_events", [])
    latest_policy_divergence: dict[str, Any] = {}
    if isinstance(policy_events, list):
        for row in reversed(policy_events):
            if not isinstance(row, dict):
                continue
            if row.get("type") == "execution_substrate_divergence":
                latest_policy_divergence = row
                break
    if isinstance(selector_artifacts, list) and selector_artifacts:
        latest = _latest_selector_policy_artifact(selector_artifacts)
        selected_substrate = str(latest.get("selected_substrate") or "")
        actual_substrate = str(latest.get("actual_substrate") or selected_substrate)
        fallback_substrate = str(latest.get("fallback_substrate") or "")
        selector_inputs = latest.get("selector_inputs", {})
        if isinstance(selector_inputs, dict):
            latest_selector_inputs = selector_inputs
        adaptive_change = latest.get("adaptive_change", {})
        if isinstance(adaptive_change, dict):
            latest_adaptive_change = adaptive_change
        divergence = latest.get("substrate_divergence", {})
        if isinstance(divergence, dict):
            latest_divergence = divergence
    if not latest_divergence and latest_policy_divergence:
        latest_divergence = {
            "requested_substrate": str(latest_policy_divergence.get("requested_substrate") or selected_substrate),
            "actual_substrate": str(latest_policy_divergence.get("actual_substrate") or actual_substrate or selected_substrate),
            "reason": str(latest_policy_divergence.get("reason") or ""),
        }

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
    stage_type = str(state.get("phase") or "mission").strip().lower() or "mission"
    workflow_complexity = str(latest_selector_inputs.get("workflow_complexity") or "medium").strip().lower()
    needs_resume = bool(latest_selector_inputs.get("needs_resume", True))
    telemetry_required = str(latest_selector_inputs.get("telemetry_required") or "standard").strip().lower()
    requires_specialist_decomposition = bool(
        latest_selector_inputs.get("requires_specialist_decomposition", False)
    )
    requires_protocol_bridge = bool(latest_selector_inputs.get("requires_protocol_bridge", False))
    scenario_type = derive_scenario_type(
        execution_mode=execution_mode,
        stage_count=stage_count,
        workflow_complexity=workflow_complexity,
        requires_specialist_decomposition=requires_specialist_decomposition,
        requires_protocol_bridge=requires_protocol_bridge,
    )
    determinism_requirement = derive_determinism_requirement(
        needs_resume=needs_resume,
        telemetry_required=telemetry_required,
    )
    adaptive_profile_key = make_adaptive_profile_key(
        scenario_type=scenario_type,
        stage_type=stage_type,
        workflow_complexity=workflow_complexity,
        determinism_requirement=determinism_requirement,
    )

    return {
        "mission_id": mission_id,
        "workflow_id": workflow_id,
        "program_id": program_id,
        "execution_mode": execution_mode,
        "selected_substrate": selected_substrate,
        "actual_substrate": str(metrics.get("actual_substrate") or actual_substrate or selected_substrate),
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
        "scenario_type": scenario_type,
        "stage_type": stage_type,
        "workflow_complexity": workflow_complexity,
        "determinism_requirement": determinism_requirement,
        "adaptive_profile_key": adaptive_profile_key,
        "selector_input_snapshot": {
            "workflow_complexity": workflow_complexity,
            "needs_resume": needs_resume,
            "telemetry_required": telemetry_required,
            "requires_specialist_decomposition": requires_specialist_decomposition,
            "requires_protocol_bridge": requires_protocol_bridge,
            "latency_slo_ms": _safe_int(latest_selector_inputs.get("latency_slo_ms"), 0),
        },
        "adaptive_decision_snapshot": {
            "considered": bool(latest_adaptive_change.get("considered", False)),
            "applied": bool(latest_adaptive_change.get("applied", False)),
            "confidence": _safe_float(latest_adaptive_change.get("confidence"), 0.0),
            "sample_count": _safe_int(latest_adaptive_change.get("sample_count"), 0),
            "failed_guardrails": list(latest_adaptive_change.get("failed_guardrails", []))
            if isinstance(latest_adaptive_change.get("failed_guardrails"), list)
            else [],
            "profile_key": str(latest_adaptive_change.get("profile_key") or ""),
        },
        "substrate_divergence_snapshot": {
            "diverged": bool(latest_divergence),
            "requested_substrate": str(latest_divergence.get("requested_substrate") or selected_substrate),
            "actual_substrate": str(latest_divergence.get("actual_substrate") or actual_substrate or selected_substrate),
            "reason": str(latest_divergence.get("reason") or ""),
        },
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
    max_history_files: int = _DEFAULT_MAX_HISTORY_FILES,
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
    adaptive_profiles = build_adaptive_performance_profiles(existing_records)
    selector_learning_recommendations = build_selector_learning_recommendations(adaptive_profiles)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "records": existing_records,
        "summary": summary,
        "selector_performance_profile": build_selector_performance_profile(summary),
        "adaptive_performance_profiles": adaptive_profiles,
        "selector_learning_recommendations": selector_learning_recommendations,
        "selector_learning_meta": {
            "mode": "bounded_recommendation",
            "profile_count": len(adaptive_profiles),
            "recommendation_count": len(selector_learning_recommendations),
        },
    }

    try:
        benchmark_path.parent.mkdir(parents=True, exist_ok=True)
        benchmark_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        # Non-fatal by design; benchmarking cannot block execution.
        pass
    _append_history_record(dict(record), path=benchmark_path, max_history_files=max_history_files)

    return output


def load_benchmark_payload(path: Path | str = _DEFAULT_BENCHMARK_PATH) -> dict[str, Any]:
    benchmark_path = Path(path)
    if not benchmark_path.exists():
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "records": [],
            "summary": summarize_benchmark_records([]),
            "selector_performance_profile": {},
            "adaptive_performance_profiles": {},
            "selector_learning_recommendations": [],
            "selector_learning_meta": {
                "mode": "bounded_recommendation",
                "profile_count": 0,
                "recommendation_count": 0,
            },
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
        "adaptive_performance_profiles": {},
        "selector_learning_recommendations": [],
        "selector_learning_meta": {
            "mode": "bounded_recommendation",
            "profile_count": 0,
            "recommendation_count": 0,
        },
    }


def _latency_distribution(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50_ms": 0.0, "p90_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}
    sorted_values = sorted(values)
    return {
        "p50_ms": round(_percentile(sorted_values, 0.50), 2),
        "p90_ms": round(_percentile(sorted_values, 0.90), 2),
        "p95_ms": round(_percentile(sorted_values, 0.95), 2),
        "p99_ms": round(_percentile(sorted_values, 0.99), 2),
    }


def build_benchmark_intelligence_report(
    payload: dict[str, Any] | None = None,
    *,
    path: Path | str = _DEFAULT_BENCHMARK_PATH,
    include_recent: int = 20,
) -> dict[str, Any]:
    """
    Operator-grade benchmark visibility report.
    """
    source = payload if isinstance(payload, dict) else load_benchmark_payload(path)
    records = source.get("records", []) if isinstance(source.get("records"), list) else []
    summary = source.get("summary", {}) if isinstance(source.get("summary"), dict) else {}

    latencies = [_safe_float(r.get("total_mission_ms"), 0.0) for r in records if isinstance(r, dict)]
    retry_values = [_safe_float(r.get("retry_frequency"), 0.0) for r in records if isinstance(r, dict)]
    failure_values = [0.0 if bool(r.get("success")) else 1.0 for r in records if isinstance(r, dict)]
    adaptive = [
        r.get("adaptive_decision_snapshot", {})
        for r in records
        if isinstance(r, dict) and isinstance(r.get("adaptive_decision_snapshot"), dict)
    ]
    divergences = [
        r.get("substrate_divergence_snapshot", {})
        for r in records
        if isinstance(r, dict) and isinstance(r.get("substrate_divergence_snapshot"), dict)
    ]
    adaptive_applied = sum(1 for row in adaptive if bool(row.get("applied")))
    adaptive_considered = sum(1 for row in adaptive if bool(row.get("considered")))
    divergence_count = sum(1 for row in divergences if bool(row.get("diverged")))

    recent_records = list(records[-max(0, include_recent):]) if include_recent > 0 else []
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_runs": len(records),
        "latency_distribution": _latency_distribution(latencies),
        "substrate_performance": summary.get("substrates", {}),
        "failure_retry_patterns": {
            "avg_failure_rate": round(sum(failure_values) / max(1, len(failure_values)), 4),
            "avg_retry_frequency": round(sum(retry_values) / max(1, len(retry_values)), 4),
            "max_retry_frequency": round(max(retry_values) if retry_values else 0.0, 4),
        },
        "adaptive_selector_influence": {
            "considered_count": adaptive_considered,
            "applied_count": adaptive_applied,
            "applied_ratio": round(adaptive_applied / max(1, adaptive_considered), 4),
            "divergence_count": divergence_count,
        },
        "adaptive_profiles": source.get("adaptive_performance_profiles", {}),
        "selector_learning_recommendations": source.get("selector_learning_recommendations", []),
        "data_integrity": {
            "records_with_adaptive_snapshot": sum(
                1
                for row in records
                if isinstance(row, dict) and isinstance(row.get("adaptive_decision_snapshot"), dict)
            ),
            "records_with_divergence_snapshot": sum(
                1
                for row in records
                if isinstance(row, dict) and isinstance(row.get("substrate_divergence_snapshot"), dict)
            ),
        },
        "recent_records": recent_records,
    }


async def run_parallel_execution_benchmark_scenario(
    *,
    mission_id: str,
    workflow_id: str,
    program_id: str,
    path: Path | str = _DEFAULT_BENCHMARK_PATH,
) -> dict[str, Any]:
    """
    Execute a real parallel benchmark stage with concurrent tool-like work.

    This runs deterministic CPU-bound hashing tasks concurrently, emits
    tool invocation events, measures aggregation timing, and persists output.
    """
    selector_inputs = {
        "execution_mode": "parallel",
        "workflow_complexity": "high",
        "needs_resume": False,
        "requires_specialist_decomposition": False,
        "latency_slo_ms": 1200,
    }
    decision = select_execution_substrate(selector_inputs)
    selected_substrate = str(decision.get("selected_substrate") or "")
    started = datetime.now(timezone.utc)
    stage_id = "benchmark_parallel_stage"

    async def _invoke(tool_id: str, payload: str) -> dict[str, Any]:
        t0 = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            "python3",
            "-c",
            (
                "import hashlib\n"
                "import sys\n"
                "digest = sys.argv[1].encode('utf-8')\n"
                "rounds = int(sys.argv[2])\n"
                "for _ in range(rounds):\n"
                "    digest = hashlib.sha256(digest).hexdigest().encode('utf-8')\n"
                "print(digest.decode('utf-8'))\n"
            ),
            payload,
            "5000",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            err = (stderr or b"").decode("utf-8", errors="replace").strip() or "hash_worker_failed"
            raise RuntimeError(err)
        output_hash = (stdout or b"").decode("utf-8", errors="replace").strip()
        duration_ms = (time.monotonic() - t0) * 1000.0
        return {"tool_id": tool_id, "duration_ms": round(duration_ms, 2), "hash": output_hash}

    # Run three invocations concurrently.
    results = await asyncio.gather(
        _invoke("parallel_tool_alpha", "alpha-payload"),
        _invoke("parallel_tool_beta", "beta-payload"),
        _invoke("parallel_tool_gamma", "gamma-payload"),
    )
    aggregation_start = datetime.now(timezone.utc)
    aggregated = {
        "hashes": sorted([row["hash"] for row in results]),
        "slowest_tool_ms": max(row["duration_ms"] for row in results),
    }
    aggregation_ms = (datetime.now(timezone.utc) - aggregation_start).total_seconds() * 1000.0
    total_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000.0

    record = {
        "mission_id": mission_id,
        "workflow_id": workflow_id,
        "program_id": program_id,
        "execution_mode": "parallel",
        "selected_substrate": selected_substrate,
        "actual_substrate": selected_substrate,
        "fallback_substrate": str(decision.get("fallback_substrate") or ""),
        "terminal_status": "completed",
        "success": True,
        "error": "",
        "total_mission_ms": round(total_ms, 2),
        "stage_count": 1,
        "avg_stage_ms": round(total_ms, 2),
        "p95_stage_ms": round(total_ms, 2),
        "tool_invocations": len(results),
        "avg_tool_ms": round(sum(row["duration_ms"] for row in results) / len(results), 2),
        "tool_failure_rate": 0.0,
        "retry_frequency": 0.0,
        "model_calls": 0,
        "total_tokens": 0,
        "estimated_cost_cents": 0.0,
        "scenario_type": "parallel",
        "stage_type": stage_id,
        "workflow_complexity": "high",
        "determinism_requirement": "standard",
        "adaptive_profile_key": make_adaptive_profile_key(
            scenario_type="parallel",
            stage_type=stage_id,
            workflow_complexity="high",
            determinism_requirement="standard",
        ),
        "selector_input_snapshot": selector_inputs,
        "aggregation_timing_ms": round(aggregation_ms, 2),
        "aggregation_summary": aggregated,
        "adaptive_decision_snapshot": {
            "considered": False,
            "applied": False,
            "confidence": 0.0,
            "sample_count": 0,
            "failed_guardrails": [],
            "profile_key": "",
        },
        "substrate_divergence_snapshot": {
            "diverged": False,
            "requested_substrate": selected_substrate,
            "actual_substrate": selected_substrate,
            "reason": "",
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    output = persist_benchmark_run(record, path=path)
    return {
        "record": record,
        "benchmark_summary": output.get("summary", {}),
    }
