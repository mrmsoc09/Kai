from __future__ import annotations

import json

from apps.backend.src.core.model_decision_observability import emit_model_decision_event


def test_model_decision_observability_writes_event(monkeypatch, tmp_path):
    path = tmp_path / "telemetry.jsonl"
    monkeypatch.setenv("K1_MODEL_TELEMETRY_PATH", str(path))
    emit_model_decision_event({"location_id": "x", "task_id": "t1"})
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["location_id"] == "x"
    assert payload["task_id"] == "t1"
