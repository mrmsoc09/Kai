from __future__ import annotations

import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from ..core.auth import get_current_user, User, require_roles, ROLE_ANALYST
from ..core.models import Evidence

router = APIRouter(prefix='/evidence', tags=['evidence'])
ROOT = Path(__file__).resolve().parents[4]
EV_BASE = ROOT / 'artifacts' / 'evidence'
EV_BASE.mkdir(parents=True, exist_ok=True)

def _ev_path(eid: str) -> Path:
    return EV_BASE / f"{eid}.json"

@router.post('/register', response_model=Evidence, dependencies=[Depends(require_roles(ROLE_ANALYST))])
def register(ev: Evidence, user: User = Depends(get_current_user)):
    p = _ev_path(ev.id)
    if p.exists():
        # Prevent overwriting finalized entries
        existing = Evidence(**json.loads(p.read_text()))
        if existing.finalized:
            raise HTTPException(status_code=409, detail='immutable')
    p.write_text(ev.model_dump_json())
    return ev

@router.post('/finalize')
def finalize(payload: dict, user: User = Depends(require_roles(ROLE_ANALYST))):
    eid = payload.get('id')
    if not eid:
        raise HTTPException(status_code=400, detail='id_required')
    p = _ev_path(eid)
    if not p.exists():
        raise HTTPException(status_code=404, detail='not_found')
    data = json.loads(p.read_text())
    if data.get('finalized'):
        return {'ok': True, 'id': eid, 'finalized': True}
    data['finalized'] = True
    p.write_text(json.dumps(data))
    return {'ok': True, 'id': eid, 'finalized': True}

@router.post('/update')
def update(payload: dict, user: User = Depends(require_roles(ROLE_ANALYST))):
    eid = payload.get('id')
    if not eid:
        raise HTTPException(status_code=400, detail='id_required')
    p = _ev_path(eid)
    if not p.exists():
        raise HTTPException(status_code=404, detail='not_found')
    data = json.loads(p.read_text())
    if data.get('finalized'):
        return JSONResponse(status_code=409, content={'status':'blocked','reason':'immutable'})
    # merge shallow
    for k, v in payload.items():
        if k != 'id':
            data[k] = v
    p.write_text(json.dumps(data))
    return {'ok': True, 'id': eid}
