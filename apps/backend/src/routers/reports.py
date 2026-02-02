from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any

from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.packager import build_submission_package
from ..core.duplicates import check_title_duplicate, vector_duplicate
from ..core.vector_store import VectorStore
from ..core.logs import log_decision
from ..core.recordings import has_recording
from ..core.finalize import finalize_report

try:
    from ..core.report_formats import get_format, render_report, validate_rendered  # type: ignore
except Exception:  # pragma: no cover
    from ..core.formats import get_format, render_report, validate_rendered  # type: ignore

router = APIRouter(prefix='/reports', tags=['reports'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

@router.post('/render')
async def render(payload: Dict[str, Any]) -> Dict[str, Any]:
    fid = payload.get('format_id') or payload.get('format')
    if not fid:
        raise HTTPException(400, 'format_id required')
    finding = payload.get('finding') or {}
    evidence = payload.get('evidence') or {}
    mitigation = payload.get('mitigation') or {}
    run_id = (payload.get('run_id') or 'n/a')
    content = render_report(get_format(fid), finding, evidence, mitigation)
    try:
        log_decision(run_id, 'report_render', {'format': fid, 'finding_title': finding.get('title')})
    except Exception:
        pass
    return {'content': content}

@router.post('/validate')
async def validate(payload: Dict[str, Any]) -> Dict[str, Any]:
    fid = payload.get('format_id')
    if not fid:
        raise HTTPException(400, 'format_id required')
    run_id = payload.get('run_id')
    if not run_id:
        raise HTTPException(400, 'run_id required')
    finding = payload.get('finding') or {}
    evidence = payload.get('evidence') or {}
    mitigation = payload.get('mitigation') or {}
    has_rec = bool(payload.get('has_recording'))
    fmt = get_format(fid)
    content = render_report(fmt, finding, evidence, mitigation)
    result = validate_rendered(fmt.get('stakeholder', 'generic'), content, run_id=run_id, has_recording=has_rec)
    try:
        log_decision(run_id, 'report_validate', {'format': fid, 'ok': bool(result.get('ok'))})
    except Exception:
        pass
    return {'ok': result.get('ok', False), 'result': result, 'content': content}

@router.post('/submit_hil')
async def submit_hil(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = payload.get('run_id')
    fid = payload.get('format_id')
    if not run_id or not fid:
        raise HTTPException(400, 'run_id and format_id required')
    if not payload.get('hil_approved'):
        raise HTTPException(403, 'hil_approval_required')
    if not has_recording(run_id):
        raise HTTPException(409, 'screen_recording_required')

    finding = payload.get('finding') or {}
    evidence = payload.get('evidence') or {}
    mitigation = payload.get('mitigation') or {}
    fmt = get_format(fid)
    content = render_report(fmt, finding, evidence, mitigation)

    from ..core.persistence import persist_submission
    saved = persist_submission(run_id, content, {
        'run_id': run_id,
        'format_id': fid,
        'hil_approved': True,
        'duplicate_check': payload.get('duplicate_check') or {},
        'stakeholder': fmt.get('stakeholder', 'generic')
    })

    # Vector memory upsert for duplicate/chain signals
    try:
        vs = VectorStore()
        title = (finding.get('title') or run_id)
        summary = (finding.get('summary') or '')
        repro = (evidence.get('repro') or '')
        text = f"{title} {summary} {repro}"
        vs.upsert([{'id': run_id, 'text': text, 'meta': {'run_id': run_id, 'format': fid, 'title': title, 'severity': (finding.get('severity') or 'low')}}])
    except Exception:
        pass

    try:
        log_decision(run_id, 'report_submit_hil', {'format': fid, 'stakeholder': fmt.get('stakeholder')})
    except Exception:
        pass
    return {'status': 'queued_for_submission_by_operator', 'artifacts': saved}

@router.post('/duplicate_check')
async def duplicate_check(payload: Dict[str, Any]) -> Dict[str, Any]:
    title = (payload.get('finding') or {}).get('title') or payload.get('title')
    if not title:
        raise HTTPException(400, 'title required')
    td = check_title_duplicate(title)
    vd = vector_duplicate(title, (payload.get('summary') or (payload.get('finding') or {}).get('summary')))
    status = 'duplicate_suspected' if (td.get('count', 0) > 0 or vd.get('count', 0) > 0) else 'clear'
    return {'duplicate_check': {'status': status, 'title': td, 'vector': vd}}

@router.post('/finalize')
async def finalize(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = payload.get('run_id')
    if not run_id:
        raise HTTPException(400, 'run_id required')
    fmt_id = (payload.get('format_id') or 'google_vrp')
    fmt = get_format(fmt_id)
    # finalize_report evaluates mitigation, recording, duplicate status, etc.
    out = finalize_report(run_id, fmt.get('stakeholder', 'generic'), payload)
    if out.get('ok'):
        try:
            log_decision(run_id, 'report_finalize', {'ok': True, 'stakeholder': fmt.get('stakeholder')})
        except Exception:
            pass
        # Tests expect ready_for_hil_review
        return {'status': 'ready_for_hil_review', 'run_id': run_id}
    reason = out.get('reason') or 'finalize_requirements_not_met'
    status = 409 if reason in ('mitigation_required', 'recording_required', 'duplicate_suspected', 'hil_required') else 400
    return JSONResponse(status_code=status, content={'status': 'blocked', 'reason': reason})

@router.post('/package')
async def package(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = payload.get('run_id')
    fid = payload.get('format_id')
    if not run_id or not fid:
        raise HTTPException(400, 'run_id and format_id required')
    if not payload.get('hil_approved'):
        raise HTTPException(403, 'hil_approval_required')
    if not has_recording(run_id):
        raise HTTPException(409, 'screen_recording_required')

    fmt = get_format(fid)
    stakeholder = fmt.get('stakeholder', 'generic')
    ctx = {
        'run_id': run_id,
        'finding': payload.get('finding') or {},
        'evidence': payload.get('evidence') or {},
        'mitigation': payload.get('mitigation') or {},
        'hil_approved': True,
        'duplicate_check': payload.get('duplicate_check') or {}
    }
    from ..core.finalize import finalize_report as _finalize
    if not bool(payload.get('override_package_without_finalize')):
        fin = _finalize(run_id, stakeholder, ctx)
        if not fin.get('ok'):
            raise HTTPException(409, 'finalize_requirements_not_met')

    out = build_submission_package(run_id, stakeholder, ctx)
    try:
        log_decision(run_id, 'report_package', {'stakeholder': stakeholder, 'zip': out.get('zip')})
    except Exception:
        pass
    return {'status': 'packaged', 'package': out}

@router.post('/format/validate')
async def format_validate(payload: Dict[str, Any]) -> Dict[str, Any]:
    fmt_id = (payload.get('format_id') or 'google_vrp')
    finding = payload.get('finding') or {}
    evidence = payload.get('evidence') or {}
    mitigation = payload.get('mitigation') or {}
    rendered = render_report(get_format(fmt_id), finding, evidence, mitigation)
    ok, errs = validate_rendered(fmt_id, rendered)
    return {'ok': bool(ok), 'errors': errs}



from pathlib import Path as _P
ROOT = _P(__file__).resolve().parents[4]
REPORTS_DIR = ROOT / 'artifacts' / 'reports'

@router.get('/runs')
async def list_runs() -> dict:
    runs = []
    if REPORTS_DIR.exists():
        for p in sorted(d for d in REPORTS_DIR.iterdir() if d.is_dir()):
            runs.append(p.name)
    return {'runs': runs}



@router.post('/checklist')
async def checklist(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = payload.get('run_id')
    fid = payload.get('format_id') or 'google_vrp'
    if not run_id:
        raise HTTPException(400, 'run_id required')
    fmt = get_format(fid)
    finding = payload.get('finding') or {}
    evidence = payload.get('evidence') or {}
    mitigation = payload.get('mitigation') or {}
    rendered = render_report(fmt, finding, evidence, mitigation)
    # format validation
    v = validate_rendered(fmt.get('stakeholder','generic'), rendered, run_id=run_id, has_recording=has_recording(run_id))
    # duplicate checks
    title = finding.get('title') or payload.get('title') or ''
    title_res = check_title_duplicate(title) if title else {'status':'clear','count':0}
    vec_res = vector_duplicate(title, (finding.get('summary') or '')) if title else {'status':'clear','count':0}
    duplicate_status = 'duplicate_suspected' if (title_res.get('count',0) > 0 or vec_res.get('count',0) > 0) else 'clear'
    # recording present
    rec_ok = has_recording(run_id)
    # mitigation plan
    mit_ok = bool((mitigation or {}).get('plan'))
    ok = bool(v.get('ok') and rec_ok and mit_ok and duplicate_status == 'clear')
    out = {
        'ok': ok,
        'format_ok': bool(v.get('ok')),
        'recording_ok': rec_ok,
        'mitigation_ok': mit_ok,
        'duplicate': {'status': duplicate_status, 'title': title_res, 'vector': vec_res},
        'stakeholder': fmt.get('stakeholder','generic')
    }
    try:
        log_decision(run_id, 'report_checklist', out)
    except Exception:
        pass
    return out


from ..core.format_rules import check_format

@router.post('/format_check')
async def format_check(payload: Dict[str, Any]) -> Dict[str, Any]:
    stakeholder = payload.get('stakeholder') or payload.get('format_id') or 'google_vrp'
    out = check_format(stakeholder, payload)
    try:
        from ..core.logs import log_decision
        rid = payload.get('run_id') or 'no-run'
        log_decision(rid, 'report_format_check', {'stakeholder': stakeholder, 'ok': out.get('ok'), 'missing': out.get('missing')})
    except Exception:
        pass
    return {'format_check': out}
