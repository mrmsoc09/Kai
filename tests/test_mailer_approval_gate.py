from __future__ import annotations

import pytest
from fastapi import HTTPException

from apps.backend.src.core.hil_approval_system import ApprovalStatus, ApprovalType
from apps.backend.src.routers import mailer


class _Approval:
    def __init__(self, approval_id: str, status: ApprovalStatus, approval_type: ApprovalType):
        self.approval_id = approval_id
        self.status = status
        self.approval_type = approval_type


class _Hil:
    def __init__(self, approvals):
        self.approval_history = approvals


def test_mailer_requires_matching_approved_request(monkeypatch):
    fake = _Hil([_Approval("a-1", ApprovalStatus.APPROVED, ApprovalType.EMAIL_REPLY)])
    monkeypatch.setattr(mailer, "get_hil_system", lambda: fake)
    mailer._ensure_approval_granted("a-1", "email_reply")


def test_mailer_rejects_missing_or_wrong_approval(monkeypatch):
    fake = _Hil([_Approval("a-2", ApprovalStatus.REJECTED, ApprovalType.REPORT_SUBMISSION)])
    monkeypatch.setattr(mailer, "get_hil_system", lambda: fake)
    with pytest.raises(HTTPException):
        mailer._ensure_approval_granted("a-2", "report_submission")
    with pytest.raises(HTTPException):
        mailer._ensure_approval_granted(None, "report_submission")
