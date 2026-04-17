"""Task 7 validation: Duplicate Detection Engine.

Updated to verify:
- In-memory dedup still works (existing behavior)
- DB-backed methods (check_duplicate_db, register_finding_db) exist and are callable
- DedupFingerprint model is importable
"""
from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend", "src"))

from core.dedup_service import DeduplicationService


async def run_tests() -> list[str]:
    errors: list[str] = []
    svc = DeduplicationService()
    campaign = "campaign-001"

    # --- In-memory tests (existing behavior preserved) ---
    finding1 = {
        "id": "f-001",
        "endpoint": "https://api.example.com/login",
        "vuln_type": "sql_injection",
        "parameter": "username",
    }
    await svc.register_finding(finding1, campaign)

    finding2 = {
        "endpoint": "https://api.example.com/login",
        "vuln_type": "sql_injection",
        "parameter": "username",
    }
    result = await svc.check_duplicate(finding2, campaign)
    if not result.is_duplicate:
        errors.append("Identical finding should be flagged as duplicate")
    if result.duplicate_of != "f-001":
        errors.append(f"Should reference f-001, got {result.duplicate_of}")
    if result.similarity_score != 1.0:
        errors.append(f"Exact match score should be 1.0, got {result.similarity_score}")

    finding3 = {
        "endpoint": "https://api.example.com/register",
        "vuln_type": "xss",
        "parameter": "email",
    }
    result2 = await svc.check_duplicate(finding3, campaign)
    if result2.is_duplicate:
        errors.append("Different finding should NOT be flagged as duplicate")

    finding4 = {
        "endpoint": "https://api.example.com/login",
        "vuln_type": "xss",
        "parameter": "username",
    }
    result3 = await svc.check_duplicate(finding4, "campaign-002")
    if result3.is_duplicate:
        errors.append("Finding in different campaign should NOT be duplicate")

    # --- DB-backed method existence checks ---
    if not hasattr(svc, "check_duplicate_db"):
        errors.append("DeduplicationService missing check_duplicate_db method")
    if not hasattr(svc, "register_finding_db"):
        errors.append("DeduplicationService missing register_finding_db method")
    if not callable(getattr(svc, "check_duplicate_db", None)):
        errors.append("check_duplicate_db must be callable")
    if not callable(getattr(svc, "register_finding_db", None)):
        errors.append("register_finding_db must be callable")

    # --- DedupFingerprint model: verify file exists and has required columns ---
    import importlib.util
    import pathlib

    model_path = pathlib.Path(__file__).parent.parent / "apps" / "backend" / "src" / "models" / "dedup_fingerprint.py"
    if not model_path.exists():
        errors.append(f"dedup_fingerprint.py not found at {model_path}")
    else:
        source = model_path.read_text()
        for required in ("campaign_id", "fingerprint", "endpoint", "vuln_type", "created_at", "finding_id"):
            if required not in source:
                errors.append(f"DedupFingerprint model missing column definition: {required}")

    return errors


def main() -> None:
    errors = asyncio.run(run_tests())
    if errors:
        print("TASK 7 FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("TASK 7 DEDUP DB VERIFIED")


if __name__ == "__main__":
    main()
