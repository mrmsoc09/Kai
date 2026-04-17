"""Task 1 validation: Scope Enforcement Engine."""
from __future__ import annotations

import sys
import os

# Ensure the backend source is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend", "src"))

from core.scope_ingestion_service import (
    NormalizedScope,
    ProgramScopeIngestion,
    ScopeEnforcementGate,
)


def main() -> None:
    errors: list[str] = []

    # Build scope
    scope = NormalizedScope(
        allowed=["example.com", "*.example.com"],
        denied=["admin.example.com"],
    )
    gate = ScopeEnforcementGate()

    # 1. api.example.com should be in scope (matches *.example.com)
    if not gate.check_target("api.example.com", scope):
        errors.append("api.example.com should be in scope")

    # 2. evil.com should be out of scope
    if gate.check_target("evil.com", scope):
        errors.append("evil.com should be out of scope")

    # 3. admin.example.com should be blocked by denylist
    if gate.check_target("admin.example.com", scope):
        errors.append("admin.example.com should be blocked by denylist")

    # Bonus: test ingestion from H1-style payload
    ingestion = ProgramScopeIngestion()
    payload = {
        "in_scope": [
            {"asset_identifier": "example.com", "asset_type": "DOMAIN"},
            {"asset_identifier": "*.example.com", "asset_type": "WILDCARD"},
        ],
        "out_of_scope": [
            {"asset_identifier": "admin.example.com", "asset_type": "URL"},
        ],
    }
    ns = ingestion.ingest_hackerone_payload(payload)
    assert len(ns.allowed) == 2, f"Expected 2 allowed, got {len(ns.allowed)}"
    assert len(ns.denied) == 1, f"Expected 1 denied, got {len(ns.denied)}"

    if errors:
        print("TASK 1 FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("TASK 1 PASSED")


if __name__ == "__main__":
    main()
