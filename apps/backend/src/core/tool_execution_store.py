from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional


@dataclass
class ExecutionRecord:
    execution_id: str
    tool_id: str
    params: Dict[str, Any]
    status: str
    created_at: str
    updated_at: str
    run_id: Optional[str] = None
    user_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    rejected_reason: Optional[str] = None


class ToolExecutionStore:
    def __init__(self) -> None:
        self._records: Dict[str, ExecutionRecord] = {}
        self._lock = Lock()

    def create_pending(self, execution_id: str, tool_id: str, params: Dict[str, Any], run_id: str | None, user_id: str | None) -> ExecutionRecord:
        now = datetime.now(timezone.utc).isoformat()
        rec = ExecutionRecord(
            execution_id=execution_id,
            tool_id=tool_id,
            params=dict(params),
            status="pending_approval",
            created_at=now,
            updated_at=now,
            run_id=run_id,
            user_id=user_id,
        )
        with self._lock:
            self._records[execution_id] = rec
        return rec

    def get(self, execution_id: str) -> Optional[ExecutionRecord]:
        with self._lock:
            rec = self._records.get(execution_id)
            if not rec:
                return None
            return ExecutionRecord(**asdict(rec))

    def mark_completed(self, execution_id: str, result: Dict[str, Any]) -> Optional[ExecutionRecord]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            rec = self._records.get(execution_id)
            if not rec:
                return None
            rec.status = "completed"
            rec.result = dict(result)
            rec.updated_at = now
            return ExecutionRecord(**asdict(rec))

    def mark_rejected(self, execution_id: str, reason: str | None) -> Optional[ExecutionRecord]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            rec = self._records.get(execution_id)
            if not rec:
                return None
            rec.status = "rejected"
            rec.rejected_reason = reason
            rec.updated_at = now
            return ExecutionRecord(**asdict(rec))


_STORE = ToolExecutionStore()


def get_tool_execution_store() -> ToolExecutionStore:
    return _STORE
