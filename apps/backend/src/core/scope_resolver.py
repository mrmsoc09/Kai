"""
Canonical Scope Resolver

Legacy compatibility wrapper that now delegates to scope_guardrails so
tool authorization and workflow planning share one policy authority.
"""

from __future__ import annotations

import asyncio
from typing import Optional
from uuid import UUID

from sqlalchemy import select

from ..models.campaign import CampaignRun, ScopeTarget
from ..models.workflow import WorkflowRun
from .hil_db import get_async_session_maker
from .scope_guardrails import ScopePolicy, evaluate_target_scope, load_scope_policy


def _coerce_uuid(value: str | UUID) -> UUID | None:
    if isinstance(value, UUID):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return UUID(text)
    except ValueError:
        return None


async def _load_workflow_scope_policy(workflow_id: str | UUID) -> ScopePolicy | None:
    workflow_uuid = _coerce_uuid(workflow_id)
    if workflow_uuid is None:
        return None

    session_maker = get_async_session_maker()
    async with session_maker() as db:
        result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == workflow_uuid))
        workflow_run = result.scalar_one_or_none()
        if workflow_run is None:
            return None

        result = await db.execute(
            select(CampaignRun).where(CampaignRun.id == workflow_run.campaign_run_id)
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            return None

        result = await db.execute(
            select(ScopeTarget).where(ScopeTarget.program_id == campaign.program_id)
        )
        scope_targets = result.scalars().all()
        if not scope_targets:
            return None

    base_policy = load_scope_policy()
    allowlist = [
        str(item.target).strip()
        for item in scope_targets
        if item.is_in_scope and str(item.target).strip()
    ]
    denylist = [
        str(item.target).strip()
        for item in scope_targets
        if not item.is_in_scope and str(item.target).strip()
    ]
    if not allowlist and not denylist:
        return None
    return ScopePolicy(
        allowlist=allowlist,
        denylist=denylist,
        cidr_allowlist=list(base_policy.cidr_allowlist),
        safe_mode_default=base_policy.safe_mode_default,
        strict_allowlist=bool(allowlist),
    )


async def is_in_scope_for_workflow_async(target: str, workflow_id: Optional[str] = None) -> bool:
    policy = load_scope_policy()
    if workflow_id:
        try:
            dynamic_policy = await _load_workflow_scope_policy(workflow_id)
        except Exception:
            dynamic_policy = None
        if dynamic_policy is not None:
            policy = dynamic_policy
    decision = evaluate_target_scope(target, policy)
    return decision.allowed


def is_in_scope_for_workflow(target: str, workflow_id: Optional[str] = None) -> bool:
    """Compatibility helper with DB-backed workflow scope when workflow_id is provided."""
    if not workflow_id:
        policy = load_scope_policy()
        decision = evaluate_target_scope(target, policy)
        return decision.allowed
    try:
        return asyncio.run(is_in_scope_for_workflow_async(target, workflow_id=workflow_id))
    except RuntimeError:
        # If running inside an event loop, avoid nested loop errors and fall back
        # to canonical baseline policy.
        policy = load_scope_policy()
        decision = evaluate_target_scope(target, policy)
        return decision.allowed


def get_scope_context(target: str, workflow_id: Optional[str] = None) -> dict:
    """Return scope context for audit/debugging with canonical scope policy evaluation."""
    source = "scope_guardrails"
    policy = load_scope_policy()
    if workflow_id:
        try:
            dynamic_policy = asyncio.run(_load_workflow_scope_policy(workflow_id))
        except RuntimeError:
            dynamic_policy = None
        except Exception:
            dynamic_policy = None
        if dynamic_policy is not None:
            policy = dynamic_policy
            source = "workflow_db_scope"
    decision = evaluate_target_scope(target, policy)
    return {
        "in_scope": decision.allowed,
        "source": source,
        "workflow_id": workflow_id,
        "host": decision.normalized_host,
        "reason": decision.reason,
        "matched_rule": decision.matched_rule,
    }
