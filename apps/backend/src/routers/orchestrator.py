from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.jobs import enqueue, list_jobs
from ..core.logs import log_decision


from typing import Any

def _json_run_id(obj: Any):
    try:
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            return obj.get('run_id') or obj.get('id') or obj.get('rid')
        return None
    except Exception:
        return None

router = APIRouter(prefix='/orchestrator', tags=['orchestrator'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

@router.post('/queue_scan')
async def queue_scan(payload: Dict[str, Any]) -> Dict[str, Any]:
    target = payload.get('target')
    if not target:
        raise HTTPException(400, 'target required')
    job = enqueue('dorks_scan', {
        'target': target,
        'mode': payload.get('mode') or 'plan',
        'chain': payload.get('chain') or 'default_chain',
        'accept_scope': bool(payload.get('accept_scope') or False)
    })
    try:
        log_decision(job['id'], 'queue_scan', {'target': target})
    except Exception:
        pass
    return {'queued': True, 'job': job}


@router.post('/run_next')
async def run_next() -> Dict[str, Any]:
    from fastapi.testclient import TestClient
    import main as backend_main
    client = TestClient(backend_main.app)
    AUTH = {"Authorization": "Bearer devtoken"}
    jobs = list_jobs('queued')
    for job in jobs:
        if job.get('kind') != 'dorks_scan':
            continue
        payload = job.get('payload') or {}
        body = {'target': payload.get('target'), 'mode': payload.get('mode'), 'chain': payload.get('chain')}
        if not payload.get('accept_scope'):
            return {'status': 'blocked', 'reason': 'scope_not_accepted', 'job_id': job['id']}
        try:
            r = client.post('/dorks/run', json=body, headers=AUTH)
            if r.status_code != 200:
                return {'status': 'error', 'job_id': job['id'], 'code': r.status_code, 'resp': r.json()}
            resp = r.json()
            rid = _json_run_id(resp)
            log_decision(rid, 'orchestrator_run', {'job_id': job['id'], 'target': payload.get('target')})
            return {'status': 'ran', 'job_id': job['id'], 'run_id': rid}
        except Exception as e:
            return {'status': 'error', 'job_id': job['id'], 'error': str(e)}
    return {'status': 'no_jobs'}
