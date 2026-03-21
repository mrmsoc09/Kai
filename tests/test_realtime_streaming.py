from __future__ import annotations

import asyncio
from uuid import uuid4

from apps.backend.src.core.praison_execution_events import MissionEvent, mission_started_event, node_entered_event
from apps.backend.src.core.realtime_events import normalize_mission_event
from apps.backend.src.core.ws import CHANNEL_MISSION, ConnectionManager


class _FakeRuntime:
    def __init__(self, mission_id: str, tenant_id: str) -> None:
        self._mission_id = mission_id
        self._tenant_id = tenant_id

    def tenant_for_mission(self, mission_id: str):
        if mission_id == self._mission_id:
            return self._tenant_id
        return None


class _FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def accept(self) -> None:
        return None

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)


def test_normalize_mission_event_contract(monkeypatch):
    mission_id = "m-100"
    tenant_id = uuid4()
    runtime = _FakeRuntime(mission_id=mission_id, tenant_id=tenant_id)
    monkeypatch.setattr(
        "apps.backend.src.core.realtime_events._resolve_tenant_for_mission",
        lambda value: str(runtime.tenant_for_mission(value)) if runtime.tenant_for_mission(value) else None,
    )

    event = mission_started_event(mission_id=mission_id, workflow_id="wf-1", program_id="prog-1")
    payload = normalize_mission_event(event)

    assert payload is not None
    assert payload["schema_version"] == "1.0"
    assert payload["event_type"] == "mission_started"
    assert payload["category"] == "lifecycle"
    assert payload["status"] == "running"
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["mission_id"] == mission_id


def test_connection_manager_filters_by_tenant_and_mission():
    async def _run():
        manager = ConnectionManager()
        ws_tenant_a = _FakeWebSocket()
        ws_tenant_b = _FakeWebSocket()

        await manager.connect(ws_tenant_a, user_id="user-a", tenant_id="tenant-a", roles={"viewer"})
        await manager.connect(ws_tenant_b, user_id="user-b", tenant_id="tenant-b", roles={"viewer"})

        await manager.set_subscription(ws_tenant_a, CHANNEL_MISSION, "mission-1", True)
        await manager.set_subscription(ws_tenant_b, CHANNEL_MISSION, "mission-1", True)

        event_for_tenant_a = {
            "event_id": "evt-1",
            "mission_id": "mission-1",
            "tenant_id": "tenant-a",
            "category": "lifecycle",
            "event_type": "mission_started",
            "timestamp": "2026-03-18T00:00:00Z",
        }
        await manager.broadcast_mission_event(event_for_tenant_a)

        assert len(ws_tenant_a.messages) == 1
        assert len(ws_tenant_b.messages) == 0

        event_other_mission = {
            "event_id": "evt-2",
            "mission_id": "mission-2",
            "tenant_id": "tenant-a",
            "category": "lifecycle",
            "event_type": "mission_started",
            "timestamp": "2026-03-18T00:00:01Z",
        }
        await manager.broadcast_mission_event(event_other_mission)

        assert len(ws_tenant_a.messages) == 1

    asyncio.run(_run())


def test_normalize_node_event(monkeypatch):
    mission_id = "m-200"
    tenant_id = uuid4()
    runtime = _FakeRuntime(mission_id=mission_id, tenant_id=tenant_id)
    monkeypatch.setattr(
        "apps.backend.src.core.realtime_events._resolve_tenant_for_mission",
        lambda value: str(runtime.tenant_for_mission(value)) if runtime.tenant_for_mission(value) else None,
    )

    event = node_entered_event(
        mission_id=mission_id,
        workflow_id="wf-2",
        program_id="prog-2",
        node_id="recon_node",
    )
    payload = normalize_mission_event(event)

    assert payload is not None
    assert payload["category"] == "node"
    assert payload["status"] == "running"
    assert payload["node_id"] == "recon_node"


def test_normalize_simulation_event_category(monkeypatch):
    mission_id = "m-300"
    tenant_id = uuid4()
    runtime = _FakeRuntime(mission_id=mission_id, tenant_id=tenant_id)
    monkeypatch.setattr(
        "apps.backend.src.core.realtime_events._resolve_tenant_for_mission",
        lambda value: str(runtime.tenant_for_mission(value)) if runtime.tenant_for_mission(value) else None,
    )

    event = MissionEvent(
        event_type="simulation_started",
        mission_id=mission_id,
        workflow_id="wf-3",
        program_id="prog-3",
    )
    payload = normalize_mission_event(event)

    assert payload is not None
    assert payload["category"] == "simulation"
    assert payload["status"] == "running"
