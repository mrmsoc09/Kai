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
        # Lightweight gate mode for tests/CLI: validate mitigation + recording
        fin = finalize_report(run_id or 'no-run', 'generic', payload)
        if not fin.get('ok'):
            return JSONResponse(status_code=409, content={'ok': False, 'reason': fin.get('reason')})
        return {'ok': True}
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
    run_id = payload.get('run_id') or 'no-run'
    fmt_id = (payload.get('format_id') or 'google_vrp')
    fmt = get_format(fmt_id)
    # finalize_report evaluates mitigation, recording, duplicate status, etc.
    out = finalize_report(run_id, fmt.get('stakeholder', 'generic'), payload)
    if out.get('ok'):
        try:
            log_decision(run_id, 'report_finalize', {'ok': True, 'stakeholder': fmt.get('stakeholder')})
        except Exception:
            pass
        return {'ok': True, 'status': 'ready_for_hil_review', 'run_id': run_id}
    reason = out.get('reason') or 'finalize_requirements_not_met'
    return JSONResponse(status_code=409, content={'ok': False, 'status': 'blocked', 'reason': reason})

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


# ========== Phase 6: Multi-Format Export & Evidence Embedding ==========

from datetime import datetime, timedelta

# Cache for generated reports (in production, use Redis)
_report_cache: Dict[str, Dict[str, Any]] = {}
_cache_expiry: Dict[str, datetime] = {}
CACHE_TTL_MINUTES = 60


def _generate_report_id(stakeholder: str, finding_title: str) -> str:
    """Generate unique report ID."""
    import hashlib
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    title_hash = hashlib.sha256(finding_title.encode()).hexdigest()[:8]
    return f"REPORT_{stakeholder.upper()}_{timestamp}_{title_hash}"


def _get_from_cache(report_id: str) -> Dict[str, Any] | None:
    """Get report from cache if still valid."""
    if report_id not in _report_cache:
        return None

    if datetime.utcnow() > _cache_expiry.get(report_id, datetime.utcnow()):
        # Cache expired
        del _report_cache[report_id]
        if report_id in _cache_expiry:
            del _cache_expiry[report_id]
        return None

    return _report_cache[report_id]


def _cache_report(report_id: str, report_data: Dict[str, Any]):
    """Cache generated report."""
    _report_cache[report_id] = report_data
    _cache_expiry[report_id] = datetime.utcnow() + timedelta(minutes=CACHE_TTL_MINUTES)


@router.post('/generate-all')
async def generate_all_formats(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Generate report in all formats (markdown, HTML, PDF, JSON)."""
    try:
        stakeholder = payload.get('stakeholder') or payload.get('format_id') or 'google_vrp'
        finding = payload.get('finding') or {}
        evidence = payload.get('evidence') or {}
        mitigation = payload.get('mitigation') or {}
        run_id = payload.get('run_id') or 'n/a'

        # Generate markdown (base format)
        fmt = get_format(stakeholder)
        markdown_content = render_report(fmt, finding, evidence, mitigation)

        report_id = _generate_report_id(stakeholder, finding.get('title', ''))

        # Try to generate other formats (may not all be available)
        result = {
            'report_id': report_id,
            'stakeholder': stakeholder,
            'formats': {
                'markdown': {
                    'size_bytes': len(markdown_content.encode()),
                    'generated_at': datetime.utcnow().isoformat(),
                }
            }
        }

        # Try PDF generation
        try:
            from ..core.pdf_generator import generate_pdf_from_markdown
            pdf_bytes = generate_pdf_from_markdown(markdown_content, stakeholder=stakeholder)
            result['formats']['pdf'] = {
                'size_bytes': len(pdf_bytes) if isinstance(pdf_bytes, bytes) else len(pdf_bytes.encode()),
                'generated_at': datetime.utcnow().isoformat(),
            }
        except Exception as e:
            result['formats']['pdf'] = {'error': str(e)}

        # Include validation if requested
        if payload.get('include_validation'):
            validation = validate_rendered(
                fmt.get('stakeholder', stakeholder),
                markdown_content,
                run_id=run_id,
                has_recording=bool(payload.get('has_recording'))
            )
            result['validation'] = validation

        # Cache result
        _cache_report(report_id, result)

        try:
            log_decision(run_id, 'report_generate_all', {
                'stakeholder': stakeholder,
                'formats': list(result['formats'].keys()),
                'report_id': report_id
            })
        except Exception:
            pass

        return {'ok': True, 'result': result}

    except Exception as e:
        import traceback
        logger.error(f"Multi-format generation failed: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.post('/embed-evidence')
async def embed_evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Embed evidence artifact in report."""
    try:
        from ..core.evidence_embedder import create_embedder

        finding_id = payload.get('finding_id')
        evidence_type = payload.get('evidence_type')
        content = payload.get('content')
        description = payload.get('description', '')
        metadata = payload.get('metadata', {})

        if not all([finding_id, evidence_type, content]):
            raise HTTPException(400, 'finding_id, evidence_type, and content required')

        embedder = create_embedder(merkle_chain_enabled=True)

        if evidence_type == 'code_snippet':
            result = embedder.embed_code_snippet(
                code_content=content,
                language=metadata.get('language', 'python'),
                finding_id=finding_id,
                description=description
            )
        elif evidence_type == 'log_output':
            result = embedder.embed_log_output(
                log_content=content,
                finding_id=finding_id,
                description=description,
                truncate_lines=metadata.get('max_lines')
            )
        else:
            raise HTTPException(400, f'Unsupported evidence type: {evidence_type}')

        return {'ok': True, 'embedding': result, 'embedded_at': datetime.utcnow().isoformat()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Evidence embedding failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")


@router.get('/cache/stats')
async def cache_stats() -> Dict[str, Any]:
    """Get report cache statistics."""
    try:
        active_count = sum(
            1 for rid, expiry in _cache_expiry.items()
            if datetime.utcnow() <= expiry
        )

        return {
            'ok': True,
            'statistics': {
                'total_cached': len(_report_cache),
                'active_reports': active_count,
                'cache_ttl_minutes': CACHE_TTL_MINUTES,
                'timestamp': datetime.utcnow().isoformat(),
            }
        }

    except Exception as e:
        logger.error(f"Cache stats retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.get('/cache/{report_id}')
async def get_cached_report(report_id: str) -> Dict[str, Any]:
    """Retrieve cached report."""
    try:
        report = _get_from_cache(report_id)

        if not report:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found or expired")

        return {
            'ok': True,
            'report_id': report_id,
            'report': report,
            'retrieved_at': datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")


@router.delete('/cache/{report_id}')
async def delete_cached_report(report_id: str) -> Dict[str, Any]:
    """Delete cached report."""
    try:
        if report_id in _report_cache:
            del _report_cache[report_id]
            if report_id in _cache_expiry:
                del _cache_expiry[report_id]
            return {
                'ok': True,
                'report_id': report_id,
                'deleted_at': datetime.utcnow().isoformat(),
            }

        raise HTTPException(status_code=404, detail=f"Report {report_id} not in cache")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report deletion failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


import logging
logger = logging.getLogger(__name__)
