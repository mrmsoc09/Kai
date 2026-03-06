from __future__ import annotations

from apps.backend.src.core.tool_execution_store import ToolExecutionStore


def test_tool_execution_store_lifecycle():
    store = ToolExecutionStore()
    created = store.create_pending("e1", "tool", {"a": 1}, run_id="r1", user_id="u1")
    assert created.status == "pending_approval"

    rec = store.get("e1")
    assert rec is not None
    assert rec.tool_id == "tool"

    done = store.mark_completed("e1", {"ok": True})
    assert done is not None
    assert done.status == "completed"
    assert done.result["ok"] is True
