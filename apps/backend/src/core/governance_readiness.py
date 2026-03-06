from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import yaml

from scripts import check_toolpack_adapter_compat, check_unmanaged_secrets


def _claims_status(claims_path: Path) -> Dict[str, Any]:
    if not claims_path.exists():
        return {"ok": False, "reason": "claims_registry_missing"}
    try:
        payload = yaml.safe_load(claims_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return {"ok": False, "reason": f"claims_registry_parse_error:{exc}"}
    claims = payload.get("claims")
    if not isinstance(claims, list) or not claims:
        return {"ok": False, "reason": "claims_registry_empty"}
    return {"ok": True, "claims_count": len(claims)}


def _benchmark_status(benchmark_path: Path) -> Dict[str, Any]:
    if not benchmark_path.exists():
        return {"ok": False, "reason": "benchmark_summary_missing"}
    try:
        payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "reason": f"benchmark_summary_parse_error:{exc}"}

    failed_claims = int(payload.get("failed_claims") or 0)
    total_claims = int(payload.get("total_claims") or 0)
    return {
        "ok": failed_claims == 0 and total_claims > 0,
        "failed_claims": failed_claims,
        "total_claims": total_claims,
    }


def build_governance_readiness_report(
    *,
    claims_path: str = "claims/claims.yaml",
    benchmark_path: str = "artifacts/benchmarks/latest.json",
) -> Dict[str, Any]:
    claims = _claims_status(Path(claims_path))
    benchmark = _benchmark_status(Path(benchmark_path))
    toolpacks_ok = check_toolpack_adapter_compat.main() == 0
    secrets_ok = check_unmanaged_secrets.main() == 0

    components = {
        "claims_registry": claims,
        "benchmark_summary": benchmark,
        "toolpack_adapter_compatibility": {"ok": toolpacks_ok},
        "unmanaged_secret_reads": {"ok": secrets_ok},
    }
    overall_ok = all(bool(part.get("ok")) for part in components.values())
    return {"status": "ready" if overall_ok else "not_ready", "ok": overall_ok, "components": components}
