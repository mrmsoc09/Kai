from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from pathlib import Path
import json, time
from ..core.auth import require_roles, ROLE_OPERATOR

router = APIRouter(prefix='/programs', tags=['programs'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

ROOT = Path(__file__).resolve().parents[4]
PROG_DIR = ROOT / 'artifacts' / 'programs'
PROG_DIR.mkdir(parents=True, exist_ok=True)

@router.post('/ingest_vrp')
async def ingest_vrp(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Plan-only: accept pasted JSON/fields for Google VRP or others; no network fetch
    data = payload.get('data') or {}
    name = data.get('name') or payload.get('name') or 'program'
    slug = (payload.get('slug') or name.lower().replace(' ', '-'))
    program = {
        'slug': slug,
        'name': name,
        'platform': data.get('platform', 'google_vrp'),
        'policy_url': data.get('policy_url'),
        'scope': data.get('scope') or [],
        'rules': data.get('rules') or {},
        'ingested_at': int(time.time())
    }
    outdir = PROG_DIR / slug
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / 'program.json').write_text(json.dumps(program, indent=2))
    return {'ok': True, 'slug': slug, 'path': str(outdir / 'program.json')}

@router.get('/list')
async def list_programs() -> Dict[str, Any]:
    out = []
    for p in PROG_DIR.glob('*/program.json'):
        try:
            out.append(json.loads(p.read_text()))
        except Exception:
            pass
    return {'programs': out}

@router.get('/get/{slug}')
async def get_program(slug: str) -> Dict[str, Any]:
    p = PROG_DIR / slug / 'program.json'
    if not p.exists():
        raise HTTPException(404, 'program not found')
    return json.loads(p.read_text())


from fastapi.responses import FileResponse

# Knowledge artifacts (Top-50 BBP)
KNOWLEDGE_DIR = ROOT / 'artifacts' / 'knowledge'
CANON_JSONL = KNOWLEDGE_DIR / 'bbp_programs_top50_canonical.jsonl'
CANON_CSV = KNOWLEDGE_DIR / 'bbp_priority_rank_top50_canonical.csv'
VALIDATION_JSON = KNOWLEDGE_DIR / 'bbp_top50_url_validation.json'
FALLBACK_JSONL = KNOWLEDGE_DIR / 'bbp_programs_top50.jsonl'
FALLBACK_CSV = KNOWLEDGE_DIR / 'bbp_priority_rank_top50.csv'
MD_SUMMARY = KNOWLEDGE_DIR / 'BBP_TOP50.md'

def _read_jsonl(path: Path):
    items = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                import json
                items.append(json.loads(line))
    except FileNotFoundError:
        return []
    return items

@router.get('/bbp/top50')
async def bbp_top50(n: int = 50) -> Dict[str, Any]:
    data = _read_jsonl(CANON_JSONL) or _read_jsonl(FALLBACK_JSONL)
    if not data:
        return {'programs': [], 'count': 0, 'source': None}
    data.sort(key=lambda r: r.get('priority_score', 0.0), reverse=True)
    sel = data[: max(1, min(int(n), 50))]
    return {'programs': sel, 'count': len(sel), 'source': str(CANON_JSONL if (CANON_JSONL.exists()) else FALLBACK_JSONL)}

@router.get('/bbp/top10')
async def bbp_top10() -> Dict[str, Any]:
    return await bbp_top50(n=10)  # type: ignore

@router.get('/bbp/top50/validation')
async def bbp_top50_validation() -> Dict[str, Any]:
    import json
    if not VALIDATION_JSON.exists():
        return {'validation': [], 'available': False}
    return {'validation': json.loads(VALIDATION_JSON.read_text()), 'available': True}

@router.get('/bbp/top50/download')
async def bbp_top50_download(fmt: str = 'canonical_jsonl'):
    fmt = (fmt or '').lower()
    mapping = {
        'canonical_jsonl': (CANON_JSONL, 'text/plain'),
        'canonical_csv': (CANON_CSV, 'text/csv'),
        'jsonl': (FALLBACK_JSONL, 'text/plain'),
        'csv': (FALLBACK_CSV, 'text/csv'),
        'md': (MD_SUMMARY, 'text/markdown'),
        'validation': (VALIDATION_JSON, 'application/json'),
    }
    if fmt not in mapping:
        from fastapi import HTTPException
        raise HTTPException(400, detail='unsupported_format')
    path, media = mapping[fmt]
    if not path.exists():
        from fastapi import HTTPException
        raise HTTPException(404, detail='file_not_found')
    return FileResponse(path, media_type=media, filename=path.name)


from ..core.jobs import enqueue
from ..core.logs import log_decision

@router.post('/bbp/queue')
async def bbp_queue(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Queue a plan-mode OSINT dork run for a given target with scope acceptance flagged.
    # This performs a plan-mode run (no external calls) via /dorks/run and returns job + run info.
    target = (payload.get('target') or '').strip()
    if not target:
        raise HTTPException(400, 'target required')
    mode = (payload.get('mode') or 'plan').lower()
    chain = payload.get('chain')  # optional
    auto = bool(payload.get('auto', True))

    # DUPLICATE_PREFLIGHT: block recent identical plan runs (6h window)
    try:
        from apps.backend.src.core.run_store import load_all_runs
        import time as _t
        recent = load_all_runs() or []
        _now = _t.time()
        def _age_sec(ts: str):
            try:
                return _now - _t.mktime(_t.strptime(ts, '%Y-%m-%dT%H:%M:%SZ'))
            except Exception:
                return 10**9
        for r in recent:
            if _age_sec(r.get('timestamp','1970-01-01T00:00:00Z')) < 6*3600:
                if r.get('target') == target and (r.get('chain') or 'default_chain') == (chain or 'default_chain'):
                    from fastapi import HTTPException
                    raise HTTPException(status_code=409, detail='duplicate_plan_recent')
    except Exception:
        pass
    

    job = enqueue('dorks_scan', {
        'target': target,
        'mode': mode,
        'chain': chain,
        'accept_scope': True,
    })
    try:
        log_decision(job['id'], 'bbp_queue', {'target': target, 'mode': mode, 'chain': chain})
    except Exception:
        pass

    out: Dict[str, Any] = {'queued': True, 'job': job}

    if auto:
        # Dev convenience: directly call plan-mode /dorks/run to persist a run record (no external calls)
        try:
            from fastapi.testclient import TestClient
            from apps.backend.src.main import app as _app
            client = TestClient(_app)
            AUTH = {'Authorization': 'Bearer devtoken'}
            body = {'target': target, 'mode': 'plan', 'chain': chain}
            r = client.post('/dorks/run', headers=AUTH, json=body)
            out['auto_run'] = {'status': r.status_code, 'body': r.json()}
        except Exception as e:
            out['auto_run'] = {'status': 'error', 'error': str(e)}

    return out
