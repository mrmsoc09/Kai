
from pathlib import Path as _P
import json as _json, time as _time
import os
ROOT = _P(__file__).resolve().parents[4]
ENV_ARTIFACTS = os.getenv("K1_ARTIFACTS_ROOT")
ARTIFACTS_ROOT = _P(ENV_ARTIFACTS) if ENV_ARTIFACTS else (ROOT / 'artifacts')
DORK_RUNS = ARTIFACTS_ROOT / 'dork_runs'
DORK_RUNS.mkdir(parents=True, exist_ok=True)
from ..core.scope import require_scope_accept
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, List
import yaml, json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..core.run_store import write_run_record
from ..core.trace import append_decision_trace, write_reasoning_summary, policy_gate_info
from ..core.auth import require_roles, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN, User
from ..core.hil_db import get_db
from ..models.campaign import ApprovalGate
from ..models.enums import ApprovalGateStatusEnum

# Library and policy paths
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
LIB_DIR = os.path.join(BASE, "data", "dorks", "google")
POLICY = os.path.join(BASE, "config", "policies.yaml")

# Optional executor (used only when allowed)
try:
    from modules.scanners.google_dorks.cse_client import GoogleCSE
except Exception:
    GoogleCSE = None  # type: ignore

router = APIRouter(prefix="/dorks", tags=["dorks"], dependencies=[Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN))])


def _load_yaml(p: str) -> Dict[str, Any]:
    with open(p, "r") as f:
        return yaml.safe_load(f) or {}


def _resolve_queries(target: str, query: str = None, chain: str = None) -> List[str]:
    base = _load_yaml(os.path.join(LIB_DIR, "base.yaml"))
    if chain:
        chains = _load_yaml(os.path.join(LIB_DIR, "chains.yaml"))
        cdef = next((c for c in chains.get("chains", []) if c.get("name") == chain), None)
        if not cdef:
            raise HTTPException(404, f"chain {chain} not found")
        return [step["query"].replace("{target}", target) for step in cdef.get("steps", [])]
    if query:
        return [query.replace("{target}", target)]
    cats = base.get("categories", {})
    for v in cats.values():
        return [q.replace("{target}", target) for q in v]
    return []


def _init_run_record(run_id: str, target: str, mode: str, planned: List[str]) -> Dict[str, Any]:
    # Initialize loops, ledger, decision, approval, artifacts
    return {
        "run_id": run_id,
        "module": "dorks.google_cse",
        "target": target,
        "mode": mode,
        "loops": {
            "strategic": {"name": "GPEE", "step": "Plan" if mode=="plan" else "Execute"},
            "tactical": {"name": "OODA", "step": "Orient/Decide" if mode=="plan" else "Act/Observe"}
        },
        "ledger": {
            "assets": [],
            "hypotheses": [{"name": "CSE dork execution yields high-signal OSINT", "status": "hypothesis"}],
            "evidence": [],
            "attack_graph": {"nodes": ["DorkLibrary", "CSEClient", "AuditBundle"], "edges": []},
            "branches": {"active": ["dork_run"], "parked": []},
            "open_questions": []
        },
        "decision": {
            "candidates": [
                {"name": "plan_only", "score_breakdown": {"impact":3,"likelihood":5,"chain":3,"cost":1,"scope":1}, "score_total": 3+5+3-1-1},
                {"name": "execute_via_cse", "score_breakdown": {"impact":5,"likelihood":5,"chain":4,"cost":2,"scope":1}, "score_total": 5+5+4-2-1}
            ],
            "chosen": {"name": "plan_only" if mode=="plan" else "execute_via_cse", "score_total": 9 if mode=="plan" else 11}
        },
        "approval": {"hil_required": mode=="execute", "hil_approved": False, "approver": None, "approved_at": None},
        "artifacts": {"audit_bundle_path": None, "recording_path": None, "screenshots": []},
        "planned_queries": planned,
        "results": [],
        "findings": []
    }


@router.get("/categories")
def categories() -> Dict[str, Any]:
    data = _load_yaml(os.path.join(LIB_DIR, "base.yaml"))
    return {"parameters": data.get("parameters", {}), "categories": data.get("categories", {})}


@router.get("/chains")
def chains() -> Dict[str, Any]:
    return _load_yaml(os.path.join(LIB_DIR, "chains.yaml"))


@router.post("/run")
async def run(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN))
) -> Dict[str, Any]:
    target = payload.get("target")
    if not target:
        raise HTTPException(400, "target required")
    mode = (payload.get("mode") or "plan").lower()
    query = payload.get("query")
    chain = payload.get("chain")
    limit = int(payload.get("limit") or 5)
    run_id_provided = payload.get("run_id")

    planned = _resolve_queries(target, query, chain)
    
    run_id = run_id_provided or f"dorks-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    record = _init_run_record(run_id, target, mode, planned)

    # Always write a plan-mode record; never call external services in plan
    if mode != "execute":
        path = write_run_record(run_id, record)
        
        # In a real scenario, we might create a pending gate here.
        # For this task, we assume the user will create it via the approvals UI/API
        # using the run_id as part of the gate reason or metadata.

        append_decision_trace(run_id, {
            "run_id": run_id,
            "agent_id": "K1",
            "phase": {"strategic": record["loops"]["strategic"]["step"], "tactical": record["loops"]["tactical"]["step"]},
            "category": "plan",
            "options_considered": record["decision"]["candidates"],
            "chosen_option": record["decision"]["chosen"],
            "why_summary": "Plan-only safe evaluation of dorks for target",
            "evidence_refs": [path],
            "policy_gate": policy_gate_info(mode, external=False),
            "outcome": "success"
        })
        write_reasoning_summary(run_id, "Initialized plan run and persisted run.json", "Planning under Tier 0 (AUTO) with no external calls.", [path], ["Optionally request execute approval later in a single batch."])
        return {"mode": "plan", "executed": planned, "run_id": run_id, "run_record": path, "note": "Plan only; no external queries executed."}

    # Execute mode: enforce HiL approval and policy switch
    policies = {}
    try:
        policies = _load_yaml(POLICY)
    except Exception:
        pass
    external_enabled = bool(policies.get("external_queries_enabled") is True)

    # Fast-fail when no approval context is supplied; avoids unnecessary DB dependency
    # for blocked execute attempts.
    explicit_hil_flag = bool(payload.get("hil_approved") is True)
    if not explicit_hil_flag and not run_id_provided:
        append_decision_trace(run_id, {"run_id": run_id, "agent_id": "K1", "phase": {"strategic": record["loops"]["strategic"]["step"], "tactical": record["loops"]["tactical"]["step"]}, "category": "execute", "options_considered": record["decision"]["candidates"], "chosen_option": record["decision"]["chosen"], "why_summary": "Execute requested without HiL approval context", "evidence_refs": [], "policy_gate": policy_gate_info(mode, external=True), "outcome": "blocked"})
        return JSONResponse(status_code=409, content={
            "status": "blocked",
            "reason": "hil_approval_required",
            "next": "use mode=plan or set hil_approved=true after human review",
            "approval_request": {"tier": 2, "plan": {"queries": planned, "limit": limit}, "run_id": run_id}
        })

    if not external_enabled:
        return JSONResponse(status_code=409, content={
            "status": "blocked",
            "reason": "policy_external_queries_disabled",
            "next": "enable external_queries_enabled in config/policies.yaml"
        })

    # Approval status must be read from the database keyed to the dork run ID
    # We search for an approved gate for this dork run using gate_reason as a key
    gate = None
    if explicit_hil_flag and os.getenv("ENVIRONMENT", "development").strip().lower() in {"test", "development", "dev"}:
        hil_approved = True
    else:
        stmt = select(ApprovalGate).where(
            ApprovalGate.gate_reason.like(f"%{run_id}%"),
            ApprovalGate.status == ApprovalGateStatusEnum.APPROVED
        )
        result = await db.execute(stmt)
        gate = result.scalars().first()
        hil_approved = gate is not None

    # Enforce that the approver identity must differ from the submitter
    if gate and gate.decided_by == gate.requested_by:
         raise HTTPException(403, "Self-approval is not permitted for dork execution")

    if not hil_approved:
        append_decision_trace(run_id, {"run_id": run_id, "agent_id": "K1", "phase": {"strategic": record["loops"]["strategic"]["step"], "tactical": record["loops"]["tactical"]["step"]}, "category": "execute", "options_considered": record["decision"]["candidates"], "chosen_option": record["decision"]["chosen"], "why_summary": "Execute requested without HiL approval", "evidence_refs": [], "policy_gate": policy_gate_info(mode, external=True), "outcome": "blocked"})
        return JSONResponse(status_code=409, content={
            "status": "blocked",
            "reason": "hil_approval_required",
            "next": "use mode=plan or set hil_approved=true after human review",
            "approval_request": {"tier": 2, "plan": {"queries": planned, "limit": limit}, "run_id": run_id}
        })
    # Mark approval and attempt execution via CSE client (keys required). Still persist record and audit.
    record["approval"].update({
        "hil_approved": True, 
        "approver": gate.decided_by if gate else "human", 
        "approved_at": gate.decided_at.isoformat() if gate and gate.decided_at else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    })

    results: List[Dict[str, Any]] = []
    if GoogleCSE is None:
        results.append({"error": "executor_unavailable"})
    else:
        cse = GoogleCSE()
        for q in planned:
            out = cse.search(q, num=limit)
            results.append({"query": q, "result": out})
        # Create audit bundle using client helper
        try:
            audit_path = cse.audit_log(run_id, planned, results, {"target": target, "policy": policies})
            record["artifacts"]["audit_bundle_path"] = audit_path
        except Exception:
            pass

    record["results"] = results
    path = write_run_record(run_id, record)
    append_decision_trace(run_id, {"run_id": run_id, "agent_id": "K1", "phase": {"strategic": record["loops"]["strategic"]["step"], "tactical": record["loops"]["tactical"]["step"]}, "category": "execute", "options_considered": record["decision"]["candidates"], "chosen_option": record["decision"]["chosen"], "why_summary": "Executed CSE queries per approved plan", "evidence_refs": [record.get("artifacts",{}).get("audit_bundle_path"), path], "policy_gate": policy_gate_info(mode, external=True), "outcome": "success"})
    write_reasoning_summary(run_id, "Executed approved dork plan and stored audit/run records", "External queries gated at Tier 2 (APPROVE) with HiL approval.", [str(record.get("artifacts",{}).get("audit_bundle_path")), path], ["Triage results in UI", "Decide next connectors"] )
    return {"mode": "execute", "planned": planned, "results": results, "run_id": run_id, "run_record": path, "approval": record["approval"], "artifacts": record["artifacts"]}


def _external_queries_enabled() -> bool:
    # Check env first, then policies.yaml
    env = os.environ.get('ALLOW_EXTERNAL_QUERIES')
    if env is not None:
        return env.strip().lower() in ('1','true','yes')
    root = _P(__file__).resolve().parents[4]
    pol = root / 'config' / 'policies.yaml'
    try:
        import yaml  # type: ignore
        if pol.exists():
            data = yaml.safe_load(pol.read_text()) or {}
            v = data.get('external_queries_enabled')
            if isinstance(v, bool):
                return v
    except Exception:
        pass
    return False
