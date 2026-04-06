from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict

from ..core.governance_readiness import build_governance_readiness_report
from ..core.kai_execution_benchmarks import (
    build_benchmark_intelligence_report,
    load_benchmark_payload,
    query_benchmark_records,
    summarize_benchmark_records,
    run_parallel_execution_benchmark_scenario,
)
from ..core.auth import (
    User,
    get_current_user,
    require_roles,
    ROLE_VIEWER,
    ROLE_OPERATOR,
    ROLE_ANALYST,
    ROLE_ADMIN,
)

router = APIRouter(
    prefix="/governance", 
    tags=["governance"],
    dependencies=[Depends(require_roles(ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN))]
)


@router.get("/readiness")
async def governance_readiness() -> Dict[str, Any]:
    return build_governance_readiness_report()


@router.get("/benchmark-intelligence")
async def governance_benchmark_intelligence(
    include_recent: int = 20,
    include_history: bool = True,
    substrate: str = "",
    scenario_type: str = "",
    success_only: bool | None = None,
    created_after: str = "",
    created_before: str = "",
    run_parallel_probe: bool = False,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    include_recent = max(0, min(int(include_recent), 100))
    probe_result: Dict[str, Any] | None = None
    probe_allowed = any(role in user.roles for role in (ROLE_OPERATOR, ROLE_ADMIN))
    if run_parallel_probe:
        if not probe_allowed:
            raise HTTPException(
                status_code=403,
                detail="benchmark_probe_forbidden_requires_operator_or_admin",
            )
        mission_id = f"benchmark-{uuid.uuid4()}"
        probe_result = await run_parallel_execution_benchmark_scenario(
            mission_id=mission_id,
            workflow_id="governance-benchmark",
            program_id="kai-governance",
        )

    records = query_benchmark_records(
        include_latest=True,
        include_history=bool(include_history),
        substrate=substrate,
        scenario_type=scenario_type,
        success=success_only,
        created_after=created_after,
        created_before=created_before,
        limit=max(50, include_recent),
    )
    payload = load_benchmark_payload()
    payload["records"] = records
    payload["summary"] = summarize_benchmark_records(records)
    try:
        report = build_benchmark_intelligence_report(payload=payload, include_recent=include_recent)
    except TypeError:
        # Backward-compatibility path for tests or callsites that monkeypatch the
        # reporter with legacy signature (include_recent only).
        report = build_benchmark_intelligence_report(include_recent=include_recent)
    report["query_policy"] = {
        "include_history": bool(include_history),
        "filters": {
            "substrate": str(substrate or ""),
            "scenario_type": str(scenario_type or ""),
            "success_only": success_only,
            "created_after": str(created_after or ""),
            "created_before": str(created_before or ""),
        },
        "probe_allowed_roles": [ROLE_OPERATOR, ROLE_ADMIN],
        "probe_requested": bool(run_parallel_probe),
        "probe_allowed": bool(probe_allowed),
    }
    if probe_result is not None:
        report["parallel_probe"] = probe_result
    return report
