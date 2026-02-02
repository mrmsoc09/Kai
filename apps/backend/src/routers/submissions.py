from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from pathlib import Path
from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.packager import build_submission_package
from ..core.logs import log_decision
from fastapi.responses import FileResponse

router = APIRouter(prefix='/submissions', tags=['submissions'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

ROOT = Path(__file__).resolve().parents[4]
SUBMITS = ROOT / 'artifacts' / 'submissions'
OUTBOX = SUBMITS / 'outbox'
OUTBOX.mkdir(parents=True, exist_ok=True)

@router.post('/dispatch')
async def dispatch(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = payload.get('run_id')
    fid = payload.get('format_id') or 'google_vrp'
    stakeholder = payload.get('stakeholder') or 'google_vrp'
    if not run_id:
        raise HTTPException(400, 'run_id required')
    # ensure package exists
    pkg = SUBMITS / f'{run_id}_{stakeholder}.zip'
    if not pkg.exists():
        ctx = {
            'run_id': run_id,
            'finding': payload.get('finding') or {},
            'evidence': payload.get('evidence') or {},
            'mitigation': payload.get('mitigation') or {},
            'hil_approved': bool(payload.get('hil_approved')),
            'duplicate_check': payload.get('duplicate_check') or {}
        }
        info = build_submission_package(run_id, stakeholder, ctx)
        pkg = Path(info['zip'])
    # extract email.eml to outbox
    import zipfile
    out_eml = OUTBOX / f'{run_id}_{stakeholder}.eml'
    with zipfile.ZipFile(pkg, 'r') as z:
        if 'email.eml' not in z.namelist():
            raise HTTPException(500, 'email.eml missing in package')
        data = z.read('email.eml')
        out_eml.write_bytes(data)
    try:
        log_decision(run_id, 'report_dispatch', {'stakeholder': stakeholder, 'zip': str(pkg), 'eml': str(out_eml)})
    except Exception:
        pass
    return {'status': 'dispatched_to_outbox', 'zip': str(pkg), 'eml': str(out_eml)}


@router.get('/outbox_index')
async def outbox_index():
    files = []
    for p in sorted(OUTBOX.glob('*.eml')):
        files.append({'name': p.name, 'bytes': p.stat().st_size})
    return {'files': files}

@router.get('/outbox/{name}')
async def outbox_download(name: str):
    p = OUTBOX / name
    if not p.exists():
        raise HTTPException(404, 'not found')
    return FileResponse(path=str(p), filename=name, media_type='message/rfc822')


@router.post('/followup')
async def followup(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = payload.get('run_id')
    stakeholder = payload.get('stakeholder') or 'generic'
    if not run_id:
        raise HTTPException(400, 'run_id required')
    from email.message import EmailMessage
    from email.utils import formatdate
    msg = EmailMessage()
    msg['Date'] = formatdate(localtime=False)
    msg['Subject'] = f'Follow-up on submission {run_id}'
    msg['From'] = 'agent-zero@k1.local'
    msg['To'] = 'stakeholder@program.local'
    default_body = "Hello,\n\nFollowing up on report {rid}. Please advise on the current status.\n\nRegards,\nK1".format(rid=run_id)
    body = payload.get('body') or default_body
    msg.set_content(body)
    out_eml = OUTBOX / f'{run_id}_{stakeholder}_followup.eml'
    out_eml.write_bytes(msg.as_bytes())
    try:
        log_decision(run_id, 'report_followup', {'stakeholder': stakeholder, 'eml': str(out_eml)})
    except Exception:
        pass
    return {'status': 'followup_dispatched', 'eml': str(out_eml)}
