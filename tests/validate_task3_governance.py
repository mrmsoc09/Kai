"""Task 3 validation: Tool Governance + Risk Bands.

Updated to verify that Band 2 with a FAKE gate_id (not in DB) is REJECTED,
not silently approved.
"""
from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend", "src"))

from core.tool_risk_registry import get_tool_band
from core.tool_governance_service import ToolGovernanceService


async def run_tests() -> list[str]:
    errors: list[str] = []
    svc = ToolGovernanceService()

    # 1. whois -> Band 0 -> allowed, no approval (no db needed)
    r = await svc.check_tool_authorization("whois", "campaign-1", db=None)
    if not r.allowed:
        errors.append("whois should be allowed")
    if r.band != 0:
        errors.append(f"whois should be band 0, got {r.band}")
    if r.requires_approval:
        errors.append("whois should not require approval")

    # 2. ffuf -> Band 2 -> not allowed without gate
    r = await svc.check_tool_authorization("ffuf", "campaign-1", db=None)
    if r.allowed:
        errors.append("ffuf without gate should not be allowed")
    if r.band != 2:
        errors.append(f"ffuf should be band 2, got {r.band}")
    if not r.requires_approval:
        errors.append("ffuf should require approval")

    # 3. CRITICAL: Band 2 with a FAKE gate_id and no db must be REJECTED (not approved)
    # This is the security fix: a bare UUID is never trusted without a DB check
    r = await svc.check_tool_authorization(
        "ffuf", "campaign-1", db=None, existing_gate_id="fake-gate-uuid-that-does-not-exist"
    )
    if r.allowed:
        errors.append(
            "SECURITY BUG: ffuf with a fake gate_id and no db must be REJECTED, not approved"
        )
    if not r.requires_approval:
        errors.append("ffuf with unverified gate should still require_approval=True")

    # 4. is_approved with None gate_id returns False (no crash)
    approved = await svc.is_approved(None, db=None)
    if approved:
        errors.append("is_approved(None, None) should return False")

    # 5. metasploit -> Band 3 -> blocked
    r = await svc.check_tool_authorization("metasploit", "campaign-1", db=None)
    if r.allowed:
        errors.append("metasploit should be blocked")
    if r.band != 3:
        errors.append(f"metasploit should be band 3, got {r.band}")
    if r.requires_approval:
        errors.append("metasploit should not require approval (blocked entirely)")
    if r.reason != "Band 3 tools blocked":
        errors.append(f"metasploit reason should be 'Band 3 tools blocked', got '{r.reason}'")

    # 6. Unknown tool defaults to band 2
    band = get_tool_band("unknown_tool_xyz")
    if band != 2:
        errors.append(f"Unknown tool should default to band 2, got {band}")

    return errors


def main() -> None:
    errors = asyncio.run(run_tests())
    if errors:
        print("TASK 3 FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("TASK 3 GOVERNANCE FIX VERIFIED")


if __name__ == "__main__":
    main()
