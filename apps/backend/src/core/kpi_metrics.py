from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .payout_ledger import list_payout_records


def _state_dir() -> Path:
    return Path(os.getenv("K1_SUBMISSION_STATE_DIR", "artifacts/submissions/states")).resolve()


def _reflective_path() -> Path:
    return Path(os.getenv("K1_REFLECTIVE_STATE_PATH", "artifacts/learning/reflective_state.json")).resolve()


def _load_submission_states() -> List[Dict[str, Any]]:
    root = _state_dir()
    if not root.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for file_path in root.glob("*.json"):
        try:
            rows.append(json.loads(file_path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return rows


def _load_reflective_outcomes() -> List[Dict[str, Any]]:
    path = _reflective_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return list(payload.get("outcomes") or [])


def build_kpi_snapshot() -> Dict[str, Any]:
    submissions = _load_submission_states()
    outcomes = _load_reflective_outcomes()
    payouts = list_payout_records()

    submitted = 0
    accepted = 0
    rejected = 0
    for row in submissions:
        state = str(row.get("state") or "")
        history = row.get("history") or []
        if state == "accepted":
            accepted += 1
        if state == "rejected":
            rejected += 1
        if any((h.get("to_state") in {"dispatched", "acknowledged", "in_triage", "accepted", "rejected"}) for h in history):
            submitted += 1

    duplicate_events = sum(1 for out in outcomes if str(out.get("outcome")) == "duplicate")
    acceptance_rate = accepted / max(submitted, 1)
    duplicate_rate = duplicate_events / max(submitted, 1)
    throughput_per_week = submitted / 4.345 if submitted else 0.0

    gross = sum(float(item.get("actual_amount") or 0.0) for item in payouts)
    fees = sum(float(item.get("fees") or 0.0) for item in payouts)
    net = sum(float(item.get("net_amount") or 0.0) for item in payouts)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reports_submitted": submitted,
        "reports_accepted": accepted,
        "reports_rejected": rejected,
        "acceptance_rate": round(acceptance_rate, 6),
        "duplicate_events": duplicate_events,
        "duplicate_rate": round(duplicate_rate, 6),
        "throughput_reports_per_week": round(throughput_per_week, 6),
        "payouts": {
            "gross_amount": round(gross, 2),
            "fees": round(fees, 2),
            "net_amount": round(net, 2),
        },
    }


def kpi_snapshot_csv(snapshot: Dict[str, Any]) -> str:
    flat_rows = [
        ("generated_at", snapshot.get("generated_at")),
        ("reports_submitted", snapshot.get("reports_submitted")),
        ("reports_accepted", snapshot.get("reports_accepted")),
        ("reports_rejected", snapshot.get("reports_rejected")),
        ("acceptance_rate", snapshot.get("acceptance_rate")),
        ("duplicate_events", snapshot.get("duplicate_events")),
        ("duplicate_rate", snapshot.get("duplicate_rate")),
        ("throughput_reports_per_week", snapshot.get("throughput_reports_per_week")),
        ("gross_payout_amount", (snapshot.get("payouts") or {}).get("gross_amount")),
        ("payout_fees", (snapshot.get("payouts") or {}).get("fees")),
        ("net_payout_amount", (snapshot.get("payouts") or {}).get("net_amount")),
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["metric", "value"])
    for key, value in flat_rows:
        writer.writerow([key, value])
    return buffer.getvalue()
