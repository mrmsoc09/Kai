from __future__ import annotations

import asyncio

import pytest

from apps.backend.src.core.hil_db import dispose_async_engine
from apps.backend.src.core.tool_execution_store import ToolExecutionStore


@pytest.mark.asyncio
async def test_tool_execution_store_lifecycle():
    await dispose_async_engine()
    try:
        store = ToolExecutionStore()
        created = await asyncio.wait_for(
            store.create_pending("e1", "tool", {"a": 1}, run_id="r1", user_id="u1"),
            timeout=10,
        )
        assert created.status == "pending_approval"

        rec = await asyncio.wait_for(store.get("e1"), timeout=10)
        assert rec is not None
        assert rec.tool_id == "tool"

        done = await asyncio.wait_for(store.mark_completed("e1", {"ok": True}), timeout=10)
        assert done is not None
        assert done.status == "completed"
        assert done.result["ok"] is True
    finally:
        await dispose_async_engine()
