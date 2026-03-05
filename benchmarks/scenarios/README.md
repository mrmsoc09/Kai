# Kai Deterministic Benchmark Scenarios

All scenarios in this directory must use offline deterministic fixtures.
No external network calls or live scanning is permitted.

Source fixtures:
- `tests/fixtures/benchmarks/*.json`

Metrics computed by runner:
- coverage = discovered_assets / total_assets
- precision = true_positives / reported_positives
- recall = true_positives / ground_truth
- runtime_seconds = total_execution_time
- cost_usd = llm_cost + api_cost
- error_rate = failed_runs / total_runs
- retry_rate = retries / total_runs
