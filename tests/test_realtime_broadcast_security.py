from __future__ import annotations

from uuid import uuid4

from apps.backend.src.core.auth import ROLE_ADMIN, ROLE_OPERATOR, create_access_token


class _RuntimeStub:
    def __init__(self, mission_to_tenant: dict[str, str]) -> None:
        self._mission_to_tenant = mission_to_tenant

    def tenant_for_mission(self, mission_id: str):
        return self._mission_to_tenant.get(mission_id)


def _auth_header(*, roles: list[str], tenant_id: str | None) -> dict[str, str]:
    token = create_access_token(
        subject=str(uuid4()),
        roles=roles,
        tenant_id=tenant_id,
    )
    return {"Authorization": f"Bearer {token}"}


def test_broadcast_endpoint_requires_admin_role(client, monkeypatch):
    import apps.backend.src.routers.realtime as realtime_router

    tenant_id = str(uuid4())
    monkeypatch.setattr(
        realtime_router,
        "get_mission_runtime",
        lambda: _RuntimeStub({"mission-1": tenant_id}),
    )
    headers = _auth_header(roles=[ROLE_OPERATOR], tenant_id=tenant_id)
    response = client.post(
        "/events/broadcast",
        json={"mission_id": "mission-1", "event_type": "manual_test"},
        headers=headers,
    )

    assert response.status_code == 403


def test_broadcast_endpoint_enforces_mission_tenant_scope(client, monkeypatch):
    import apps.backend.src.routers.realtime as realtime_router

    tenant_a = str(uuid4())
    tenant_b = str(uuid4())
    monkeypatch.setattr(
        realtime_router,
        "get_mission_runtime",
        lambda: _RuntimeStub({"mission-2": tenant_b}),
    )
    headers = _auth_header(roles=[ROLE_ADMIN], tenant_id=tenant_a)
    response = client.post(
        "/events/broadcast",
        json={"mission_id": "mission-2", "event_type": "manual_test"},
        headers=headers,
    )

    assert response.status_code == 403


def test_broadcast_endpoint_rejects_unknown_mission(client, monkeypatch):
    import apps.backend.src.routers.realtime as realtime_router

    tenant_id = str(uuid4())
    monkeypatch.setattr(
        realtime_router,
        "get_mission_runtime",
        lambda: _RuntimeStub({}),
    )
    headers = _auth_header(roles=[ROLE_ADMIN], tenant_id=tenant_id)
    response = client.post(
        "/events/broadcast",
        json={"mission_id": "missing-mission", "event_type": "manual_test"},
        headers=headers,
    )

    assert response.status_code == 404
