from __future__ import annotations

from pathlib import Path
import sys
import yaml

REQUIRED_FIELDS = {"id", "metric", "threshold", "benchmark_scenario", "validation_condition"}
ALLOWED_METRICS = {
    "coverage",
    "precision",
    "recall",
    "runtime_seconds",
    "cost_usd",
    "error_rate",
    "retry_rate",
}


def main() -> int:
    path = Path("claims/claims.yaml")
    if not path.exists():
        print("claims registry missing: claims/claims.yaml")
        return 1

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    claims = data.get("claims") or []
    if not isinstance(claims, list) or not claims:
        print("claims registry invalid: 'claims' must be a non-empty list")
        return 1

    ids = set()
    scenarios = set()
    for idx, claim in enumerate(claims, start=1):
        if not isinstance(claim, dict):
            print(f"claim #{idx} must be an object")
            return 1

        missing = REQUIRED_FIELDS - set(claim.keys())
        if missing:
            print(f"claim #{idx} missing required fields: {sorted(missing)}")
            return 1

        claim_id = str(claim["id"])
        if claim_id in ids:
            print(f"duplicate claim id: {claim_id}")
            return 1
        ids.add(claim_id)

        metric = str(claim["metric"])
        if metric not in ALLOWED_METRICS:
            print(f"claim {claim_id} has unsupported metric: {metric}")
            return 1

        scenarios.add(str(claim["benchmark_scenario"]))

    fixtures = Path("tests/fixtures/benchmarks")
    missing_fixtures = [s for s in sorted(scenarios) if not (fixtures / f"{s}.json").exists()]
    if missing_fixtures:
        print("missing benchmark fixtures for scenarios:")
        for scenario in missing_fixtures:
            print(f"- {scenario}")
        return 1

    print(f"claims validation passed ({len(claims)} claims)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
