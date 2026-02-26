from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from ..core.ws import manager
from ..core.auth import decode_access_token, require_roles, ROLE_OPERATOR

router = APIRouter(tags=['realtime'])


@router.websocket('/ws')
async def ws(ws: WebSocket):
    # Expect JWT token via query string; reject unauthenticated sockets.
    token = ws.query_params.get('token') if hasattr(ws, 'query_params') else None
    if not token:
        try:
            await ws.close(code=1008)
        except Exception:
            pass
        return

    try:
        decode_access_token(token)
    except Exception:
        try:
            await ws.close(code=1008)
        except Exception:
            pass
        return
    await manager.connect(ws)
    try:
        while True:
            msg = await ws.receive_text()
            await manager.broadcast({'type': 'echo', 'data': msg})
    except WebSocketDisconnect:
        manager.disconnect(ws)


@router.post('/events/broadcast', dependencies=[Depends(require_roles(ROLE_OPERATOR))])
async def broadcast(event: dict):
    await manager.broadcast({'type': 'event', 'data': event})
    return {'ok': True}
