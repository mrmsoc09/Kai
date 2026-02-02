from __future__ import annotations
from typing import Dict, Any, List

REQUIRED_COMMON = ["Summary", "Impact", "Steps to Reproduce", "Evidence", "Mitigation"]

STAKEHOLDER_RULES = {
    "google_vrp": {
        "required_sections": REQUIRED_COMMON + ["Timeline"],
        "multipliers": ["format compliance", "duplicate check", "safe repro video"],
    },
    "hackerone": {
        "required_sections": REQUIRED_COMMON + ["References"],
        "multipliers": ["CWE included", "CVSS provided"],
    },
    "bugcrowd": {
        "required_sections": REQUIRED_COMMON + ["Attack Scenario"],
        "multipliers": ["attack narrative clarity"],
    },
}


def validate_rendered(stakeholder: str, content: str, run_id: str | None = None, has_recording: bool = False) -> Dict[str, Any]:
    rules = STAKEHOLDER_RULES.get(stakeholder, {"required_sections": REQUIRED_COMMON})
    missing: List[str] = []
    for sec in rules.get("required_sections", []):
        if f"## {sec}" not in content and not content.strip().startswith(f"# {sec}"):
            missing.append(sec)
    issues: List[str] = []
    if not has_recording:
        issues.append("screen_recording_missing")
    ok = not missing and not issues
    return {
        "ok": ok,
        "missing_sections": missing,
        "issues": issues,
        "stakeholder": stakeholder,
        "advice": rules.get("multipliers", []),
    }
