from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


class HiLValidationError(ValueError):
    pass


@dataclass(slots=True)
class ChecklistItem:
    item: str
    description: str
    required: bool = True
    completed: bool = False
    analyst_notes: str | None = None
    analyst_severity_adjustment: str | None = None
    analyst_payout_adjustment: int | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "item": self.item,
            "description": self.description,
            "required": self.required,
            "completed": self.completed,
            "analyst_notes": self.analyst_notes,
        }
        if self.analyst_severity_adjustment is not None:
            payload["analyst_severity_adjustment"] = self.analyst_severity_adjustment
        if self.analyst_payout_adjustment is not None:
            payload["analyst_payout_adjustment"] = self.analyst_payout_adjustment
        return payload


class VerificationChecklist:
    """
    Mandatory 8-item analyst checklist for finding approval.
    """

    BASE_ITEMS: list[tuple[str, str, bool]] = [
        ("Proof-of-Concept Verification", "Analyst confirms POC steps are accurate and reproducible", True),
        ("Vulnerability Existence Confirmation", "Analyst verifies vulnerability actually exists on target", True),
        ("Severity Assessment", "Analyst validates severity estimate (can adjust if needed)", True),
        ("Scope Compliance Check", "Analyst confirms finding is within authorized scope", True),
        ("Payout Estimate Review", "Analyst reviews payout estimate (can adjust if needed)", True),
        ("Report Quality Review", "Analyst reviews entire report for clarity/accuracy", True),
        ("Remediation Guidance Accuracy", "Analyst verifies remediation steps are correct", True),
        (
            "Platform-Specific Compliance",
            "Analyst confirms finding meets H1/Bugcrowd/Intigriti/direct submission requirements",
            True,
        ),
    ]

    def generate_checklist_for_finding(self, finding: dict[str, Any]) -> dict[str, Any]:
        items = [ChecklistItem(item=i, description=d, required=r).as_dict() for i, d, r in self.BASE_ITEMS]
        return {
            "finding_id": finding.get("finding_id") or finding.get("id") or "unknown",
            "vulnerability_type": finding.get("vulnerability_type", "unknown"),
            "created_at": datetime.now(UTC).isoformat(),
            "items": items,
        }

    def complete_item(
        self,
        checklist: dict[str, Any],
        item_name: str,
        *,
        analyst_notes: str,
        analyst_severity_adjustment: str | None = None,
        analyst_payout_adjustment: int | None = None,
    ) -> dict[str, Any]:
        updated = False
        for item in checklist.get("items", []):
            if str(item.get("item", "")) == item_name:
                item["completed"] = True
                item["analyst_notes"] = analyst_notes
                if analyst_severity_adjustment is not None:
                    item["analyst_severity_adjustment"] = analyst_severity_adjustment
                if analyst_payout_adjustment is not None:
                    item["analyst_payout_adjustment"] = analyst_payout_adjustment
                updated = True
                break

        if not updated:
            raise HiLValidationError(f"Checklist item not found: {item_name}")

        return checklist

    def validate_checklist_complete(self, checklist: dict[str, Any]) -> bool:
        required_items = [item for item in checklist.get("items", []) if bool(item.get("required", False))]
        missing = [item.get("item", "unknown") for item in required_items if not bool(item.get("completed", False))]
        if missing:
            raise HiLValidationError(f"Checklist incomplete. Missing: {missing}")
        return True

    def completion_summary(self, checklist: dict[str, Any]) -> dict[str, Any]:
        items = checklist.get("items", [])
        total = len(items)
        completed = sum(1 for i in items if bool(i.get("completed", False)))
        required_total = sum(1 for i in items if bool(i.get("required", False)))
        required_completed = sum(1 for i in items if bool(i.get("required", False)) and bool(i.get("completed", False)))
        return {
            "finding_id": checklist.get("finding_id"),
            "total_items": total,
            "completed_items": completed,
            "required_total": required_total,
            "required_completed": required_completed,
            "completion_percent": round((completed / total) * 100, 2) if total else 0.0,
            "required_complete": required_total == required_completed,
        }


__all__ = ["VerificationChecklist", "ChecklistItem", "HiLValidationError"]
