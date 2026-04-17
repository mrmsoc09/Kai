"""Task 4 validation: Opportunity + Program Ingestion."""
from __future__ import annotations

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend", "src"))

from core.program_ingestion_service import ProgramIngestionService


def main() -> None:
    errors: list[str] = []
    svc = ProgramIngestionService()

    # Mock H1 payload with 3 in-scope domains, 1 out-of-scope domain, 1 wildcard
    payload = {
        "handle": "test-program",
        "platform": "hackerone",
        "in_scope": [
            {"asset_identifier": "api.example.com", "asset_type": "URL"},
            {"asset_identifier": "www.example.com", "asset_type": "URL"},
            {"asset_identifier": "shop.example.com", "asset_type": "URL"},
            {"asset_identifier": "*.example.com", "asset_type": "WILDCARD"},
            {"asset_identifier": "Company Hardware", "asset_type": "HARDWARE"},
        ],
        "out_of_scope": [
            {"asset_identifier": "admin.example.com", "asset_type": "URL"},
        ],
    }

    program = svc.ingest_from_hackerone_payload(payload)

    if program.program_handle != "test-program":
        errors.append(f"Expected handle 'test-program', got '{program.program_handle}'")

    if len(program.in_scope_assets) != 5:
        errors.append(f"Expected 5 in_scope_assets, got {len(program.in_scope_assets)}")

    if len(program.out_of_scope_assets) != 1:
        errors.append(f"Expected 1 out_of_scope_assets, got {len(program.out_of_scope_assets)}")

    # Derive targets - should exclude hardware and out-of-scope admin
    targets = svc.derive_scan_targets(program)

    # Expected: api.example.com, www.example.com, shop.example.com, *.example.com
    # admin.example.com is out-of-scope, Company Hardware is non-scannable
    if len(targets) != 4:
        errors.append(f"Expected 4 scan targets, got {len(targets)}: {targets}")

    if "api.example.com" not in targets:
        errors.append("api.example.com should be in targets")

    if "admin.example.com" in targets:
        errors.append("admin.example.com should NOT be in targets (out of scope)")

    # Schedule
    schedule = svc.schedule_program(program, interval_hours=12)
    if schedule["program_handle"] != "test-program":
        errors.append(f"Schedule handle mismatch: {schedule['program_handle']}")
    if schedule["targets_count"] != 4:
        errors.append(f"Expected 4 targets in schedule, got {schedule['targets_count']}")

    next_run = datetime.fromisoformat(schedule["next_run_at"])
    if next_run <= datetime.now(timezone.utc):
        errors.append("next_run_at should be in the future")

    if errors:
        print("TASK 4 FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("TASK 4 PASSED")


if __name__ == "__main__":
    main()
