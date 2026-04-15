from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RoundRobinEntry:
    opportunity_id: str
    position_in_queue: int
    confidence: float
    estimated_payout: float
    scanned_today: bool = False
    scan_completion_time: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "position_in_queue": self.position_in_queue,
            "confidence": self.confidence,
            "estimated_payout": self.estimated_payout,
            "scanned_today": self.scanned_today,
            "scan_completion_time": self.scan_completion_time,
        }


class RoundRobinCycleManager:
    """
    Round-robin cycle manager.

    Behavior:
    - Initializes a cycle from sorted opportunities.
    - Returns next unscanned opportunity.
    - Marks scanned opportunities and removes them from active queue.
    - Renews cycle after completion.
    """

    def __init__(
        self,
        *,
        event_log_path: str | Path = "tools/orchestration/data/round_robin_events.jsonl",
        state_path: str | Path = "tools/orchestration/data/round_robin_state.yaml",
    ) -> None:
        self.current_round_robin_list: list[dict[str, Any]] = []
        self.round_robin_history: list[dict[str, Any]] = []
        self.last_renewal_date: str | None = None

        self.event_log_path = Path(event_log_path)
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.event_log_path.exists():
            self.event_log_path.write_text("", encoding="utf-8")

        self.state_path = Path(state_path)
        self._load_state()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _today() -> str:
        return datetime.now(UTC).date().isoformat()

    @staticmethod
    def _stable_json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def log_round_robin_event(self, event_type: str, opportunity_id: str | None, extra: dict[str, Any] | None = None) -> None:
        payload = {
            "event_time": self._now(),
            "event_type": event_type,
            "opportunity_id": opportunity_id,
            "extra": extra or {},
        }
        with self.event_log_path.open("a", encoding="utf-8") as f:
            f.write(self._stable_json(payload) + "\n")

    def _persist_state(self) -> None:
        payload = {
            "last_renewal_date": self.last_renewal_date,
            "current_round_robin_list": self.current_round_robin_list,
            "round_robin_history": self.round_robin_history,
            "saved_at": self._now(),
        }
        text = json.dumps(payload, indent=2, sort_keys=False)
        self.state_path.write_text(text, encoding="utf-8")

    def _load_state(self) -> None:
        if not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(payload, dict):
            return

        current = payload.get("current_round_robin_list", [])
        history = payload.get("round_robin_history", [])
        if isinstance(current, list):
            self.current_round_robin_list = [x for x in current if isinstance(x, dict)]
        if isinstance(history, list):
            self.round_robin_history = [x for x in history if isinstance(x, dict)]
        self.last_renewal_date = str(payload.get("last_renewal_date", "")) or None

    def initialize_round_robin_list(self, sorted_opportunities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        queue: list[dict[str, Any]] = []
        for idx, opp in enumerate(sorted_opportunities):
            opportunity_id = str(opp.get("opportunity_id") or opp.get("id") or "").strip()
            if not opportunity_id:
                continue
            entry = RoundRobinEntry(
                opportunity_id=opportunity_id,
                position_in_queue=idx,
                confidence=float(opp.get("confidence_score", opp.get("confidence", 0.0))),
                estimated_payout=float(opp.get("estimated_payout", 0.0)),
            )
            queue.append(entry.as_dict())

        self.current_round_robin_list = queue
        self.last_renewal_date = self._today()
        self.log_round_robin_event(
            "round_robin_initialized",
            None,
            extra={"queue_size": len(queue), "renewal_date": self.last_renewal_date},
        )
        self._persist_state()
        return list(self.current_round_robin_list)

    def replace_current_queue(self, queue_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.current_round_robin_list = [dict(x) for x in queue_items if isinstance(x, dict)]
        for idx, row in enumerate(self.current_round_robin_list):
            row["position_in_queue"] = idx
        self._persist_state()
        self.log_round_robin_event(
            "round_robin_reprioritized",
            None,
            extra={"queue_size": len(self.current_round_robin_list)},
        )
        return list(self.current_round_robin_list)

    def get_next_round_robin_opportunity(self) -> dict[str, Any] | None:
        if not self.current_round_robin_list:
            return None

        # The queue is maintained as active/unscanned items only.
        return dict(self.current_round_robin_list[0])

    def mark_opportunity_scanned(self, opportunity_id: str) -> bool:
        for idx, opp in enumerate(self.current_round_robin_list):
            if str(opp.get("opportunity_id", "")) != opportunity_id:
                continue

            record = dict(opp)
            record["scanned_today"] = True
            record["scan_completion_time"] = self._now()

            self.current_round_robin_list.pop(idx)
            self.log_round_robin_event(
                "opportunity_scanned_and_removed",
                opportunity_id,
                extra={"remaining_queue_size": len(self.current_round_robin_list), "record": record},
            )
            self._persist_state()
            return True

        return False

    def check_if_round_robin_cycle_complete(self) -> bool:
        return len(self.current_round_robin_list) == 0

    def get_scanned_count_from_history(self) -> int:
        count = 0
        with self.event_log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get("event_type") == "opportunity_scanned_and_removed":
                    count += 1
        return count

    def renew_round_robin_cycle(self, newly_sorted_opportunities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        history_item = {
            "cycle_start_date": self.last_renewal_date,
            "cycle_end_date": self._today(),
            "opportunities_scanned": self.get_scanned_count_from_history(),
        }
        self.round_robin_history.append(history_item)

        renewed = self.initialize_round_robin_list(newly_sorted_opportunities)
        self.log_round_robin_event(
            "round_robin_cycle_renewed",
            None,
            extra={"history_item": history_item, "new_queue_size": len(renewed)},
        )
        self._persist_state()
        return renewed


__all__ = ["RoundRobinCycleManager", "RoundRobinEntry"]
