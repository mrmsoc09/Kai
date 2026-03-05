# Kai Benchmarks

Deterministic benchmark suite for validating platform claims.

## Rules
- No live network scanning.
- Use offline fixtures from `tests/fixtures/benchmarks`.
- Benchmark outputs are reproducible and CI-gated.

## Commands
- Validate claims schema and fixture coverage:
  - `python3 scripts/validate_claims.py`
- Run deterministic benchmark evaluation:
  - `python3 scripts/run_benchmarks.py --verify-claims`

Output artifact:
- `artifacts/benchmarks/latest.json`
