from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schemas import BountyWalletRegistry


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


def upsert_bounty_record(data: Dict[str, Any]) -> BountyWalletRegistry:
    """
    Upsert a bounty record into the Dual-Ledger.
    Tracks expected vs validated income.
    """
    payload = _load()
    records = payload.get("records", [])
    
    # Validate via Pydantic
    entry = BountyWalletRegistry.model_validate(data)
    
    idx = next(
        (i for i, item in enumerate(records) if item.get("finding_id") == entry.finding_id),
        None
    )
    
    record_dict = entry.model_dump(mode="json")
    if idx is None:
        records.append(record_dict)
    else:
        records[idx] = record_dict
        
    payload["records"] = records
    _save(payload)
    return entry


def verify_bounty(finding_id: str, amount: float, actor: str = "HiL_Admin") -> Optional[BountyWalletRegistry]:
    """
    Verification Gate: Move funds from Expected to Validated.
    Human-in-the-Loop (HiL) approval required.
    """
    payload = _load()
    records = payload.get("records", [])
    
    idx = next((i for i, item in enumerate(records) if item.get("finding_id") == finding_id), None)
    if idx is None:
        return None
        
    record = records[idx]
    record["validated_amount"] = float(amount)
    record["status"] = "validated"
    record["verified_by"] = actor
    record["verified_at"] = datetime.now(UTC).isoformat()
    record["updated_at"] = datetime.now(UTC).isoformat()
    
    # Re-validate
    entry = BountyWalletRegistry.model_validate(record)
    records[idx] = entry.model_dump(mode="json")
    
    payload["records"] = records
    _save(payload)
    return entry


def list_payout_records() -> List[Dict[str, Any]]:
    return list(_load().get("records") or [])


def summarize_month(year: int, month: int) -> Dict[str, Any]:
    records = list_payout_records()
    scoped = []
    for rec in records:
        raw = rec.get("updated_at") or rec.get("observed_at")
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except Exception:
            continue
        if dt.year == year and dt.month == month:
            scoped.append(rec)

    expected = sum(float(r.get("expected_amount") or 0.0) for r in scoped)
    validated = sum(float(r.get("validated_amount") or 0.0) for r in scoped)

    return {
        "year": year,
        "month": month,
        "records": scoped,
        "count": len(scoped),
        "totals": {
            "expected_total": expected,
            "validated_total": validated,
            "pending_validation": max(0.0, expected - validated),
        },
    }

# Backward compatibility bridge for record_payout
def record_payout(**kwargs) -> Dict[str, Any]:
    # Map legacy fields to BountyWalletRegistry
    data = {
        "finding_id": kwargs.get("opportunity_id") or kwargs.get("workflow_id"),
        "run_id": kwargs.get("workflow_id"),
        "program_name": kwargs.get("program_name"),
        "platform": kwargs.get("platform", "custom"),
        "expected_amount": float(kwargs.get("payout_usd", 0)),
        "status": "triaged"
    }
    return upsert_bounty_record(data).model_dump(mode="json")
