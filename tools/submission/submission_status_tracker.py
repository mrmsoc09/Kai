from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from tools.ai.learning_feedback_loop import LearningFeedbackLoop
from tools.submission.platform_api_submission import PlatformAPISubmissionClient


class SubmissionStatusTracker:
    """Tracks submission outcomes and feeds accepted results back into learning."""

    FINAL_STATES = {"accepted", "rejected", "duplicate", "out_of_scope", "paid"}

    def __init__(
        self,
        *,
        api_client: PlatformAPISubmissionClient | None = None,
        learning_loop: LearningFeedbackLoop | None = None,
        outcomes_path: str | Path = "tools/submission/data/submission_outcomes.yaml",
    ) -> None:
        self.api_client = api_client or PlatformAPISubmissionClient()
        self.learning_loop = learning_loop or LearningFeedbackLoop()

        self.outcomes_path = Path(outcomes_path)
        self.outcomes_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = self._load_db()

    def _load_db(self) -> dict[str, Any]:
        if not self.outcomes_path.exists():
            return {
                "version": "1.0",
                "created_at": datetime.now(UTC).isoformat(),
                "records": [],
            }

        payload = yaml.safe_load(self.outcomes_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid outcomes database payload: {self.outcomes_path}")
        payload.setdefault("records", [])
        return payload

    def _save_db(self) -> None:
        self.outcomes_path.write_text(yaml.safe_dump(self._db, sort_keys=False), encoding="utf-8")

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _normalize(value: str | None) -> str:
        return (value or "").strip().lower()

    def poll_submission_status(self, submission_id: str, platform: str) -> dict[str, Any]:
        result = self.api_client.poll_status(platform=platform, submission_id=submission_id)
        return {
            "submission_id": submission_id,
            "platform": platform,
            "poll_time": self._now(),
            "current_status": result.get("platform_status") or result.get("status"),
            "status_payload": result,
            "payout_received": (
                result.get("payload", {}).get("payout")
                if isinstance(result.get("payload"), dict)
                else None
            ),
            "platform_feedback": (
                result.get("payload", {}).get("feedback")
                if isinstance(result.get("payload"), dict)
                else None
            ),
        }

    def record_submission_outcome(
        self,
        *,
        submission_id: str,
        platform: str,
        outcome: dict[str, Any],
        finding: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        estimated_payout = int(outcome.get("estimated_payout", 0) or 0)
        actual_payout = int(outcome.get("payout_amount", 0) or 0)
        status = self._normalize(str(outcome.get("status", "unknown")))

        payout_accuracy = round((actual_payout / max(1, estimated_payout)), 3)

        record = {
            "submission_id": submission_id,
            "platform": platform,
            "outcome_status": status,
            "actual_payout": actual_payout,
            "estimated_payout": estimated_payout,
            "payout_accuracy": payout_accuracy,
            "platform_feedback": outcome.get("feedback"),
            "recorded_at": self._now(),
        }
        self._db["records"].append(record)
        self._save_db()

        # Feed learning loop for closed outcomes when finding context is available.
        if finding and status in self.FINAL_STATES:
            learning_outcome = {
                "payout_received": actual_payout,
                "platform_decision": status,
                "analyst_feedback": str(outcome.get("feedback", "")),
                "pattern_names": list(outcome.get("pattern_names", [])),
                "resolution_date": record["recorded_at"],
            }
            self.learning_loop.record_finding_outcome(finding=finding, outcome=learning_outcome)

        return record

    def get_status_summary(self) -> dict[str, Any]:
        rows = self._db.get("records", [])
        if not rows:
            return {
                "record_count": 0,
                "acceptance_rate": 0.0,
                "paid_rate": 0.0,
                "mean_payout_accuracy": 0.0,
            }

        accepted = sum(1 for row in rows if self._normalize(str(row.get("outcome_status"))) == "accepted")
        paid = sum(1 for row in rows if self._normalize(str(row.get("outcome_status"))) == "paid")
        avg_accuracy = round(sum(float(row.get("payout_accuracy", 0.0)) for row in rows) / len(rows), 3)

        return {
            "record_count": len(rows),
            "acceptance_rate": round((accepted / len(rows)) * 100, 2),
            "paid_rate": round((paid / len(rows)) * 100, 2),
            "mean_payout_accuracy": avg_accuracy,
        }


__all__ = ["SubmissionStatusTracker"]
