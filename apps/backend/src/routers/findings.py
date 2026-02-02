
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
from datetime import datetime, timezone
from ..core.run_store import load_run, save_run_record

router = APIRouter(prefix="/findings", tags=["findings"])

@router.post('/set_status')
def set_status(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = payload.get('run_id')
    status = (payload.get('status') or '').upper()
    finding_id = payload.get('finding_id') or 'run'
    recording_path = payload.get('recording_path')

    if not run_id or not status:
        raise HTTPException(status_code=400, detail='run_id and status required')

    run = load_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail='run_not_found')

    # Enforce evidence gate: VALIDATED requires recording reference
    if status == 'VALIDATED':
        recorded = recording_path or (run.get('artifacts') or {}).get('recording_path')
        if not recorded:
            return JSONResponse(status_code=409, content={
                'status': 'blocked',
                'reason': 'recording_required',
                'next': 'attach recording_path and retry or keep status below VALIDATED'
            })
        # persist recording into artifacts if provided
        if recording_path:
            run.setdefault('artifacts', {})['recording_path'] = recording_path
            run['first_validated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Update findings list
    fins = run.setdefault('findings', [])
    updated = False
    for f in fins:
        if f.get('id') == finding_id:
            f['status'] = status
            f['updated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            updated = True
            break
    if not updated:
        fins.append({'id': finding_id, 'status': status, 'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')})

    # If this is the first non-INFO status treat as first_signal_at
    if status in ('HYPOTHESIS','SIGNAL','LIKELY') and not run.get('first_signal_at'):
        run['first_signal_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Persist updated run (recomputes metrics)
    save_run_record(run_id, run)
    return {'ok': True, 'run_id': run_id, 'findings': fins, 'artifacts': run.get('artifacts', {})}
