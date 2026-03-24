from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from apps.backend.src.auth.dependencies import CurrentUser
from apps.backend.src.routers import artifacts as artifacts_router
from apps.backend.src.routers import events as events_router


class _RuntimeStub:
    def __init__(self, tenant_id: str | None) -> None:
        self._tenant_id = tenant_id

    def tenant_for_mission(self, mission_id: str):
        del mission_id
        return self._tenant_id

def test_artifact_mission_guard_blocks_cross_tenant_access(monkeypatch):
    user = CurrentUser(
        id=uuid4(),
        tenant_id=uuid4(),
        username="u1",
        email="u1@example.com",
        full_name="User One",
        is_active=True,
        is_superuser=False,
        must_change_password=False,
        role="operator",
    )
    other_tenant = uuid4()
    monkeypatch.setattr(artifacts_router, "get_mission_runtime", lambda: _RuntimeStub(other_tenant))

    with pytest.raises(HTTPException) as exc_info:
        artifacts_router._enforce_mission_tenant_access(user, uuid4())

    assert exc_info.value.status_code == 403


def test_event_mission_guard_blocks_cross_tenant_access(monkeypatch):
    user = CurrentUser(
        id=uuid4(),
        tenant_id=uuid4(),
        username="u2",
        email="u2@example.com",
        full_name="User Two",
        is_active=True,
        is_superuser=False,
        must_change_password=False,
        role="operator",
    )
    other_tenant = uuid4()
    monkeypatch.setattr(events_router, "get_mission_runtime", lambda: _RuntimeStub(other_tenant))

    with pytest.raises(HTTPException) as exc_info:
        events_router._enforce_mission_tenant_access(user, uuid4())

    assert exc_info.value.status_code == 403


def test_mission_guard_allows_when_runtime_has_no_mapping(monkeypatch):
    user = CurrentUser(
        id=uuid4(),
        tenant_id=uuid4(),
        username="u3",
        email="u3@example.com",
        full_name="User Three",
        is_active=True,
        is_superuser=False,
        must_change_password=False,
        role="operator",
    )
    monkeypatch.setattr(events_router, "get_mission_runtime", lambda: _RuntimeStub(None))
    monkeypatch.setattr(artifacts_router, "get_mission_runtime", lambda: _RuntimeStub(None))

    events_router._enforce_mission_tenant_access(user, uuid4())
    artifacts_router._enforce_mission_tenant_access(user, uuid4())
