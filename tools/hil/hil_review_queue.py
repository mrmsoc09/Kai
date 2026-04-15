from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from tools.hil.verification_checklist import VerificationChecklist


class HiLReviewQueue:
    """
    In-memory HiL review queue with routing, assignment and priority ordering.

    Intended as a deterministic backend component for approval gating.
    """

    PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

    def __init__(self) -> None:
        self.pending_reviews: list[dict[str, Any]] = []
        self.in_progress_reviews: list[dict[str, Any]] = []
        self.approval_history: list[dict[str, Any]] = []
        self.rejected_history: list[dict[str, Any]] = []
        self.queue_events: list[dict[str, Any]] = []
        self.checklist_engine = VerificationChecklist()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _normalize(text: str | None) -> str:
        return (text or "").strip().upper()

    def log_queue_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "timestamp": self._now(),
            "payload": payload,
        }
        self.queue_events.append(event)
        return event

    def calculate_priority(self, finding: dict[str, Any]) -> str:
        severity = self._normalize(str((finding.get("severity") or {}).get("severity_level", "MEDIUM")))
        if severity in self.PRIORITY_ORDER:
            return severity

        severity_est = self._normalize(str((finding.get("categorization") or {}).get("severity_estimate", "MEDIUM")))
        if severity_est in self.PRIORITY_ORDER:
            return severity_est

        return "MEDIUM"

    def enqueue_finding_for_review(self, finding: dict[str, Any], automation_source: str) -> dict[str, Any]:
        item = {
            "review_id": str(uuid4()),
            "finding_id": finding.get("finding_id") or finding.get("id") or str(uuid4()),
            "finding": finding,
            "automation_source": automation_source,
            "status": "pending_review",
            "enqueued_at": self._now(),
            "priority": self.calculate_priority(finding),
            "analyst_assigned": None,
            "review_started_at": None,
            "review_completed_at": None,
            "analyst_decision": None,
            "analyst_notes": None,
            "analyst_signature": None,
            "verification_checklist": self.checklist_engine.generate_checklist_for_finding(finding),
        }
        self.pending_reviews.append(item)
        self.log_queue_event("finding_enqueued", {"finding_id": item["finding_id"], "priority": item["priority"]})
        return item

    def _sort_reviews(self, reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            reviews,
            key=lambda r: (
                self.PRIORITY_ORDER.get(str(r.get("priority", "MEDIUM")), 99),
                str(r.get("enqueued_at", "")),
            ),
        )

    def get_pending_reviews_for_analyst(
        self,
        analyst_id: str,
        priority_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        pending = [r for r in self.pending_reviews if str(r.get("status", "")) == "pending_review"]
        if priority_filter:
            pf = self._normalize(priority_filter)
            pending = [r for r in pending if self._normalize(str(r.get("priority", ""))) == pf]
        return self._sort_reviews(pending)

    def _locate(self, finding_id: str) -> tuple[str, dict[str, Any] | None]:
        for qname, queue in [
            ("pending", self.pending_reviews),
            ("in_progress", self.in_progress_reviews),
        ]:
            for item in queue:
                if str(item.get("finding_id", "")) == finding_id:
                    return qname, item
        return "", None

    def assign_to_analyst(self, finding_id: str, analyst_id: str) -> dict[str, Any]:
        qname, item = self._locate(finding_id)
        if not item:
            raise KeyError(f"Finding not found in review queues: {finding_id}")

        if qname == "pending":
            self.pending_reviews = [x for x in self.pending_reviews if x is not item]
            self.in_progress_reviews.append(item)

        item["status"] = "in_review"
        item["analyst_assigned"] = analyst_id
        item["review_started_at"] = item.get("review_started_at") or self._now()

        self.log_queue_event("review_assigned", {"finding_id": finding_id, "analyst_id": analyst_id})
        return item

    def mark_review_decision(
        self,
        *,
        finding_id: str,
        decision: str,
        analyst_id: str,
        analyst_notes: str,
        analyst_signature: str,
    ) -> dict[str, Any]:
        qname, item = self._locate(finding_id)
        if not item:
            raise KeyError(f"Finding not found: {finding_id}")

        item["status"] = "review_completed"
        item["analyst_decision"] = decision
        item["analyst_assigned"] = analyst_id
        item["analyst_notes"] = analyst_notes
        item["analyst_signature"] = analyst_signature
        item["review_completed_at"] = self._now()

        if qname == "in_progress":
            self.in_progress_reviews = [x for x in self.in_progress_reviews if x is not item]

        if decision.upper() == "APPROVED":
            self.approval_history.append(item)
        else:
            self.rejected_history.append(item)

        self.log_queue_event(
            "review_decision",
            {
                "finding_id": finding_id,
                "decision": decision,
                "analyst_id": analyst_id,
            },
        )
        return item


__all__ = ["HiLReviewQueue"]
