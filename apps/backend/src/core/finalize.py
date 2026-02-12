from __future__ import annotations
from typing import Dict, Any

from pathlib import Path


def finalize_report(run_id: str, stakeholder: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforce minimal finalize requirements for HiL review readiness.

    API contract (tests rely on this):
    - `mitigation_plan` (or `mitigation.plan`) must be provided.
    - `recording_path` (or `has_recording=True`) must be provided; merely
      having a recording on disk is not sufficient because the operator is
      explicitly choosing which artifact is attached for submission.
    """

    missing: list[str] = []

    # Normalize mitigation plan input
    mitigation = payload.get("mitigation") or {}
    if not (mitigation.get("plan") or "").strip():
        plan = (payload.get("mitigation_plan") or "").strip()
        if plan:
            mitigation["plan"] = plan
        else:
            missing.append("mitigation")

    # Recording must be explicitly provided
    has_rec = bool(payload.get("has_recording"))
    if not has_rec:
        rec_path = payload.get("recording_path")
        if rec_path:
            p = Path(rec_path)
            if not p.is_absolute():
                root = Path(__file__).resolve().parents[5]
                alt_root = root / "k1"
                candidates = [root / p, alt_root / p]
            else:
                candidates = [p]
            for cand in candidates:
                if cand.exists():
                    has_rec = True
                    break
        if not has_rec:
            missing.append("recording")

    if missing:
        return {"ok": False, "reason": ";".join(f"{m}_required" for m in missing)}

    dup = (payload.get('duplicate_check') or {}).get('status')
    if dup and dup != 'clear':
        return {'ok': False, 'reason': 'duplicate_suspected'}

    # Do not require HiL at finalize stage; finalize prepares for HiL review.
    return {'ok': True}
