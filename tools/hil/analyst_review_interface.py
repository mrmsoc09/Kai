from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools.hil.ai_verification_assistant import AIVerificationAssistant
from tools.hil.approval_workflow import ApprovalWorkflow
from tools.hil.hil_review_queue import HiLReviewQueue
from tools.hil.verification_checklist import HiLValidationError, VerificationChecklist


@dataclass(slots=True)
class AnalystSession:
    analyst_id: str
    active_review_finding_id: str | None = None


class AnalystReviewInterface:
    """
    Backend-style interface for analyst HiL operations.

    Blocking governance: approval path is denied until all required checklist
    items are completed.
    """

    def __init__(
        self,
        *,
        review_queue: HiLReviewQueue,
        approval_workflow: ApprovalWorkflow,
        ai_assistant: AIVerificationAssistant | None = None,
    ) -> None:
        self.review_queue = review_queue
        self.approval_workflow = approval_workflow
        self.ai_assistant = ai_assistant or AIVerificationAssistant()
        self.checklist_engine = VerificationChecklist()

    def list_pending_reviews(self, analyst_id: str, priority_filter: str | None = None) -> list[dict[str, Any]]:
        return self.review_queue.get_pending_reviews_for_analyst(analyst_id, priority_filter=priority_filter)

    def start_review(self, finding_id: str, analyst_id: str) -> dict[str, Any]:
        return self.review_queue.assign_to_analyst(finding_id, analyst_id)

    def get_review_item(self, finding_id: str) -> dict[str, Any]:
        for item in self.review_queue.pending_reviews + self.review_queue.in_progress_reviews:
            if str(item.get("finding_id", "")) == finding_id:
                return item
        raise KeyError(f"Review item not found: {finding_id}")

    def complete_checklist_item(
        self,
        *,
        finding_id: str,
        item_name: str,
        analyst_notes: str,
        analyst_severity_adjustment: str | None = None,
        analyst_payout_adjustment: int | None = None,
    ) -> dict[str, Any]:
        item = self.get_review_item(finding_id)
        checklist = item.get("verification_checklist", {})
        updated = self.checklist_engine.complete_item(
            checklist,
            item_name,
            analyst_notes=analyst_notes,
            analyst_severity_adjustment=analyst_severity_adjustment,
            analyst_payout_adjustment=analyst_payout_adjustment,
        )
        item["verification_checklist"] = updated
        return self.checklist_engine.completion_summary(updated)

    def run_ai_assistance(
        self,
        *,
        finding_id: str,
        scope_definition: dict[str, Any],
        target_context: dict[str, Any],
    ) -> dict[str, Any]:
        item = self.get_review_item(finding_id)
        finding = item.get("finding", {})
        poc_steps = list(finding.get("reproduction_steps", []))

        poc_review = self.ai_assistant.analyze_poc_clarity(poc_steps)
        scope_review = self.ai_assistant.validate_scope_compliance(finding, scope_definition)
        severity_review = self.ai_assistant.validate_severity_estimate(finding, target_context)

        return {
            "finding_id": finding_id,
            "poc_review": poc_review,
            "scope_review": scope_review,
            "severity_review": severity_review,
            "analyst_decision_required": True,
        }

    def approve_finding(self, finding_id: str, analyst_id: str, analyst_notes: str) -> dict[str, Any]:
        item = self.get_review_item(finding_id)
        checklist = item.get("verification_checklist", {})
        self.checklist_engine.validate_checklist_complete(checklist)
        return self.approval_workflow.analyst_approves_finding(finding_id, analyst_id, analyst_notes)

    def reject_finding(
        self,
        *,
        finding_id: str,
        analyst_id: str,
        rejection_reason: str,
        analyst_notes: str,
    ) -> dict[str, Any]:
        return self.approval_workflow.analyst_rejects_finding(
            finding_id,
            analyst_id,
            rejection_reason,
            analyst_notes,
        )

    def request_changes(self, finding_id: str, analyst_id: str, analyst_notes: str) -> dict[str, Any]:
        item = self.get_review_item(finding_id)
        item["status"] = "changes_requested"
        item["analyst_assigned"] = analyst_id
        item["analyst_notes"] = analyst_notes
        self.review_queue.log_queue_event(
            "changes_requested",
            {
                "finding_id": finding_id,
                "analyst_id": analyst_id,
                "analyst_notes": analyst_notes,
            },
        )
        return {
            "finding_id": finding_id,
            "status": "changes_requested",
            "analyst_id": analyst_id,
            "notes": analyst_notes,
        }


__all__ = ["AnalystReviewInterface", "AnalystSession", "HiLValidationError"]
