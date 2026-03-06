from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List
import argparse
import json
import yaml


@dataclass
class BenchmarkResult:
    scenario: str
    metrics: Dict[str, float]


def compute_metrics(payload: Dict[str, Any]) -> Dict[str, float]:
    discovered_assets = float(payload.get("discovered_assets", 0))
    total_assets = float(payload.get("total_assets", 1))
    reported_positives = float(payload.get("reported_positives", 1))
    true_positives = float(payload.get("true_positives", 0))
    ground_truth = float(payload.get("ground_truth", 1))
    total_execution_time = float(payload.get("total_execution_time", 0))
    llm_cost = float(payload.get("llm_cost", 0))
    api_cost = float(payload.get("api_cost", 0))
    failed_runs = float(payload.get("failed_runs", 0))
    retries = float(payload.get("retries", 0))
    total_runs = float(payload.get("total_runs", 1))
    reports_submitted = float(payload.get("reports_submitted", 0))
    reports_accepted = float(payload.get("reports_accepted", 0))
    gross_payout_usd = float(payload.get("gross_payout_usd", 0))
    operating_cost_usd = float(payload.get("operating_cost_usd", 0))
    net_payout_usd = gross_payout_usd - operating_cost_usd

    return {
        "coverage": discovered_assets / max(total_assets, 1.0),
        "precision": true_positives / max(reported_positives, 1.0),
        "recall": true_positives / max(ground_truth, 1.0),
        "runtime_seconds": total_execution_time,
        "cost_usd": llm_cost + api_cost,
        "error_rate": failed_runs / max(total_runs, 1.0),
        "retry_rate": retries / max(total_runs, 1.0),
        "accepted_rate": reports_accepted / max(reports_submitted, 1.0),
        "payout_efficiency": net_payout_usd / max(operating_cost_usd, 1.0),
    }


def load_claims(path: Path) -> List[Dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("claims") or [])


def evaluate_claim(metrics: Dict[str, float], claim: Dict[str, Any]) -> bool:
    comparator = str(claim.get("comparator") or ">=").strip()
    metric_name = str(claim["metric"])
    threshold = float(claim["threshold"])
    value = float(metrics[metric_name])

    if comparator == ">=":
        return value >= threshold
    if comparator == "<=":
        return value <= threshold
    raise ValueError(f"unsupported comparator: {comparator}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Kai benchmarks.")
    parser.add_argument("--claims", default="claims/claims.yaml")
    parser.add_argument("--fixtures", default="tests/fixtures/benchmarks")
    parser.add_argument("--output", default="artifacts/benchmarks/latest.json")
    parser.add_argument("--verify-claims", action="store_true")
    args = parser.parse_args()

    claims_path = Path(args.claims)
    fixtures_dir = Path(args.fixtures)
    output_path = Path(args.output)

    claims = load_claims(claims_path)
    results: List[Dict[str, Any]] = []
    failures: List[str] = []

    for claim in claims:
        scenario = str(claim["benchmark_scenario"])
        fixture_path = fixtures_dir / f"{scenario}.json"
        if not fixture_path.exists():
            failures.append(f"missing fixture for scenario: {scenario}")
            continue

        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        metrics = compute_metrics(payload)
        passed = evaluate_claim(metrics, claim)
        results.append(
            {
                "claim_id": claim["id"],
                "scenario": scenario,
                "metric": claim["metric"],
                "threshold": claim["threshold"],
                "comparator": claim.get("comparator", ">="),
                "value": round(metrics[str(claim["metric"])], 6),
                "passed": bool(passed),
            }
        )
        if not passed:
            failures.append(f"claim failed: {claim['id']}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "total_claims": len(results),
        "failed_claims": len([r for r in results if not r["passed"]]),
        "results": results,
    }
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"benchmark summary written: {output_path}")

    if args.verify_claims and failures:
        print("benchmark verification failed:")
        for item in failures:
            print(f"- {item}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
