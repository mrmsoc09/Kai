"""Task 7 validation: Duplicate Detection Engine."""
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

    # Register first finding
    finding1 = {
        "id": "f-001",
        "endpoint": "https://api.example.com/login",
        "vuln_type": "sql_injection",
        "parameter": "username",
    }
    await svc.register_finding(finding1, campaign)

    # Check identical finding -> should be duplicate
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

    # Check completely different finding -> not duplicate
    finding3 = {
        "endpoint": "https://api.example.com/register",
        "vuln_type": "xss",
        "parameter": "email",
    }
    result2 = await svc.check_duplicate(finding3, campaign)
    if result2.is_duplicate:
        errors.append("Different finding should NOT be flagged as duplicate")

    # Check same endpoint different vuln_type in a fresh campaign -> not exact dup
    finding4 = {
        "endpoint": "https://api.example.com/login",
        "vuln_type": "xss",
        "parameter": "username",
    }
    # In a different campaign, should not be duplicate
    result3 = await svc.check_duplicate(finding4, "campaign-002")
    if result3.is_duplicate:
        errors.append("Finding in different campaign should NOT be duplicate")

    return errors


def main() -> None:
    errors = asyncio.run(run_tests())
    if errors:
        print("TASK 7 FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("TASK 7 PASSED")


if __name__ == "__main__":
    main()
