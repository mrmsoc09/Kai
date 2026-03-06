from __future__ import annotations

import json
from pathlib import Path

from apps.backend.src.core.kpi_metrics import build_kpi_snapshot
from apps.backend.src.core.payout_ledger import upsert_payout_record
from apps.backend.src.core.submission_lifecycle import transition_submission_state


def test_kpi_snapshot_reflects_submission_and_payout(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("K1_SUBMISSION_STATE_DIR", str(tmp_path / "states"))
    monkeypatch.setenv("K1_PAYOUT_LEDGER_PATH", str(tmp_path / "ledger.json"))
    learning_path = tmp_path / "reflective_state.json"
    learning_path.write_text(json.dumps({"outcomes": [{"outcome": "duplicate"}]}), encoding="utf-8")
    monkeypatch.setenv("K1_REFLECTIVE_STATE_PATH", str(learning_path))

    transition_submission_state("run-1", "ready_for_submission")
    transition_submission_state("run-1", "packaged")
    transition_submission_state("run-1", "dispatched")
    transition_submission_state("run-1", "accepted")
    upsert_payout_record(
        {
            "run_id": "run-1",
            "finding_id": "f1",
            "actual_amount": 1000,
            "fees": 50,
        }
    )

    snapshot = build_kpi_snapshot()
    assert snapshot["reports_submitted"] >= 1
    assert snapshot["reports_accepted"] >= 1
    assert snapshot["payouts"]["net_amount"] == 950.0
