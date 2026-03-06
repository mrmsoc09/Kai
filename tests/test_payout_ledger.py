from __future__ import annotations

from apps.backend.src.core.payout_ledger import (
    list_payout_records,
    summarize_month,
    upsert_payout_record,
)


def test_payout_ledger_upsert_and_linking(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_PAYOUT_LEDGER_PATH", str(tmp_path / "ledger.json"))
    rec = upsert_payout_record(
        {
            "run_id": "run-9",
            "finding_id": "finding-1",
            "program_id": "h1-abc",
            "expected_amount": 1500,
            "actual_amount": 1200,
            "fees": 120,
            "status": "accepted",
        }
    )
    assert rec["net_amount"] == 1080
    rows = list_payout_records()
    assert len(rows) == 1
    assert rows[0]["run_id"] == "run-9"
    assert rows[0]["finding_id"] == "finding-1"


def test_payout_monthly_reconciliation(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_PAYOUT_LEDGER_PATH", str(tmp_path / "ledger.json"))
    upsert_payout_record(
        {"run_id": "r1", "finding_id": "f1", "actual_amount": 1000, "fees": 100, "expected_amount": 1200}
    )
    upsert_payout_record(
        {"run_id": "r2", "finding_id": "f2", "actual_amount": 500, "fees": 50, "expected_amount": 600}
    )
    rows = list_payout_records()
    first = rows[0]
    dt = first["updated_at"].split("T", 1)[0].split("-")
    year, month = int(dt[0]), int(dt[1])
    summary = summarize_month(year, month)
    assert summary["count"] == 2
    assert summary["totals"]["actual_amount"] == 1500
    assert summary["totals"]["net_amount"] == 1350
