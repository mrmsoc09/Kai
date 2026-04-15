from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
from typing import Any

from tools.hil.hil_audit_trail import HiLAuditTrail
from tools.hil.hil_review_queue import HiLReviewQueue
from tools.hil.verification_checklist import HiLValidationError, VerificationChecklist


class ApprovalWorkflow:
    """
    Approval/rejection workflow with signatures and non-repudiation tokens.
    """

    def __init__(
        self,
        *,
        review_queue: HiLReviewQueue,
        audit_trail: HiLAuditTrail,
        signing_key: str = "k1-hil-approval-signing-key",
    ) -> None:
        self.review_queue = review_queue
        self.audit_trail = audit_trail
        self.signing_key = signing_key.encode("utf-8")
        self.checklist_engine = VerificationChecklist()
        self.approved_queue: list[dict[str, Any]] = []
        self.rejected_queue: list[dict[str, Any]] = []

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def create_digital_signature(self, analyst_id: str, finding_id: str) -> str:
        msg = f"{analyst_id}:{finding_id}:{self._now()}"
        return hmac.new(self.signing_key, msg.encode("utf-8"), hashlib.sha256).hexdigest()

    def generate_non_repudiation_token(
        self,
        *,
        finding_id: str,
        analyst_id: str,
        decision: str,
        digital_signature: str,
        timestamp: str,
    ) -> str:
        payload = f"{finding_id}|{analyst_id}|{decision}|{digital_signature}|{timestamp}"
        return self._hash(payload)

    @staticmethod
    def get_analyst_name(analyst_id: str) -> str:
        return f"analyst::{analyst_id}"

    def _get_review_item(self, finding_id: str) -> dict[str, Any]:
        search_spaces = (
            self.review_queue.pending_reviews
            + self.review_queue.in_progress_reviews
            + self.review_queue.approval_history
            + self.review_queue.rejected_history
            + self.approved_queue
            + self.rejected_queue
        )
        for item in search_spaces:
            if str(item.get("finding_id", "")) == finding_id:
                return item
        raise KeyError(f"Finding not found in HiL workflow state: {finding_id}")

    def get_completion_summary(self, finding_id: str) -> dict[str, Any]:
        item = self._get_review_item(finding_id)
        checklist = item.get("verification_checklist", {})
        return self.checklist_engine.completion_summary(checklist)

    def _assert_checklist_complete(self, finding_id: str) -> dict[str, Any]:
        item = self._get_review_item(finding_id)
        checklist = item.get("verification_checklist", {})
        self.checklist_engine.validate_checklist_complete(checklist)
        return checklist

    def move_to_approved_queue(self, item: dict[str, Any]) -> None:
        self.approved_queue.append(item)

    def move_to_rejected_queue(self, item: dict[str, Any]) -> None:
        self.rejected_queue.append(item)

    def analyst_approves_finding(self, finding_id: str, analyst_id: str, analyst_notes: str) -> dict[str, Any]:
        checklist = self._assert_checklist_complete(finding_id)
        item = self._get_review_item(finding_id)

        timestamp = self._now()
        signature = self.create_digital_signature(analyst_id, finding_id)
        token = self.generate_non_repudiation_token(
            finding_id=finding_id,
            analyst_id=analyst_id,
            decision="APPROVED",
            digital_signature=signature,
            timestamp=timestamp,
        )

        completion = self.checklist_engine.completion_summary(checklist)
        approval_record = {
            "finding_id": finding_id,
            "decision": "APPROVED",
            "analyst_id": analyst_id,
            "analyst_name": self.get_analyst_name(analyst_id),
            "approval_timestamp": timestamp,
            "analyst_notes": analyst_notes,
            "digital_signature": signature,
            "non_repudiation_token": token,
            "checklist_completion": completion,
        }

        self.review_queue.mark_review_decision(
            finding_id=finding_id,
            decision="APPROVED",
            analyst_id=analyst_id,
            analyst_notes=analyst_notes,
            analyst_signature=signature,
        )
        item["approval_record"] = approval_record
        self.move_to_approved_queue(item)

        self.audit_trail.record_hil_event(
            event_type="finding_approved",
            finding_id=finding_id,
            analyst_id=analyst_id,
            event_data=approval_record,
        )
        return approval_record

    def analyst_rejects_finding(
        self,
        finding_id: str,
        analyst_id: str,
        rejection_reason: str,
        analyst_notes: str,
    ) -> dict[str, Any]:
        item = self._get_review_item(finding_id)
        timestamp = self._now()
        signature = self.create_digital_signature(analyst_id, finding_id)
        token = self.generate_non_repudiation_token(
            finding_id=finding_id,
            analyst_id=analyst_id,
            decision="REJECTED",
            digital_signature=signature,
            timestamp=timestamp,
        )

        rejection_record = {
            "finding_id": finding_id,
            "decision": "REJECTED",
            "analyst_id": analyst_id,
            "analyst_name": self.get_analyst_name(analyst_id),
            "rejection_reason": rejection_reason,
            "analyst_notes": analyst_notes,
            "rejection_timestamp": timestamp,
            "digital_signature": signature,
            "non_repudiation_token": token,
        }

        self.review_queue.mark_review_decision(
            finding_id=finding_id,
            decision="REJECTED",
            analyst_id=analyst_id,
            analyst_notes=analyst_notes,
            analyst_signature=signature,
        )
        item["rejection_record"] = rejection_record
        self.move_to_rejected_queue(item)

        self.audit_trail.record_hil_event(
            event_type="finding_rejected",
            finding_id=finding_id,
            analyst_id=analyst_id,
            event_data=rejection_record,
        )
        return rejection_record


__all__ = ["ApprovalWorkflow", "HiLValidationError"]
