from __future__ import annotations

from apps.backend.src.core.comms_store import append_message, get_thread, list_threads


def test_comms_store_thread_linking(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_COMMS_ROOT", str(tmp_path / "comms"))
    msg = append_message(
        run_id="run-1",
        finding_id="finding-7",
        report_id="report-9",
        stakeholder="h1",
        channel="email",
        direction="outbound",
        subject="Initial Submission",
        body="Body",
        artifact_path="artifacts/submissions/outbox/run-1_h1.eml",
        metadata={"status": "prepared"},
    )
    assert msg["message_id"]

    threads = list_threads(run_id="run-1")
    assert len(threads) == 1
    thread = threads[0]
    assert thread["run_id"] == "run-1"
    assert thread["finding_id"] == "finding-7"
    assert thread["report_id"] == "report-9"
    assert thread["messages"][0]["subject"] == "Initial Submission"

    loaded = get_thread(thread["thread_id"])
    assert loaded is not None
    assert loaded["messages"][0]["channel"] == "email"
