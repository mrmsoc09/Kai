"""
Kai Billing / Usage Tracker
============================
Tracks platform resource consumption for future billing integration.

Records are written to artifacts/usage/usage.jsonl (append-only JSONL).
Each record carries tenant_id and user_id for per-tenant aggregation.

Usage event types:
  usage.llm_tokens      — LLM inference (input + output token counts)
  usage.tool_execution  — tool execution (tool name, duration)
  usage.mission_run     — mission started (workflow, mode)
  usage.simulation_run  — simulation run (mode, fixture_profile)

Usage records are NOT billing invoices — they are the raw usage log that
a billing engine would aggregate over a billing period.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
_USAGE_LOCK = threading.Lock()


def _usage_log_path() -> Path:
    raw = os.getenv("K1_USAGE_LOG_PATH", "artifacts/usage/usage.jsonl")
    return Path(raw).resolve()


def _ensure_dir(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error("usage_tracker: cannot create dir %s: %s", path.parent, exc)


def _write_usage_record(event_type: str, tenant_id: str, user_id: str, detail: dict[str, Any]) -> str:
    """Append a single usage record. Returns record_id. Never raises."""
    record_id = str(uuid.uuid4())
    record = {
        "record_id": record_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "tenant_id": tenant_id or "",
        "user_id": user_id or "",
        **detail,
    }
    path = _usage_log_path()
    _ensure_dir(path)
    try:
        line = json.dumps(record, separators=(",", ":"), default=str)
        with _USAGE_LOCK:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception as exc:
        logger.error("usage_tracker: write failed: %s", exc)
        return ""
    return record_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def track_llm_tokens(
    *,
    tenant_id: str,
    user_id: str,
    mission_id: str = "",
    provider: str = "",
    model: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
) -> str:
    """Record LLM token consumption."""
    return _write_usage_record(
        "usage.llm_tokens",
        tenant_id=tenant_id,
        user_id=user_id,
        detail={
            "mission_id": mission_id,
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": round(cost_usd, 6),
        },
    )


def track_tool_execution(
    *,
    tenant_id: str,
    user_id: str,
    mission_id: str = "",
    tool_name: str,
    tool_band: str = "",
    duration_ms: float = 0.0,
    status: str = "success",
) -> str:
    """Record tool execution (counts + duration)."""
    return _write_usage_record(
        "usage.tool_execution",
        tenant_id=tenant_id,
        user_id=user_id,
        detail={
            "mission_id": mission_id,
            "tool_name": tool_name,
            "tool_band": tool_band,
            "duration_ms": round(duration_ms, 2),
            "status": status,
        },
    )


def track_mission_run(
    *,
    tenant_id: str,
    user_id: str,
    mission_id: str,
    workflow_id: str = "",
    program_id: str = "",
    execution_mode: str = "live",
    action: str = "started",  # started | completed | failed
    duration_ms: float = 0.0,
) -> str:
    """Record mission lifecycle events."""
    return _write_usage_record(
        "usage.mission_run",
        tenant_id=tenant_id,
        user_id=user_id,
        detail={
            "mission_id": mission_id,
            "workflow_id": workflow_id,
            "program_id": program_id,
            "execution_mode": execution_mode,
            "action": action,
            "duration_ms": round(duration_ms, 2),
        },
    )


def track_simulation_run(
    *,
    tenant_id: str,
    user_id: str,
    mission_id: str = "",
    simulation_mode: str,
    fixture_profile: str = "default",
    scenario_pack: str = "",
    action: str = "started",
) -> str:
    """Record simulation run events."""
    return _write_usage_record(
        "usage.simulation_run",
        tenant_id=tenant_id,
        user_id=user_id,
        detail={
            "mission_id": mission_id,
            "simulation_mode": simulation_mode,
            "fixture_profile": fixture_profile,
            "scenario_pack": scenario_pack,
            "action": action,
        },
    )


def track_api_request(
    *,
    tenant_id: str,
    user_id: str,
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: float = 0.0,
) -> str:
    """Record API request (for quota/rate audit)."""
    return _write_usage_record(
        "usage.api_request",
        tenant_id=tenant_id,
        user_id=user_id,
        detail={
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )


# ---------------------------------------------------------------------------
# Aggregation helpers (for billing engine)
# ---------------------------------------------------------------------------


def read_usage_records(
    tenant_id: str | None = None,
    event_type: str | None = None,
    since_iso: str | None = None,
) -> list[dict[str, Any]]:
    """
    Read usage records from the log, optionally filtered by tenant, event type,
    and start timestamp. Returns a list of record dicts.

    For production use, this should be replaced by a database query.
    This file-based fallback is for dev/test environments.
    """
    path = _usage_log_path()
    if not path.exists():
        return []
    records = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if tenant_id and record.get("tenant_id") != tenant_id:
                    continue
                if event_type and record.get("event_type") != event_type:
                    continue
                if since_iso and record.get("timestamp", "") < since_iso:
                    continue
                records.append(record)
    except OSError as exc:
        logger.error("usage_tracker: read failed: %s", exc)
    return records


def summarize_usage(tenant_id: str, since_iso: str | None = None) -> dict[str, Any]:
    """Return a usage summary for a tenant. Suitable for billing API responses."""
    records = read_usage_records(tenant_id=tenant_id, since_iso=since_iso)
    summary: dict[str, Any] = {
        "tenant_id": tenant_id,
        "since": since_iso or "all_time",
        "total_records": len(records),
        "llm_total_input_tokens": 0,
        "llm_total_output_tokens": 0,
        "llm_total_cost_usd": 0.0,
        "tool_executions": 0,
        "mission_runs": 0,
        "simulation_runs": 0,
    }
    for r in records:
        et = r.get("event_type", "")
        if et == "usage.llm_tokens":
            summary["llm_total_input_tokens"] += r.get("input_tokens", 0)
            summary["llm_total_output_tokens"] += r.get("output_tokens", 0)
            summary["llm_total_cost_usd"] += r.get("cost_usd", 0.0)
        elif et == "usage.tool_execution":
            summary["tool_executions"] += 1
        elif et == "usage.mission_run" and r.get("action") == "started":
            summary["mission_runs"] += 1
        elif et == "usage.simulation_run" and r.get("action") == "started":
            summary["simulation_runs"] += 1
    summary["llm_total_cost_usd"] = round(summary["llm_total_cost_usd"], 6)
    return summary
