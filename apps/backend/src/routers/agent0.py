from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os, time, json, pathlib
import httpx
from ..core.auth import require_roles, ROLE_OPERATOR

router = APIRouter(tags=['agent0'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

# Audit log under k1/artifacts/logs if available, else local
ART_ROOT = pathlib.Path(__file__).resolve().parents[3] / 'artifacts' / 'logs'
ART_ROOT.mkdir(parents=True, exist_ok=True)

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
    (ART_ROOT / f'agent0_chat_{ts}.json').write_text(json.dumps(entry, indent=2))

    relay_url = os.getenv('AGENT_ZERO_CHAT_URL')
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
        reply = 'Agent Zero relay offline. HiL gate enforced locally. Continue via Operations.'
    return JSONResponse({'reply': reply})

@router.get('/agent0/logs')
async def agent0_logs(limit: int = 50):
    entries = []
    if ART_ROOT.exists():
        files = sorted(ART_ROOT.glob('agent0_chat_*.json'), reverse=True)[:limit]
        for f in files:
            try:
                entries.append(json.loads(f.read_text()))
            except Exception:
                pass
    return JSONResponse({'logs': entries})
