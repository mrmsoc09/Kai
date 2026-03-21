from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket


CHANNEL_MISSION = "mission_events"
CHANNEL_GOVERNANCE = "governance_events"
CHANNEL_ARTIFACT = "artifact_events"
CHANNEL_SIMULATION = "simulation_events"

_CATEGORY_TO_CHANNEL = {
    "governance": CHANNEL_GOVERNANCE,
    "artifact": CHANNEL_ARTIFACT,
    "simulation": CHANNEL_SIMULATION,
}


@dataclass
class WebSocketSession:
    websocket: WebSocket
    user_id: str
    tenant_id: str | None
    roles: set[str]
    channels: set[str] = field(default_factory=set)
    mission_ids: set[str] = field(default_factory=set)


class ConnectionManager:
    def __init__(self) -> None:
        self._sessions: dict[WebSocket, WebSocketSession] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str, tenant_id: str | None, roles: set[str]) -> None:
        await websocket.accept()
        session = WebSocketSession(
            websocket=websocket,
            user_id=user_id,
            tenant_id=tenant_id,
            roles=roles,
        )
        async with self._lock:
            self._sessions[websocket] = session

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._sessions:
                del self._sessions[websocket]

    async def set_subscription(
        self,
        websocket: WebSocket,
        channel: str,
        mission_id: str | None,
        subscribe: bool,
    ) -> bool:
        async with self._lock:
            session = self._sessions.get(websocket)
            if not session:
                return False

            if subscribe:
                session.channels.add(channel)
                if mission_id:
                    session.mission_ids.add(mission_id)
            else:
                if mission_id:
                    session.mission_ids.discard(mission_id)
                if not mission_id or not session.mission_ids:
                    session.channels.discard(channel)

        return True

    async def broadcast_mission_event(self, event: dict[str, Any]) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())

        stale: list[WebSocket] = []
        for session in sessions:
            if not self._should_deliver(session, event):
                continue
            try:
                await session.websocket.send_json({"type": "mission_event", "data": event})
            except Exception:
                stale.append(session.websocket)

        for websocket in stale:
            await self.disconnect(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())

        stale: list[WebSocket] = []
        for session in sessions:
            try:
                await session.websocket.send_json(message)
            except Exception:
                stale.append(session.websocket)

        for websocket in stale:
            await self.disconnect(websocket)

    def _should_deliver(self, session: WebSocketSession, event: dict[str, Any]) -> bool:
        channel = _CATEGORY_TO_CHANNEL.get(str(event.get("category")), CHANNEL_MISSION)
        mission_id = event.get("mission_id")
        tenant_id = event.get("tenant_id")
        event_tenant = str(tenant_id) if tenant_id else None

        if not mission_id or not event_tenant:
            return False

        if session.tenant_id:
            if event_tenant != session.tenant_id:
                return False
        else:
            if mission_id not in session.mission_ids:
                return False

        if channel not in session.channels and CHANNEL_MISSION not in session.channels:
            return False

        if session.mission_ids:
            if not mission_id or mission_id not in session.mission_ids:
                return False

        return True


manager = ConnectionManager()
