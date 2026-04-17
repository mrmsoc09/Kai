"""Task 3 validation: Tool Governance + Risk Bands."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend", "src"))

from core.tool_risk_registry import get_tool_band
from core.tool_governance_service import ToolGovernanceService


def main() -> None:
    errors: list[str] = []
    svc = ToolGovernanceService()

    # 1. whois -> Band 0 -> allowed, no approval
    r = svc.check_tool_authorization("whois", "campaign-1")
    if not r.allowed:
        errors.append("whois should be allowed")
    if r.band != 0:
        errors.append(f"whois should be band 0, got {r.band}")
    if r.requires_approval:
        errors.append("whois should not require approval")

    # 2. ffuf -> Band 2 -> not allowed without gate, requires approval
    r = svc.check_tool_authorization("ffuf", "campaign-1")
    if r.allowed:
        errors.append("ffuf without gate should not be allowed")
    if r.band != 2:
        errors.append(f"ffuf should be band 2, got {r.band}")
    if not r.requires_approval:
        errors.append("ffuf should require approval")

    # 2b. ffuf with approved gate -> allowed
    r = svc.check_tool_authorization("ffuf", "campaign-1", existing_gate_id="gate-123")
    if not r.allowed:
        errors.append("ffuf with approved gate should be allowed")

    # 3. metasploit -> Band 3 -> blocked
    r = svc.check_tool_authorization("metasploit", "campaign-1")
    if r.allowed:
        errors.append("metasploit should be blocked")
    if r.band != 3:
        errors.append(f"metasploit should be band 3, got {r.band}")
    if r.requires_approval:
        errors.append("metasploit should not require approval (blocked entirely)")
    if r.reason != "Band 3 tools blocked":
        errors.append(f"metasploit reason should be 'Band 3 tools blocked', got '{r.reason}'")

    # 4. Unknown tool defaults to band 2
    band = get_tool_band("unknown_tool_xyz")
    if band != 2:
        errors.append(f"Unknown tool should default to band 2, got {band}")

    if errors:
        print("TASK 3 FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("TASK 3 PASSED")


if __name__ == "__main__":
    main()
