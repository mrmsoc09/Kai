# Changelog

## 2026-02-26
- Hardened HiL approval workflow to return `409 Conflict` on duplicate approvals and avoid concurrent double-writes (`apps/backend/src/routers/hil_workflow.py`).
- Added optional concurrency regression test (`tests/test_hil_concurrency.py`) guarded by `K1_RUN_DB_TESTS=true` for environments with a live database.
- Verified dependency set against Python 3.11 in a temporary venv; pin set already uses `ollama>=0.3.0` and `llama-index>=0.14.15` to avoid earlier conflicts.
- Added reproducibility scoring support: new scorer utility (`apps/backend/src/core/reproducibility_scorer.py`), `reproducibility_score` column via Alembic migration `0002_add_reproducibility_score.py`, scoring endpoint + evidence hook in HiL findings router, and unit tests (`tests/test_reproducibility.py`).
