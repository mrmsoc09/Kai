"""Quality gate checks evidence completeness and policy adherence."""

from pathlib import Path
from typing import Dict, Any
from .lib.io_contracts import HookResult
from .lib.policy_loader import load_policy
from .lib.common import logger

POLICY_ROOT = Path(__file__).resolve().parents[1] / "policies"


def run(payload: Dict[str, Any]) -> HookResult:
    policy = load_policy("report_policy", POLICY_ROOT)
    evidence_ids = payload.get("evidence_ids") or []
    artifacts = payload.get("artifacts") or []
    if not evidence_ids:
        return HookResult(ok=False, reason="missing evidence references", warnings=["policy: report-001"])
    if any("secret" in str(a).lower() for a in artifacts):
        return HookResult(ok=False, reason="potential secret leakage", warnings=["policy: report-002"])
    logger.debug("quality_gate pass evidence_count=%d", len(evidence_ids))
    return HookResult(ok=True, data={"quality": "pass"})
