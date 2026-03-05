"""
Hunt Workflow State Machine + File-based Persistence

Workflows track the lifecycle of a bug-bounty hunt from program selection
through submission.  Each workflow is stored as a JSON file at:

    artifacts/workflows/{wf_id}/workflow.json

Public programs (public_bbp / public_vrp / government_cvd) start directly in
SCOPING because scope is already known from the opportunity catalog.
Invite-only programs start in SELECTED pending scope review.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[4]
_WF_DIR = ROOT / "artifacts" / "workflows"
_WF_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# State machine definition
# ---------------------------------------------------------------------------

STATES: List[str] = [
    "SELECTED",
    "SCOPING",
    "RECON",
    "SCANNING",
    "TRIAGE",
    "HIL_REVIEW",
    "SUBMITTED",
    "CLOSED",
]

TRANSITIONS: Dict[str, List[str]] = {
    "SELECTED":   ["SCOPING", "CLOSED"],
    "SCOPING":    ["RECON", "CLOSED"],
    "RECON":      ["SCANNING", "TRIAGE", "CLOSED"],
    "SCANNING":   ["TRIAGE", "CLOSED"],
    "TRIAGE":     ["HIL_REVIEW", "SUBMITTED", "CLOSED"],
    "HIL_REVIEW": ["SUBMITTED", "TRIAGE", "CLOSED"],
    "SUBMITTED":  ["CLOSED"],
    "CLOSED":     [],
}

_PUBLIC_ACCESS_TYPES = {"public_bbp", "public_vrp", "government_cvd"}


def _initial_state(access_type: str) -> str:
    """Public programs skip SELECTED — scope is already known."""
    return "SCOPING" if access_type in _PUBLIC_ACCESS_TYPES else "SELECTED"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class HuntWorkflow:
    id: str
    opportunity_id: str
    program_name: str
    platform: str
    access_type: str
    status: str
    scope_accepted: bool
    scope_domains: List[str]
    findings_count: int
    created_at: str
    updated_at: str
    transitioned_at: Dict[str, str]   # state -> ISO timestamp
    run_ids: List[str]
    notes: str
    created_by: str

    def is_terminal(self) -> bool:
        return self.status in ("SUBMITTED", "CLOSED")

    def allowed_transitions(self) -> List[str]:
        return TRANSITIONS.get(self.status, [])


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _wf_path(wf_id: str) -> Path:
    d = _WF_DIR / wf_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "workflow.json"


def _save(wf: HuntWorkflow) -> None:
    _wf_path(wf.id).write_text(json.dumps(asdict(wf), ensure_ascii=False, indent=2))


def _load_raw(wf_id: str) -> Optional[dict]:
    p = _wf_path(wf_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _from_dict(d: dict) -> HuntWorkflow:
    return HuntWorkflow(
        id=d["id"],
        opportunity_id=d["opportunity_id"],
        program_name=d["program_name"],
        platform=d["platform"],
        access_type=d["access_type"],
        status=d["status"],
        scope_accepted=bool(d.get("scope_accepted", False)),
        scope_domains=list(d.get("scope_domains", [])),
        findings_count=int(d.get("findings_count", 0)),
        created_at=d["created_at"],
        updated_at=d["updated_at"],
        transitioned_at=dict(d.get("transitioned_at", {})),
        run_ids=list(d.get("run_ids", [])),
        notes=d.get("notes", ""),
        created_by=d.get("created_by", ""),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_workflow(
    opportunity_id: str,
    program_name: str,
    platform: str,
    access_type: str,
    scope_domains: Optional[List[str]] = None,
    notes: str = "",
    created_by: str = "",
) -> HuntWorkflow:
    now = _now_iso()
    status = _initial_state(access_type)
    wf = HuntWorkflow(
        id=str(uuid.uuid4()),
        opportunity_id=opportunity_id,
        program_name=program_name,
        platform=platform,
        access_type=access_type,
        status=status,
        scope_accepted=(status == "SCOPING"),  # public programs auto-accept scope
        scope_domains=list(scope_domains or []),
        findings_count=0,
        created_at=now,
        updated_at=now,
        transitioned_at={status: now},
        run_ids=[],
        notes=notes,
        created_by=created_by,
    )
    _save(wf)
    return wf


def get_workflow(wf_id: str) -> Optional[HuntWorkflow]:
    raw = _load_raw(wf_id)
    if raw is None:
        return None
    return _from_dict(raw)


def list_workflows(
    status: Optional[str] = None,
    created_by: Optional[str] = None,
    platform: Optional[str] = None,
) -> List[HuntWorkflow]:
    out: List[HuntWorkflow] = []
    for p in sorted(_WF_DIR.glob("*/workflow.json")):
        try:
            raw = json.loads(p.read_text())
            wf = _from_dict(raw)
            if status and wf.status != status:
                continue
            if created_by and wf.created_by != created_by:
                continue
            if platform and wf.platform != platform:
                continue
            out.append(wf)
        except Exception:
            pass
    return out


def transition_workflow(
    wf_id: str,
    to_state: str,
    notes: str = "",
) -> HuntWorkflow:
    """
    Advance the workflow to *to_state*.
    Raises ValueError for invalid transitions.
    Raises KeyError when the workflow does not exist.
    """
    wf = get_workflow(wf_id)
    if wf is None:
        raise KeyError(f"Workflow {wf_id!r} not found")

    allowed = TRANSITIONS.get(wf.status, [])
    if to_state not in allowed:
        raise ValueError(
            f"Cannot transition from {wf.status!r} to {to_state!r}. "
            f"Allowed: {allowed}"
        )

    now = _now_iso()
    wf.status = to_state
    wf.updated_at = now
    wf.transitioned_at[to_state] = now
    if notes:
        wf.notes = notes if not wf.notes else f"{wf.notes}\n{now}: {notes}"

    # Auto-mark scope accepted when entering SCOPING
    if to_state == "SCOPING":
        wf.scope_accepted = True

    _save(wf)
    return wf


def link_run(wf_id: str, run_id: str) -> HuntWorkflow:
    """Associate a recon/scan run_id with the workflow."""
    wf = get_workflow(wf_id)
    if wf is None:
        raise KeyError(f"Workflow {wf_id!r} not found")
    if run_id not in wf.run_ids:
        wf.run_ids.append(run_id)
        wf.updated_at = _now_iso()
        _save(wf)
    return wf


def increment_findings(wf_id: str, delta: int = 1) -> Optional[HuntWorkflow]:
    """Increment the findings counter (called by finding lifecycle hooks)."""
    wf = get_workflow(wf_id)
    if wf is None:
        return None
    wf.findings_count = max(0, wf.findings_count + delta)
    wf.updated_at = _now_iso()
    _save(wf)
    return wf


def update_notes(wf_id: str, notes: str) -> Optional[HuntWorkflow]:
    """Update workflow notes without a state transition."""
    wf = get_workflow(wf_id)
    if wf is None:
        return None
    wf.notes = notes
    wf.updated_at = _now_iso()
    _save(wf)
    return wf


def delete_workflow(wf_id: str) -> bool:
    """Close and remove the workflow JSON (non-destructive: transitions to CLOSED first)."""
    wf = get_workflow(wf_id)
    if wf is None:
        return False
    if not wf.is_terminal():
        try:
            transition_workflow(wf_id, "CLOSED")
        except ValueError:
            pass
    p = _wf_path(wf_id)
    if p.exists():
        p.unlink()
    return True
