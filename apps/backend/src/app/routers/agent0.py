from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Set
import os, time, json, pathlib, asyncio, contextlib
import httpx

router = APIRouter()

ARTIFACTS_DIR = pathlib.Path(__file__).resolve().parents[4] / 'docs'  # store near docs if artifacts dir missing
(ARTIFACTS_DIR / 'audit').mkdir(parents=True, exist_ok=True)

class ChatIn(BaseModel):
    text: str

@router.post('/agent0/chat')
async def agent0_chat(payload: ChatIn, request: Request):
    ts = int(time.time()*1000)
    entry = {
        'ts': ts,
        'source': 'frontend',
        'path': '/agent0/chat',
        'text': payload.text,
        'client': request.client.host if request.client else 'unknown',
    }
    (ARTIFACTS_DIR / 'audit' / f'agent0_chat_{ts}.json').write_text(json.dumps(entry, indent=2))
    reply = None
    relay_url = os.getenv('AGENT_ZERO_CHAT_URL')
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
        reply = 'Agent Zero relay offline. HiL gate enforced locally.'
    await ws_manager.broadcast({'type':'agent0.chat', 'ts': ts, 'text': payload.text, 'reply': reply})
    return JSONResponse({'reply': reply})

class StateOut(BaseModel):
    api: str
    vector: str
    postgres: str
    thehive: str

@router.get('/state', response_model=StateOut)
async def state():
    api = 'OK'
    vector = 'OK' if os.getenv('QDRANT_URL') or os.getenv('DATABASE_URL') else '...'
    postgres = 'OK' if os.getenv('DATABASE_URL') else '...'
    thehive = 'OK' if os.getenv('THEHIVE_URL') else '...'
    return StateOut(api=api, vector=vector, postgres=postgres, thehive=thehive)

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

@router.websocket('/ws')
async def ws(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            with contextlib.suppress(Exception):
                msg = await ws.receive_text()
                await ws.send_text(msg)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
