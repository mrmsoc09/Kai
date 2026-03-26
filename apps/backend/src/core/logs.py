from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .helpers import artifacts_root


def _logs_root() -> Path:
    return artifacts_root() / "logs"


def _utc_ymd() -> tuple[str, str, str]:
    """Return (year, month, day) strings for the current UTC date."""
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}", f"{now.month:02d}", f"{now.day:02d}"


def run_dir(run_id: str, create: bool = True) -> Path:
    y, m, d = _utc_ymd()
    dpath = _logs_root() / y / m / d / "runs" / run_id
    if create:
        dpath.mkdir(parents=True, exist_ok=True)
    return dpath


def log_decision(run_id: str, event: str, data: dict[str, Any]) -> Path:
    d = run_dir(run_id, True)
    fp = d / "decision_trace.jsonl"
    rec = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
        "data": data,
    }
    with fp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return fp


def write_summary(run_id: str, text: str) -> Path:
    d = run_dir(run_id, True)
    fp = d / "summary.md"
    fp.write_text(text, encoding="utf-8")
    return fp


def read_decision_trace(run_id: str) -> list[dict[str, Any]]:
    fp = run_dir(run_id, False) / "decision_trace.jsonl"
    out: list[dict[str, Any]] = []
    if not fp.exists():
        return out
    with fp.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def read_summary(run_id: str) -> str:
    fp = run_dir(run_id, False) / "summary.md"
    return fp.read_text(encoding="utf-8") if fp.exists() else ""


def _iter_decision_logs() -> Iterable[dict[str, Any]]:
    logs_root = _logs_root()
    if not logs_root.exists():
        return
    for fp in logs_root.rglob("decision_trace.jsonl"):
        try:
            # .../logs/YYYY/MM/DD/runs/<run_id>/decision_trace.jsonl
            run_id = fp.parts[-2] if len(fp.parts) >= 2 else ""
            with fp.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        rec["run_id"] = run_id
                        yield rec
                    except Exception:
                        continue
        except Exception:
            continue


def list_recent_logs(limit: int = 200) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    for rec in _iter_decision_logs():
        event = rec.get("event", "event")
        data = rec.get("data", {})
        message = event
        if isinstance(data, dict) and data:
            hint = data.get("summary") or data.get("target") or data.get("tool")
            if hint:
                message = f"{event}: {hint}"
        logs.append(
            {
                "ts": rec.get("ts"),
                "level": "INFO",
                "source": "decision_trace",
                "message": message,
                "event": event,
                "data": data,
                "run_id": rec.get("run_id", ""),
            }
        )
    logs.sort(key=lambda r: r.get("ts") or "", reverse=True)
    return logs[: max(1, min(limit, 500))]
