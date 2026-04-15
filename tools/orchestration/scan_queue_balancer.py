from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ScheduledScan:
    scan_type: str
    scan: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"scan_type": self.scan_type, "scan": self.scan}


class ScanQueueBalancer:
    """
    Dual-queue fair scheduler for round-robin and intelligent scans.

    Fairness model:
    - Target allocation: 50% round-robin / 50% intelligent by execution time.
    - Starvation prevention: enforce max consecutive picks from same queue when alternate has work.
    - Deficit-aware scheduling: queue behind target allocation is preferred.
    """

    def __init__(
        self,
        *,
        target_allocation: tuple[float, float] = (0.5, 0.5),
        max_consecutive_same_queue: int = 2,
        event_log_path: str | Path = "tools/orchestration/data/scan_queue_balancer_events.jsonl",
    ) -> None:
        rr, intel = target_allocation
        total = rr + intel
        if total <= 0:
            rr, intel = 0.5, 0.5
        else:
            rr, intel = rr / total, intel / total

        self.time_budget_allocation = {"round_robin": rr, "intelligent": intel}
        self.max_consecutive_same_queue = max(1, int(max_consecutive_same_queue))

        self.round_robin_queue: list[dict[str, Any]] = []
        self.intelligent_scan_queue: list[dict[str, Any]] = []
        self.scan_history: list[dict[str, Any]] = []
        self.last_scheduled_type: str | None = None
        self._consecutive_picks: int = 0

        self.event_log_path = Path(event_log_path)
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.event_log_path.exists():
            self.event_log_path.write_text("", encoding="utf-8")

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _stable_json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def _log_event(self, event_type: str, payload: dict[str, Any]) -> None:
        row = {"event_type": event_type, "event_time": self._now(), "payload": payload}
        with self.event_log_path.open("a", encoding="utf-8") as f:
            f.write(self._stable_json(row) + "\n")

    @staticmethod
    def _scan_duration(scan: dict[str, Any]) -> float:
        duration = scan.get("estimated_duration_minutes")
        if duration is None:
            duration = scan.get("execution_time_minutes", 20)
        try:
            return max(1.0, float(duration))
        except (TypeError, ValueError):
            return 20.0

    def load_round_robin_queue(self, scans: list[dict[str, Any]]) -> None:
        self.round_robin_queue = [dict(x) for x in scans if isinstance(x, dict)]
        self._log_event("round_robin_queue_loaded", {"size": len(self.round_robin_queue)})

    def load_intelligent_scan_queue(self, scans: list[dict[str, Any]]) -> None:
        # Keep highest-priority intelligent scans at front.
        prepared = [dict(x) for x in scans if isinstance(x, dict)]
        prepared.sort(key=lambda row: float(row.get("priority", 0.0)), reverse=True)
        self.intelligent_scan_queue = prepared
        self._log_event("intelligent_queue_loaded", {"size": len(self.intelligent_scan_queue)})

    def calculate_time_used(self, scan_type: str) -> float:
        key = scan_type.strip().lower()
        total = 0.0
        for row in self.scan_history:
            if str(row.get("scan_type", "")).lower() != key:
                continue
            total += float(row.get("duration_minutes", 0.0))
        return round(total, 2)

    def _effective_ratio(self, scan_type: str) -> float:
        rr_time = self.calculate_time_used("round_robin")
        int_time = self.calculate_time_used("intelligent")
        total = rr_time + int_time
        if total <= 0:
            return 0.0

        if scan_type == "round_robin":
            return rr_time / total
        return int_time / total

    def _deficit(self, scan_type: str) -> float:
        target = self.time_budget_allocation[scan_type]
        current = self._effective_ratio(scan_type)
        return round(target - current, 4)

    def _choose_type_by_fairness(self) -> str | None:
        rr_available = len(self.round_robin_queue) > 0
        int_available = len(self.intelligent_scan_queue) > 0

        if not rr_available and not int_available:
            return None
        if rr_available and not int_available:
            return "round_robin"
        if int_available and not rr_available:
            return "intelligent"

        # Starvation guard: if one queue was repeatedly selected and the other has work, flip.
        if self.last_scheduled_type and self._consecutive_picks >= self.max_consecutive_same_queue:
            alt = "intelligent" if self.last_scheduled_type == "round_robin" else "round_robin"
            return alt

        rr_deficit = self._deficit("round_robin")
        int_deficit = self._deficit("intelligent")

        # Prefer the queue that is behind its target allocation.
        if rr_deficit > int_deficit:
            return "round_robin"
        if int_deficit > rr_deficit:
            return "intelligent"

        # Tie-breaker: alternate if possible.
        if self.last_scheduled_type == "round_robin":
            return "intelligent"
        return "round_robin"

    def get_next_round_robin_scan(self) -> dict[str, Any] | None:
        if not self.round_robin_queue:
            return None
        return self.round_robin_queue.pop(0)

    def get_next_intelligent_scan(self) -> dict[str, Any] | None:
        if not self.intelligent_scan_queue:
            return None
        return self.intelligent_scan_queue.pop(0)

    def schedule_next_scan(self) -> dict[str, Any] | None:
        chosen = self._choose_type_by_fairness()
        if not chosen:
            return None

        if chosen == "round_robin":
            scan = self.get_next_round_robin_scan()
        else:
            scan = self.get_next_intelligent_scan()

        if not scan:
            return None

        if self.last_scheduled_type == chosen:
            self._consecutive_picks += 1
        else:
            self.last_scheduled_type = chosen
            self._consecutive_picks = 1

        scheduled = ScheduledScan(scan_type=chosen, scan=scan).as_dict()
        self._log_event(
            "scan_scheduled",
            {
                "scan_type": chosen,
                "scan_id": scan.get("scan_id") or scan.get("opportunity_id") or scan.get("trigger_cve"),
                "remaining_round_robin": len(self.round_robin_queue),
                "remaining_intelligent": len(self.intelligent_scan_queue),
                "deficit_round_robin": self._deficit("round_robin"),
                "deficit_intelligent": self._deficit("intelligent"),
            },
        )
        return scheduled

    def record_scan_completion(
        self,
        *,
        scan_type: str,
        scan: dict[str, Any],
        duration_minutes: float,
        status: str = "completed",
    ) -> dict[str, Any]:
        row = {
            "finished_at": self._now(),
            "scan_type": scan_type,
            "scan": dict(scan),
            "duration_minutes": round(max(0.1, float(duration_minutes)), 2),
            "status": status,
        }
        self.scan_history.append(row)
        self._log_event("scan_completed", row)
        return row

    def queue_snapshot(self) -> dict[str, Any]:
        rr_time = self.calculate_time_used("round_robin")
        int_time = self.calculate_time_used("intelligent")
        total = rr_time + int_time
        rr_ratio = rr_time / total if total > 0 else 0.0
        int_ratio = int_time / total if total > 0 else 0.0

        return {
            "round_robin_queue_size": len(self.round_robin_queue),
            "intelligent_queue_size": len(self.intelligent_scan_queue),
            "time_used_minutes": {"round_robin": rr_time, "intelligent": int_time},
            "time_allocation_target": self.time_budget_allocation,
            "time_allocation_actual": {
                "round_robin": round(rr_ratio, 4),
                "intelligent": round(int_ratio, 4),
            },
            "deficits": {
                "round_robin": self._deficit("round_robin"),
                "intelligent": self._deficit("intelligent"),
            },
            "last_scheduled_type": self.last_scheduled_type,
            "consecutive_picks": self._consecutive_picks,
            "history_count": len(self.scan_history),
        }


__all__ = ["ScanQueueBalancer", "ScheduledScan"]
