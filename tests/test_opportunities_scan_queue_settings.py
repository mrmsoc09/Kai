from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from apps.backend.src.auth.models import UserScanQueueSettings
from apps.backend.src.core.auth import ROLE_ANALYST, User
from apps.backend.src.routers import opportunities as opportunities_router


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _DbStub:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []
        self.committed = False
        self.refreshed = False

    async def execute(self, _statement):
        return _ScalarResult(self.existing)

    def add(self, value):
        self.added.append(value)
        self.existing = value

    async def commit(self):
        self.committed = True

    async def refresh(self, _value):
        self.refreshed = True


def _user(*, tenant_id: str | None = None, user_id: str | None = None) -> User:
    return User(
        id=user_id or str(uuid4()),
        roles=[ROLE_ANALYST],
        tenant_id=tenant_id if tenant_id is not None else str(uuid4()),
    )


def test_scan_queue_owner_ids_requires_tenant_context() -> None:
    with pytest.raises(HTTPException) as exc_info:
        opportunities_router._scan_queue_owner_ids(_user(tenant_id=""))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "tenant_context_required"


def test_scan_queue_owner_ids_rejects_non_uuid_identity() -> None:
    with pytest.raises(HTTPException) as exc_info:
        opportunities_router._scan_queue_owner_ids(_user(user_id="dev-subject"))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "invalid_auth_identity"


def test_validated_scan_queue_bounds_rejects_min_greater_than_max() -> None:
    payload = opportunities_router.ScanQueueSettingsUpdateRequest(min_concurrent=5, max_concurrent=3)
    with pytest.raises(HTTPException) as exc_info:
        opportunities_router._validated_scan_queue_bounds(payload)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "scan_queue_min_exceeds_max"


@pytest.mark.asyncio
async def test_get_scan_queue_settings_returns_defaults_when_not_persisted() -> None:
    db = _DbStub(existing=None)
    response = await opportunities_router.get_scan_queue_settings(current_user=_user(), db=db)
    assert response.min_concurrent == opportunities_router.SCAN_QUEUE_DEFAULT_MIN
    assert response.max_concurrent == opportunities_router.SCAN_QUEUE_DEFAULT_MAX


@pytest.mark.asyncio
async def test_update_scan_queue_settings_creates_new_record() -> None:
    user = _user()
    db = _DbStub(existing=None)
    payload = opportunities_router.ScanQueueSettingsUpdateRequest(min_concurrent=2, max_concurrent=4)

    response = await opportunities_router.update_scan_queue_settings(payload, current_user=user, db=db)

    assert response.min_concurrent == 2
    assert response.max_concurrent == 4
    assert db.committed is True
    assert db.refreshed is True
    assert len(db.added) == 1
    assert isinstance(db.added[0], UserScanQueueSettings)


@pytest.mark.asyncio
async def test_update_scan_queue_settings_updates_existing_record() -> None:
    tenant_id = uuid4()
    user_id = uuid4()
    existing = UserScanQueueSettings(
        user_id=user_id,
        tenant_id=tenant_id,
        min_concurrent=1,
        max_concurrent=3,
    )
    db = _DbStub(existing=existing)
    user = User(id=str(user_id), roles=[ROLE_ANALYST], tenant_id=str(tenant_id))
    payload = opportunities_router.ScanQueueSettingsUpdateRequest(min_concurrent=3, max_concurrent=6)

    response = await opportunities_router.update_scan_queue_settings(payload, current_user=user, db=db)

    assert response.min_concurrent == 3
    assert response.max_concurrent == 6
    assert existing.min_concurrent == 3
    assert existing.max_concurrent == 6
    assert db.committed is True
    assert db.refreshed is True
