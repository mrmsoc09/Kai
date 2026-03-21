from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..core.auth import (
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    User,
    decode_access_token,
    require_roles,
)
from ..core.praison_mission_runtime import get_mission_runtime
from ..core.realtime_events import recent_mission_events, start_realtime_event_bridge
from ..core.ws import (
    CHANNEL_ARTIFACT,
    CHANNEL_GOVERNANCE,
    CHANNEL_MISSION,
    CHANNEL_SIMULATION,
    manager,
)

router = APIRouter(tags=["realtime"])

CHANNEL_ROLE_REQUIREMENTS: dict[str, set[str]] = {
    CHANNEL_MISSION: {ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN},
    CHANNEL_ARTIFACT: {ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN},
    CHANNEL_GOVERNANCE: {ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN},
    CHANNEL_SIMULATION: {ROLE_ANALYST, ROLE_ADMIN},
}


class SubscriptionMessage(BaseModel):
    action: str
    channel: str = CHANNEL_MISSION
    mission_id: str | None = None


def _coerce_subscription_message(payload: dict[str, Any]) -> SubscriptionMessage:
    mission_id = payload.get("mission_id")
    if mission_id is None:
        mission_id = payload.get("missionId")
    return SubscriptionMessage(
        action=str(payload.get("action", "")),
        channel=str(payload.get("channel", CHANNEL_MISSION)),
        mission_id=str(mission_id) if mission_id else None,
    )


def _has_channel_permission(user: User, channel: str) -> bool:
    required = CHANNEL_ROLE_REQUIREMENTS.get(channel)
    if not required:
        return False
    return any(role in required for role in user.roles)


def _validate_mission_access(user: User, mission_id: str) -> None:
    runtime = get_mission_runtime()
    tenant_id = runtime.tenant_for_mission(mission_id)
    if not tenant_id:
        raise HTTPException(status_code=404, detail="mission_not_found")
    if user.tenant_id and str(tenant_id) != user.tenant_id:
        raise HTTPException(status_code=403, detail="mission_out_of_scope")


class BroadcastEventRequest(BaseModel):
    mission_id: str
    event_type: str = "manual_broadcast"
    category: str = "operation"
    status: str | None = None
    summary: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    node_id: str | None = None
    phase: str | None = None
    workflow_id: str | None = None
    artifact_id: str | None = None
    approval_id: str | None = None
    timestamp: str | None = None


@router.on_event("startup")
async def _start_realtime_bridge() -> None:
    start_realtime_event_bridge()


@router.websocket("/ws")
async def ws(websocket: WebSocket):
    token = websocket.query_params.get("token") if hasattr(websocket, "query_params") else None
    if not token:
        await websocket.close(code=1008)
        return

    try:
        user = decode_access_token(token)
    except Exception:
        await websocket.close(code=1008)
        return

    await manager.connect(
        websocket=websocket,
        user_id=user.id,
        tenant_id=user.tenant_id,
        roles=set(user.roles),
    )
    await websocket.send_json({"type": "connected", "data": {"user_id": user.id, "tenant_id": user.tenant_id}})

    try:
        while True:
            raw_message = await websocket.receive_text()

            try:
                payload = json.loads(raw_message)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "data": {"message": "invalid_json"}})
                continue

            message = _coerce_subscription_message(payload)

            if message.action == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if message.channel not in CHANNEL_ROLE_REQUIREMENTS:
                await websocket.send_json({"type": "error", "data": {"message": "unknown_channel"}})
                continue

            if not _has_channel_permission(user, message.channel):
                await websocket.send_json({"type": "error", "data": {"message": "forbidden_channel"}})
                continue

            if message.mission_id:
                try:
                    _validate_mission_access(user, message.mission_id)
                except HTTPException:
                    await websocket.send_json({"type": "error", "data": {"message": "mission_out_of_scope"}})
                    continue
            elif message.channel == CHANNEL_MISSION and not user.tenant_id:
                await websocket.send_json({"type": "error", "data": {"message": "mission_id_required"}})
                continue

            if message.action == "subscribe":
                ok = await manager.set_subscription(
                    websocket=websocket,
                    channel=message.channel,
                    mission_id=message.mission_id,
                    subscribe=True,
                )
                if ok:
                    await websocket.send_json(
                        {
                            "type": "subscribed",
                            "data": {"channel": message.channel, "mission_id": message.mission_id},
                        }
                    )
                continue

            if message.action == "unsubscribe":
                ok = await manager.set_subscription(
                    websocket=websocket,
                    channel=message.channel,
                    mission_id=message.mission_id,
                    subscribe=False,
                )
                if ok:
                    await websocket.send_json(
                        {
                            "type": "unsubscribed",
                            "data": {"channel": message.channel, "mission_id": message.mission_id},
                        }
                    )
                continue

            await websocket.send_json({"type": "error", "data": {"message": "unsupported_action"}})
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)
        await websocket.close(code=1011)


@router.get(
    "/realtime/missions/{mission_id}/recent",
    dependencies=[Depends(require_roles(ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN))],
)
async def get_recent_mission_events(
    mission_id: str,
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(require_roles(ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    _validate_mission_access(user, mission_id)
    return {
        "mission_id": mission_id,
        "events": recent_mission_events(mission_id=mission_id, limit=limit),
    }


@router.post("/events/broadcast", dependencies=[Depends(require_roles(ROLE_ADMIN))])
async def broadcast(
    payload: BroadcastEventRequest,
    user: User = Depends(require_roles(ROLE_ADMIN)),
):
    _validate_mission_access(user, payload.mission_id)
    runtime = get_mission_runtime()
    tenant_id = runtime.tenant_for_mission(payload.mission_id)
    if not tenant_id:
        raise HTTPException(status_code=404, detail="mission_not_found")

    event = {
        "schema_version": "1.0",
        "event_id": f"manual:{payload.mission_id}:{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        "event_type": payload.event_type,
        "timestamp": payload.timestamp or datetime.now(timezone.utc).isoformat(),
        "tenant_id": str(tenant_id),
        "mission_id": payload.mission_id,
        "workflow_id": payload.workflow_id or f"manual:{payload.mission_id}",
        "program_id": "manual",
        "node_id": payload.node_id,
        "phase": payload.phase,
        "status": payload.status,
        "summary": payload.summary or payload.event_type.replace("_", " "),
        "detail": payload.detail,
        "artifact_id": payload.artifact_id,
        "approval_id": payload.approval_id,
        "category": payload.category,
    }
    await manager.broadcast_mission_event(event)
    return {"ok": True}
