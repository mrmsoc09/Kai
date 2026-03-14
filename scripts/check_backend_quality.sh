#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-all}"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  PYTHON_BIN="${PYTHON_BIN}"
elif python3 -m ruff --version >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif /usr/bin/python3 -m ruff --version >/dev/null 2>&1; then
  PYTHON_BIN="/usr/bin/python3"
else
  PYTHON_BIN="python3"
fi

LINT_PATHS=(
  "apps/backend/src/core/approval_gate_service.py"
  "apps/backend/src/core/branch_scheduler.py"
  "apps/backend/src/core/execution_result_service.py"
  "apps/backend/src/core/finding_correlation_service.py"
  "apps/backend/src/core/finding_review_service.py"
  "apps/backend/src/core/metrics_service.py"
  "apps/backend/src/core/review_queue_service.py"
  "apps/backend/src/core/submission_export_service.py"
  "apps/backend/src/core/submission_package_service.py"
  "apps/backend/src/core/submission_adapters/__init__.py"
  "apps/backend/src/core/submission_adapters/base.py"
  "apps/backend/src/core/submission_adapters/bugcrowd.py"
  "apps/backend/src/core/submission_adapters/hackerone.py"
  "apps/backend/src/core/submission_adapters/intigriti.py"
  "apps/backend/src/routers/campaigns.py"
  "apps/backend/src/schemas/campaigns.py"
  "tests/test_campaign_orchestration.py"
  "tests/test_campaign_result_ingestion.py"
  "tests/test_finding_correlation.py"
  "tests/test_finding_review.py"
  "tests/test_submission_export_adapters.py"
  "tests/test_idempotency_and_diagnostics.py"
)

run_lint() {
  echo "==> ruff check"
  "${PYTHON_BIN}" -m ruff check "${LINT_PATHS[@]}"
  echo "==> black --check"
  for path in "${LINT_PATHS[@]}"; do
    "${PYTHON_BIN}" -m black -W 1 --check "${path}"
  done
  echo "==> isort --check-only"
  for path in "${LINT_PATHS[@]}"; do
    "${PYTHON_BIN}" -m isort --check-only "${path}"
  done
}

run_tests() {
  echo "==> pytest"
  "${PYTHON_BIN}" -m pytest -q
}

case "$MODE" in
  --lint-only)
    run_lint
    ;;
  --tests-only)
    run_tests
    ;;
  all)
    run_lint
    run_tests
    ;;
  *)
    echo "Usage: $0 [--lint-only|--tests-only]"
    exit 2
    ;;
esac
