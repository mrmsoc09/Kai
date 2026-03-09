from __future__ import annotations

import pytest

from apps.backend.src.core.approval_gate_service import validate_approval_transition
from apps.backend.src.core.campaign_service import (
    validate_branch_transition,
    validate_campaign_transition,
    validate_phase_transition,
)
from apps.backend.src.core.tool_execution_service import validate_tool_transition
from apps.backend.src.models.enums import (
    ApprovalGateStatusEnum,
    BranchStatusEnum,
    CampaignStatusEnum,
    PhaseJobStatusEnum,
    ToolExecutionStatusEnum,
)


def test_campaign_transition_allows_created_to_ready():
    validate_campaign_transition(CampaignStatusEnum.CREATED, CampaignStatusEnum.READY)


def test_campaign_transition_rejects_completed_to_running():
    with pytest.raises(ValueError):
        validate_campaign_transition(CampaignStatusEnum.COMPLETED, CampaignStatusEnum.RUNNING)


def test_branch_transition_waiting_approval_to_running_is_allowed():
    validate_branch_transition(BranchStatusEnum.WAITING_APPROVAL, BranchStatusEnum.RUNNING)


def test_branch_transition_rejects_canceled_to_ready():
    with pytest.raises(ValueError):
        validate_branch_transition(BranchStatusEnum.CANCELED, BranchStatusEnum.READY)


def test_phase_transition_running_to_completed_is_allowed():
    validate_phase_transition(PhaseJobStatusEnum.RUNNING, PhaseJobStatusEnum.COMPLETED)


def test_phase_transition_queued_to_completed_is_allowed():
    validate_phase_transition(PhaseJobStatusEnum.QUEUED, PhaseJobStatusEnum.COMPLETED)


def test_phase_transition_rejects_skipped_to_running():
    with pytest.raises(ValueError):
        validate_phase_transition(PhaseJobStatusEnum.SKIPPED, PhaseJobStatusEnum.RUNNING)


def test_approval_transition_pending_to_approved_is_allowed():
    validate_approval_transition(ApprovalGateStatusEnum.PENDING, ApprovalGateStatusEnum.APPROVED)


def test_approval_transition_rejects_rejected_to_pending():
    with pytest.raises(ValueError):
        validate_approval_transition(ApprovalGateStatusEnum.REJECTED, ApprovalGateStatusEnum.PENDING)


def test_tool_transition_running_to_completed_is_allowed():
    validate_tool_transition(ToolExecutionStatusEnum.RUNNING, ToolExecutionStatusEnum.COMPLETED)


def test_tool_transition_queued_to_completed_is_allowed():
    validate_tool_transition(ToolExecutionStatusEnum.QUEUED, ToolExecutionStatusEnum.COMPLETED)


def test_tool_transition_rejects_completed_to_running():
    with pytest.raises(ValueError):
        validate_tool_transition(ToolExecutionStatusEnum.COMPLETED, ToolExecutionStatusEnum.RUNNING)
