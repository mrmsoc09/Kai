from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from pathlib import Path
from fastapi.responses import FileResponse
from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.recordings import list_recordings, compress_run, global_index

router = APIRouter(prefix='/recordings', tags=['recordings'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

ROOT = Path(__file__).resolve().parents[4]
ART = ROOT / 'artifacts'
RECS = ART / 'recordings'

@router.get('/{run_id}')
async def ls(run_id: str) -> Dict[str, Any]:
    paths = list_recordings(run_id)
    arch = RECS / f"{run_id}.tar.gz"
    segs = []
    for p in paths:
        from pathlib import Path as _P
        _pp = _P(p)
        if _pp.exists() and _pp.suffix.lower() in ('.mp4','.webm','.mkv'):
            segs.append({'name': _pp.name, 'size': _pp.stat().st_size})
    return {'run_id': run_id, 'segments': segs, 'archive': (str(arch) if arch.exists() else None)}

@router.post('/compress')
async def compress(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = payload.get('run_id')
    if not run_id:
        raise HTTPException(400, 'run_id required')
    rec = compress_run(run_id)
    return {'status': 'ok', 'archive': rec}

@router.get('/export/{run_id}')
async def export(run_id: str):
    arch = RECS / f"{run_id}.tar.gz"
    if not arch.exists():
        raise HTTPException(404, 'archive not found')
    return FileResponse(str(arch), media_type='application/gzip', filename=f'{run_id}.tar.gz')

@router.get('/index')
async def index() -> Dict[str, Any]:
    return {'index': global_index()}
