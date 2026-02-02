from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Set
import os, time, json, pathlib, asyncio, contextlib
import httpx

router = APIRouter()

ARTIFACTS_DIR = pathlib.Path(__file__).resolve().parents[3] / 'artifacts' / 'logs'
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

class ChatIn(BaseModel):
    text: str

class StateOut(BaseModel):
    api: str
    vector: str
    postgres: str
    thehive: str

# Simple in-proc websocket manager
class WSManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)
    def disconnect(self, ws: WebSocket):
        with contextlib.suppress(KeyError):
            self.active.remove(ws)
    async def broadcast(self, msg: dict):
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

ws_manager = WSManager()

@router.post('/agent0/chat')
async def agent0_chat(payload: ChatIn, request: Request):
    # Audit inbound HiL message
    ts = int(time.time()*1000)
    entry = {
        'ts': ts,
        'source': 'frontend',
        'path': '/agent0/chat',
        'text': payload.text,
        'client': request.client.host if request.client else 'unknown',
    }
    (ARTIFACTS_DIR / f'agent0_chat_{ts}.json').write_text(json.dumps(entry, indent=2))
    # Attempt to relay to actual Agent Zero if configured
    relay_url = os.getenv('AGENT_ZERO_CHAT_URL')  # e.g., http://localhost:9000/agent0/chat
    reply = None
    if relay_url:
        try:
            async with httpx.AsyncClient(timeout=5) as cli:
                r = await cli.post(relay_url, json={'text': payload.text})
                if r.status_code == 200:
                    j = r.json()
                    reply = j.get('reply') or j.get('text') or 'Acknowledged.'
        except Exception:
            reply = None
    if reply is None:
        reply = 'Agent Zero relay offline. HiL gate remains enforced. Proceed via Operations and request approval.'
    # Broadcast event
    await ws_manager.broadcast({'type':'agent0.chat', 'ts': ts, 'text': payload.text, 'reply': reply})
    return JSONResponse({'reply': reply})

@router.get('/state', response_model=StateOut)
async def state():
    # Cheap status probes with short timeouts
    api = 'OK'
    vector = '...'
    postgres = '...'
    thehive = '...'

    # Vector: prefer QDRANT_URL ping
    qdrant = os.getenv('QDRANT_URL')
    if qdrant:
        try:
            async with httpx.AsyncClient(timeout=2) as cli:
                r = await cli.get(qdrant + '/ports')
                vector = 'OK' if r.status_code < 500 else '...'
        except Exception:
            vector = '...'
    elif os.getenv('DATABASE_URL'):
        # pgvector via Postgres presence (no connection here to avoid blocking)
        vector = 'OK'

    # Postgres quick probe via HTTP proxy if provided, else env presence
    if os.getenv('DATABASE_URL'):
        postgres = 'OK'

    # TheHive quick probe
    hive = os.getenv('THEHIVE_URL')
    if hive:
        try:
            async with httpx.AsyncClient(timeout=2) as cli:
                r = await cli.get(hive + '/api/status')
                thehive = 'OK' if r.status_code < 500 else '...'
        except Exception:
            thehive = '...'

    return StateOut(api=api, vector=vector, postgres=postgres, thehive=thehive)

@router.websocket('/ws')
async def ws(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            # Keepalive/read to detect disconnect; echo pings
            with contextlib.suppress(Exception):
                msg = await ws.receive_text()
                await ws.send_text(msg)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
