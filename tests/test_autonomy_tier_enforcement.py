from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from apps.backend.src.core.approval_request import (
    ApprovalDecisionAction,
    ApprovalRequestStatus,
    ApprovalScope,
)
from apps.backend.src.core.hil_approval_gateway import HiLApprovalGateway
from apps.backend.src.core.pre_flight_checks import (
    PreFlightCheckError,
    PreFlightContext,
    PreFlightOutcome,
    resolve_effective_tier,
    run_pre_flight_checks,
)
from apps.backend.src.core.tools import ToolAutonomyTier
from apps.backend.src.core.auth import User


@pytest.mark.asyncio
async def test_tier0_auto_allows_operator():
    result = await run_pre_flight_checks(
        PreFlightContext(
            tool_id="dummy_tier0_tool",
            params={"target": "example.com"},
            user=User(id="u-operator", roles=["operator"]),
            registered_tier=ToolAutonomyTier.TIER_0_AUTO,
        )
    )
    assert result.outcome == PreFlightOutcome.ALLOW
    assert result.requires_approval is False


@pytest.mark.asyncio
async def test_tier1_notify_allows_operator():
    result = await run_pre_flight_checks(
        PreFlightContext(
            tool_id="dummy_tier1_tool",
            params={"target": "example.com"},
            user=User(id="u-operator", roles=["operator"]),
            registered_tier=ToolAutonomyTier.TIER_1_NOTIFY,
        )
    )
    assert result.outcome == PreFlightOutcome.ALLOW
    assert result.requires_approval is False


@pytest.mark.asyncio
async def test_tier2_requires_approval_for_analyst():
    result = await run_pre_flight_checks(
        PreFlightContext(
            tool_id="dummy_tier2_tool",
            params={"target": "example.com"},
            user=User(id="u-analyst", roles=["analyst"]),
            registered_tier=ToolAutonomyTier.TIER_2_APPROVE,
        )
    )
    assert result.outcome == PreFlightOutcome.REQUIRE_APPROVAL
    assert result.requires_approval is True


@pytest.mark.asyncio
async def test_tier2_blocks_operator():
    with pytest.raises(PreFlightCheckError):
        await run_pre_flight_checks(
            PreFlightContext(
                tool_id="dummy_tier2_tool",
                params={"target": "example.com"},
                user=User(id="u-operator", roles=["operator"]),
                registered_tier=ToolAutonomyTier.TIER_2_APPROVE,
            )
        )


@pytest.mark.asyncio
async def test_tier3_blocks_without_override_even_for_admin():
    with pytest.raises(PreFlightCheckError):
        await run_pre_flight_checks(
            PreFlightContext(
                tool_id="dummy_tier3_tool",
                params={"target": "example.com"},
                user=User(id="u-admin", roles=["admin"]),
                registered_tier=ToolAutonomyTier.TIER_3_HARD_STOP,
                allow_tier3_override=False,
            )
        )


@pytest.mark.asyncio
async def test_tier3_requires_admin_override():
    result = await run_pre_flight_checks(
        PreFlightContext(
            tool_id="dummy_tier3_tool",
            params={"target": "example.com"},
            user=User(id="u-admin", roles=["admin"]),
            registered_tier=ToolAutonomyTier.TIER_3_HARD_STOP,
            allow_tier3_override=True,
        )
    )
    assert result.outcome == PreFlightOutcome.REQUIRE_APPROVAL
    assert result.requires_approval is True


def test_authorized_scope_override_for_sqlmap_is_tier3():
    resolved = resolve_effective_tier(
        "sqlmap",
        ToolAutonomyTier.TIER_1_NOTIFY,
        scope_path="config/authorized_scope.json",
    )
    assert resolved == ToolAutonomyTier.TIER_3_HARD_STOP


@pytest.mark.asyncio
async def test_approval_gateway_supports_approve_reject_defer_and_timeout():
    gateway = HiLApprovalGateway(approval_ttl_seconds=3600)

    req = await gateway.create_approval_request(
        execution_id="exec-1",
        tool_id="nuclei",
        requested_by="analyst-a",
        target="example.com",
        autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE.name,
        estimated_impact="medium",
        mission_id="mission-1",
        phase_name="recon",
        mission_goal="find exposed assets",
        scope=ApprovalScope.PHASE,
    )
    assert req.status == ApprovalRequestStatus.PENDING

    approved = await gateway.resolve_request(
        execution_id="exec-1",
        decision=ApprovalDecisionAction.APPROVE,
        decided_by="admin-a",
        reason="approved",
    )
    assert approved.status == ApprovalRequestStatus.APPROVED

    req2 = await gateway.create_approval_request(
        execution_id="exec-2",
        tool_id="sqlmap",
        requested_by="analyst-b",
        target="example.com",
        autonomy_tier=ToolAutonomyTier.TIER_3_HARD_STOP.name,
        estimated_impact="high",
    )
    rejected = await gateway.resolve_request(
        execution_id="exec-2",
        decision=ApprovalDecisionAction.REJECT,
        decided_by="admin-b",
        reason="denied",
    )
    assert rejected.status == ApprovalRequestStatus.REJECTED

    req3 = await gateway.create_approval_request(
        execution_id="exec-3",
        tool_id="nikto",
        requested_by="analyst-c",
        target="example.com",
        autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE.name,
        estimated_impact="medium",
    )
    deferred = await gateway.resolve_request(
        execution_id="exec-3",
        decision=ApprovalDecisionAction.DEFER,
        decided_by="admin-c",
        reason="need more context",
    )
    assert deferred.status == ApprovalRequestStatus.DEFERRED

    req4 = await gateway.create_approval_request(
        execution_id="exec-4",
        tool_id="nmap",
        requested_by="analyst-d",
        target="example.com",
        autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE.name,
        estimated_impact="low",
    )
    req4.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    expired_count = await gateway.expire_pending()
    assert expired_count >= 1
    assert gateway.get_request("exec-4").status == ApprovalRequestStatus.EXPIRED

    metrics = gateway.metrics_snapshot()
    assert metrics["requested_total"] >= 4
    assert metrics["approved_total"] >= 1
    assert metrics["rejected_total"] >= 1
    assert metrics["deferred_total"] >= 1
    assert metrics["expired_total"] >= 1
    assert metrics["deny_by_tool"].get("sqlmap", 0) >= 1

