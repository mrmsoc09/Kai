from __future__ import annotations
from typing import Dict, Any

# Recording helper
try:
    from .recordings import has_recording as _has_rec  # type: ignore
except Exception:  # pragma: no cover
    def _has_rec(_run_id: str) -> bool:
        return False


def finalize_report(run_id: str, stakeholder: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    # Enforce minimal finalize requirements for HiL review readiness.
    mitigation = payload.get('mitigation') or {}
    if not (mitigation.get('plan') or '').strip():
        return {'ok': False, 'reason': 'mitigation_required'}

    # Determine recording presence via multiple redundant strategies
    has_rec = bool(payload.get('has_recording'))
    if not has_rec:
        try:
            from .recordings import has_recording as _has_rec  # type: ignore
            has_rec = _has_rec(run_id)
        except Exception:
            has_rec = False
    if not has_rec:
        # Fallback direct filesystem check to avoid any import/context issues
        from pathlib import Path as _P
        _ROOT = _P(__file__).resolve().parents[5]
        _RECS = _ROOT / 'artifacts' / 'recordings'
        _dir = _RECS / run_id
        try:
            if _dir.exists():
                for ext in ('.mp4', '.webm', '.mkv'):
                    if any(_dir.glob(f'seg_*{ext}')):
                        has_rec = True
                        break
            if not has_rec:
                arch = _RECS / f"{run_id}.tar.gz"
                has_rec = arch.exists() and arch.is_file() and arch.stat().st_size > 0
        except Exception:
            has_rec = False

    if not has_rec:
        return {'ok': False, 'reason': 'recording_required'}

    dup = (payload.get('duplicate_check') or {}).get('status')
    if dup and dup != 'clear':
        return {'ok': False, 'reason': 'duplicate_suspected'}

    # Do not require HiL at finalize stage; finalize prepares for HiL review.
    return {'ok': True}
