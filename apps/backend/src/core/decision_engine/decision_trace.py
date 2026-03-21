from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .decision_policy import PolicyDecision
from .hypothesis_engine import Hypothesis


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trace_path() -> Path:
    raw = os.getenv("K1_DECISION_TRACE_PATH", "artifacts/decision/decision_trace.jsonl")
    path = Path(raw).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class DecisionTrace:
    trace_id: str
    timestamp: str
    input_evidence: list[dict[str, Any]]
    hypotheses_considered: list[dict[str, Any]]
    chosen_action: str
    rejected_alternatives: list[dict[str, Any]]
    reason_code: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "input_evidence": self.input_evidence,
            "hypotheses_considered": self.hypotheses_considered,
            "chosen_action": self.chosen_action,
            "rejected_alternatives": self.rejected_alternatives,
            "reason_code": self.reason_code,
            "metadata": self.metadata,
        }


class DecisionTraceRecorder:
    """
    Deterministic decision trace sink (JSONL).
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _trace_path()

    def build_trace(
        self,
        *,
        input_evidence: Sequence[Mapping[str, Any]],
        hypotheses: Sequence[Hypothesis | Mapping[str, Any]],
        decision: PolicyDecision,
        metadata: Mapping[str, Any] | None = None,
    ) -> DecisionTrace:
        hypothesis_rows = [
            row.to_dict() if isinstance(row, Hypothesis) else dict(row)
            for row in hypotheses
        ]
        return DecisionTrace(
            trace_id=f"trace-{uuid.uuid4().hex[:12]}",
            timestamp=_utcnow_iso(),
            input_evidence=[dict(row) for row in input_evidence],
            hypotheses_considered=hypothesis_rows,
            chosen_action=decision.chosen_action.value,
            rejected_alternatives=[row.to_dict() for row in decision.rejected_alternatives],
            reason_code=decision.reason_code,
            metadata=dict(metadata or {}),
        )

    def record(self, trace: DecisionTrace) -> None:
        row = trace.to_dict()
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
