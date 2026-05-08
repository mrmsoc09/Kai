from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from ..models.campaign import ToolExecution
from ..models.enums import ApprovalGateStatusEnum
from ..schemas.campaigns import ApprovalGateCreate, ApprovalGateDecision
from .approval_gate_service import ApprovalGateService
from .approval_request import (
    ApprovalDecisionAction,
    ApprovalRequestStatus,
    ApprovalScope,
    ToolApprovalRequest,
)
from .audit_events import record_transition_event
from .hil_db import get_async_session_maker


class HiLApprovalGateway:
    """Operator-facing gateway for autonomy-tier approvals."""

    def __init__(self, approval_ttl_seconds: int = 3600):
        self._ttl_seconds = max(60, int(approval_ttl_seconds))
        self._lock = Lock()
        self._requests_by_execution: dict[str, ToolApprovalRequest] = {}
        self._history: list[ToolApprovalRequest] = []
        self._metrics: dict[str, Any] = {
            "requested_total": 0,
            "approved_total": 0,
            "rejected_total": 0,
            "deferred_total": 0,
            "expired_total": 0,
            "wait_seconds_total": 0.0,
            "wait_samples": 0,
            "deny_by_tool": {},
        }

    async def _load_execution_row(self, execution_id: str) -> ToolExecution | None:
        session_maker = get_async_session_maker()
        async with session_maker() as db:
            result = await db.execute(
                select(ToolExecution)
                .where(ToolExecution.worker_task_id == execution_id)
                .order_by(ToolExecution.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def create_approval_request(
        self,
        *,
        execution_id: str,
        tool_id: str,
        requested_by: str,
        target: str,
        autonomy_tier: str,
        estimated_impact: str,
        mission_id: str | None = None,
        phase_name: str | None = None,
        mission_goal: str | None = None,
        scope: ApprovalScope = ApprovalScope.TOOL,
        metadata: dict[str, Any] | None = None,
    ) -> ToolApprovalRequest:
        existing = self.get_request(execution_id)
        if existing and existing.status in {
            ApprovalRequestStatus.PENDING,
            ApprovalRequestStatus.DEFERRED,
        }:
            return existing

        now = datetime.now(timezone.utc)
        request = ToolApprovalRequest(
            approval_id=str(uuid4()),
            execution_id=execution_id,
            tool_id=tool_id,
            target=target,
            autonomy_tier=autonomy_tier,
            requested_by=requested_by,
            mission_id=mission_id,
            phase_name=phase_name,
            mission_goal=mission_goal,
            scope=scope,
            estimated_impact=estimated_impact,
            created_at=now,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
            metadata=metadata or {},
        )

        with self._lock:
            self._requests_by_execution[execution_id] = request
            self._metrics["requested_total"] += 1

        # Best-effort: persist as ApprovalGate and link to ToolExecution row.
        try:
            session_maker = get_async_session_maker()
            async with session_maker() as db:
                row = await self._load_execution_row(execution_id)
                if row is not None:
                    service = ApprovalGateService(db)
                    gate = await service.create_gate(
                        ApprovalGateCreate(
                            campaign_id=row.campaign_id,
                            branch_id=row.branch_id,
                            phase_job_id=row.phase_job_id if scope == ApprovalScope.PHASE else None,
                            intention_id=row.intention_id,
                            gate_reason=(
                                f"Autonomy approval required for tool '{tool_id}' "
                                f"(tier={autonomy_tier}, scope={scope.value})"
                            ),
                            policy_basis="autonomy_tier_enforcement",
                            requested_by=requested_by,
                            expires_at=request.expires_at,
                            operator_notes=f"target={target}; impact={estimated_impact}",
                            decision_payload_json={"autonomy_request": asdict(request)},
                        ),
                        actor=requested_by,
                    )
                    row.approval_gate_id = gate.id
                    await record_transition_event(
                        db,
                        event_type="tool_autonomy.approval.requested",
                        actor=requested_by,
                        message=f"Approval requested for {tool_id}",
                        campaign_id=row.campaign_id,
                        branch_id=row.branch_id,
                        phase_job_id=row.phase_job_id,
                        tool_execution_id=row.id,
                        approval_gate_id=gate.id,
                        intention_id=row.intention_id,
                        payload={
                            "execution_id": execution_id,
                            "tool_id": tool_id,
                            "autonomy_tier": autonomy_tier,
                            "scope": scope.value,
                            "target": target,
                            "estimated_impact": estimated_impact,
                            "mission_id": mission_id,
                            "phase_name": phase_name,
                            "mission_goal": mission_goal,
                        },
                    )
                    await db.commit()
        except Exception:
            # Keep runtime operable even when DB is unavailable.
            pass

        return request

    def get_request(self, execution_id: str) -> ToolApprovalRequest | None:
        with self._lock:
            req = self._requests_by_execution.get(execution_id)
            if req is None:
                return None
            if req.is_expired() and req.status in {
                ApprovalRequestStatus.PENDING,
                ApprovalRequestStatus.DEFERRED,
            }:
                req.status = ApprovalRequestStatus.EXPIRED
                req.decided_at = datetime.now(timezone.utc)
                req.decision_reason = "approval_timed_out"
                self._history.append(req)
                self._metrics["expired_total"] += 1
            return req

    async def expire_pending(self) -> int:
        expired = 0
        with self._lock:
            candidates = list(self._requests_by_execution.values())
        for req in candidates:
            if req.status not in {ApprovalRequestStatus.PENDING, ApprovalRequestStatus.DEFERRED}:
                continue
            if not req.is_expired():
                continue
            await self.resolve_request(
                execution_id=req.execution_id,
                decision=ApprovalDecisionAction.REJECT,
                decided_by="system.autonomy_timeout",
                reason="approval_timeout_auto_deny",
                mark_expired=True,
            )
            expired += 1
        return expired

    async def resolve_request(
        self,
        *,
        execution_id: str,
        decision: ApprovalDecisionAction,
        decided_by: str,
        reason: str,
        mark_expired: bool = False,
    ) -> ToolApprovalRequest:
        req = self.get_request(execution_id)
        if req is None:
            raise ValueError(f"approval request not found for execution_id={execution_id}")

        if req.status in {
            ApprovalRequestStatus.APPROVED,
            ApprovalRequestStatus.REJECTED,
            ApprovalRequestStatus.EXPIRED,
        }:
            return req

        req.decided_by = decided_by
        req.decided_at = datetime.now(timezone.utc)
        req.decision_reason = reason

        if mark_expired:
            req.status = ApprovalRequestStatus.EXPIRED
        elif decision == ApprovalDecisionAction.APPROVE:
            req.status = ApprovalRequestStatus.APPROVED
        elif decision == ApprovalDecisionAction.REJECT:
            req.status = ApprovalRequestStatus.REJECTED
        else:
            req.status = ApprovalRequestStatus.DEFERRED

        with self._lock:
            self._history.append(req)
            wait_seconds = req.wait_time_seconds(req.decided_at)
            self._metrics["wait_seconds_total"] += wait_seconds
            self._metrics["wait_samples"] += 1
            if req.status == ApprovalRequestStatus.APPROVED:
                self._metrics["approved_total"] += 1
            elif req.status == ApprovalRequestStatus.REJECTED:
                self._metrics["rejected_total"] += 1
                deny_map = self._metrics["deny_by_tool"]
                deny_map[req.tool_id] = int(deny_map.get(req.tool_id, 0)) + 1
            elif req.status == ApprovalRequestStatus.DEFERRED:
                self._metrics["deferred_total"] += 1
            elif req.status == ApprovalRequestStatus.EXPIRED:
                self._metrics["expired_total"] += 1

        # Best-effort DB synchronization.
        try:
            session_maker = get_async_session_maker()
            async with session_maker() as db:
                row = await self._load_execution_row(execution_id)
                if row is not None and row.approval_gate_id is not None:
                    service = ApprovalGateService(db)
                    gate = await service.get_gate(row.approval_gate_id)
                    if gate is not None:
                        if req.status == ApprovalRequestStatus.EXPIRED:
                            await service.expire_gate(gate, actor=decided_by, intention_id=row.intention_id)
                        else:
                            status_map = {
                                ApprovalRequestStatus.APPROVED: ApprovalGateStatusEnum.APPROVED,
                                ApprovalRequestStatus.REJECTED: ApprovalGateStatusEnum.REJECTED,
                                ApprovalRequestStatus.DEFERRED: ApprovalGateStatusEnum.DEFERRED,
                            }
                            target_status = status_map.get(req.status)
                            if target_status is not None:
                                await service.decide_gate(
                                    gate,
                                    ApprovalGateDecision(
                                        status=target_status,
                                        decided_by=decided_by,
                                        operator_notes=reason,
                                        decision_payload_json={"autonomy_request": asdict(req)},
                                    ),
                                    actor=decided_by,
                                    intention_id=row.intention_id,
                                )
                        await record_transition_event(
                            db,
                            event_type="tool_autonomy.approval.resolved",
                            actor=decided_by,
                            message=f"Approval {req.status.value} for {req.tool_id}",
                            campaign_id=row.campaign_id,
                            branch_id=row.branch_id,
                            phase_job_id=row.phase_job_id,
                            tool_execution_id=row.id,
                            approval_gate_id=row.approval_gate_id,
                            intention_id=row.intention_id,
                            payload={
                                "execution_id": req.execution_id,
                                "tool_id": req.tool_id,
                                "decision": req.status.value,
                                "reason": reason,
                                "wait_time_seconds": req.wait_time_seconds(req.decided_at),
                            },
                        )
                        await db.commit()
        except Exception:
            pass

        return req

    def pending_requests(self) -> list[ToolApprovalRequest]:
        with self._lock:
            return [
                req for req in self._requests_by_execution.values()
                if req.status in {ApprovalRequestStatus.PENDING, ApprovalRequestStatus.DEFERRED}
            ]

    def approval_history(self) -> list[ToolApprovalRequest]:
        with self._lock:
            return list(self._history)

    def metrics_snapshot(self) -> dict[str, Any]:
        with self._lock:
            metrics = dict(self._metrics)
        samples = int(metrics.get("wait_samples", 0))
        total_wait = float(metrics.get("wait_seconds_total", 0.0))
        metrics["avg_wait_seconds"] = (total_wait / samples) if samples else 0.0
        metrics["pending"] = len(self.pending_requests())
        return metrics


_GATEWAY: HiLApprovalGateway | None = None
_GATEWAY_LOCK = Lock()


def get_hil_approval_gateway() -> HiLApprovalGateway:
    global _GATEWAY
    with _GATEWAY_LOCK:
        if _GATEWAY is None:
            _GATEWAY = HiLApprovalGateway()
        return _GATEWAY


async def run_approval_timeout_sweep() -> int:
    return await get_hil_approval_gateway().expire_pending()

