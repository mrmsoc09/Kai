from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any


class ApprovalDecisionAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    DEFER = "defer"


class ApprovalRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    EXPIRED = "expired"


class ApprovalScope(str, Enum):
    TOOL = "tool"
    PHASE = "phase"


@dataclass
class ToolApprovalRequest:
    approval_id: str
    execution_id: str
    tool_id: str
    target: str
    autonomy_tier: str
    requested_by: str
    mission_id: str | None = None
    phase_name: str | None = None
    mission_goal: str | None = None
    scope: ApprovalScope = ApprovalScope.TOOL
    estimated_impact: str = "medium"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=1)
    )
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return self.expires_at <= current

    def wait_time_seconds(self, now: datetime | None = None) -> float:
        current = now or datetime.now(timezone.utc)
        return max(0.0, (current - self.created_at).total_seconds())

