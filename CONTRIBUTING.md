# Contributing to Kai / K1

Thanks for contributing. Keep changes small, testable, and honest about what is implemented.

## Development Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-dev.txt
```

3. Run backend quality checks:

```bash
bash scripts/check_backend_quality.sh
```

Optional type-check pass:

```bash
python3 -m mypy apps/backend/src/core apps/backend/src/routers/campaigns.py apps/backend/src/schemas/campaigns.py
```

## Running Tests

Full suite:

```bash
python3 -m pytest -q
```

Focused suites:

```bash
python3 -m pytest -q tests/test_campaign*
python3 -m pytest -q tests/test_finding*
python3 -m pytest -q tests/test_submission_export_adapters.py
```

## Coding Standards

- Python style is enforced with `ruff`, `black`, and `isort`.
- Keep API contracts explicit and stable (`response_model`, clear status codes).
- Do not claim behavior that is not implemented.
- Prefer deterministic, auditable service logic.
- Add or update tests for every behavior change.

## Pull Requests

Before opening a PR:

1. Rebase on the latest default branch.
2. Run `bash scripts/check_backend_quality.sh`.
3. Update docs for any contract or workflow change.
4. Keep PR scope focused; avoid unrelated refactors.

PRs should include:

- summary of behavioral changes
- test evidence (commands + results)
- any known risks or follow-up work
