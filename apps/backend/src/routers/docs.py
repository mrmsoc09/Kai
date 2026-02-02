from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import PlainTextResponse, JSONResponse
from pathlib import Path
from ..core.auth import require_roles, ROLE_OPERATOR

router = APIRouter(tags=['docs'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

# Compute path to k1/docs
DOCS_DIR = Path(__file__).resolve().parents[4] / 'docs'

@router.get('/docs/index')
async def docs_index():
    if not DOCS_DIR.exists():
        return []
    items = []
    for p in sorted(DOCS_DIR.glob('**/*.md')):
        rel = p.relative_to(DOCS_DIR).as_posix()
        items.append({
            'path': rel,
            'name': p.stem.replace('_', ' ').title(),
            'size': p.stat().st_size,
        })
    return items

@router.get('/docs/get', response_class=PlainTextResponse)
async def docs_get(path: str):
    file = (DOCS_DIR / path).resolve()
    if not str(file).startswith(str(DOCS_DIR.resolve())):
        raise HTTPException(status_code=400, detail='invalid path')
    if not file.exists() or not file.is_file():
        raise HTTPException(status_code=404, detail='not found')
    return file.read_text(encoding='utf-8', errors='ignore')
