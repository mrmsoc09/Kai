from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from apps.backend.src.core.scope_resolver import is_in_scope_for_workflow_async
from apps.backend.src.models.campaign import CampaignRun, Program, ScopeTarget
from apps.backend.src.models.enums import CampaignStatusEnum
from apps.backend.src.models.workflow import WorkflowRun


@pytest.mark.asyncio
async def test_scope_resolver_uses_workflow_db_scope(monkeypatch):
    import apps.backend.src.core.scope_resolver as scope_resolver

    now = datetime.now(timezone.utc)
    program = Program(
        id=uuid4(),
        program_key=f"scope-test-{uuid4()}",
        name="Scope Test Program",
        platform="LOCAL",
        status="ACTIVE",
        created_by="tests",
        config_json={},
    )
    scope_target = ScopeTarget(
        id=uuid4(),
        program_id=program.id,
        target="*.example.com",
        target_type="domain",
        is_in_scope=True,
        details_json={},
        created_at=now,
        updated_at=now,
    )
    campaign = CampaignRun(
        id=uuid4(),
        program_id=program.id,
        primary_scope_target_id=scope_target.id,
        campaign_name=f"scope-campaign-{uuid4()}",
        initiated_by="tests",
        declared_goal="Validate workflow scope resolver behavior",
        declared_reason="tests",
        policy_basis="TEST",
        approval_required=False,
        status=CampaignStatusEnum.RUNNING,
        run_config_json={},
        created_at=now,
        updated_at=now,
    )
    workflow = WorkflowRun(
        id=uuid4(),
        campaign_run_id=campaign.id,
        scope_target_id=scope_target.id,
        template_name="workflow_recon_surface_map",
        target="api.example.com",
        trigger_source="TEST",
        created_at=now,
        updated_at=now,
    )

    class _ScalarResult:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

        def scalars(self):
            return self

        def all(self):
            if self._value is None:
                return []
            if isinstance(self._value, list):
                return self._value
            return [self._value]

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, stmt):
            entity = stmt.column_descriptions[0]["entity"]
            if entity is WorkflowRun:
                return _ScalarResult(workflow)
            if entity is CampaignRun:
                return _ScalarResult(campaign)
            if entity is ScopeTarget:
                return _ScalarResult([scope_target])
            return _ScalarResult(None)

    monkeypatch.setattr(
        scope_resolver,
        "get_async_session_maker",
        lambda: (lambda: _FakeSession()),
    )

    assert await is_in_scope_for_workflow_async("api.example.com", workflow_id=str(workflow.id)) is True
    assert await is_in_scope_for_workflow_async("evil.com", workflow_id=str(workflow.id)) is False
