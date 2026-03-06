from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ledger_path() -> Path:
    path = Path(os.getenv("K1_PAYOUT_LEDGER_PATH", "artifacts/payouts/ledger.json")).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"records": []}, indent=2), encoding="utf-8")
    return path


def _load() -> Dict[str, Any]:
    return json.loads(_ledger_path().read_text(encoding="utf-8"))


def _save(payload: Dict[str, Any]) -> None:
    _ledger_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")


def upsert_payout_record(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = _load()
    records: List[Dict[str, Any]] = list(payload.get("records") or [])

    run_id = str(record.get("run_id") or "")
    finding_id = str(record.get("finding_id") or "")
    if not run_id or not finding_id:
        raise ValueError("run_id and finding_id are required")

    expected = float(record.get("expected_amount") or 0.0)
    actual = float(record.get("actual_amount") or 0.0)
    fees = float(record.get("fees") or 0.0)
    net = actual - fees

    normalized = {
        "run_id": run_id,
        "finding_id": finding_id,
        "program_id": record.get("program_id"),
        "program_name": record.get("program_name"),
        "status": record.get("status") or "pending",
        "currency": record.get("currency") or "USD",
        "expected_amount": expected,
        "actual_amount": actual,
        "fees": fees,
        "net_amount": net,
        "notes": record.get("notes") or "",
        "updated_at": _now(),
    }

    idx = next(
        (i for i, item in enumerate(records) if item.get("run_id") == run_id and item.get("finding_id") == finding_id),
        None,
    )
    if idx is None:
        normalized["created_at"] = _now()
        records.append(normalized)
    else:
        normalized["created_at"] = records[idx].get("created_at") or _now()
        records[idx] = normalized

    payload["records"] = records
    _save(payload)
    return normalized


def list_payout_records() -> List[Dict[str, Any]]:
    return list(_load().get("records") or [])


def summarize_month(year: int, month: int) -> Dict[str, Any]:
    records = list_payout_records()
    scoped = []
    for rec in records:
        raw = rec.get("updated_at") or rec.get("created_at")
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except Exception:
            continue
        if dt.year == year and dt.month == month:
            scoped.append(rec)

    gross = sum(float(r.get("actual_amount") or 0.0) for r in scoped)
    fees = sum(float(r.get("fees") or 0.0) for r in scoped)
    net = sum(float(r.get("net_amount") or 0.0) for r in scoped)
    expected = sum(float(r.get("expected_amount") or 0.0) for r in scoped)

    return {
        "year": year,
        "month": month,
        "records": scoped,
        "count": len(scoped),
        "totals": {
            "expected_amount": expected,
            "actual_amount": gross,
            "fees": fees,
            "net_amount": net,
        },
    }
