from __future__ import annotations
from typing import Dict, Any

TEMPLATES = {
    "google_vrp": {
        "subject": "[VRP] {title} — {severity}",
        "body": (
            "Hello VRP Team,\n\n"
            "Please find the report attached/included below.\n\n"
            "Title: {title}\n"
            "Severity: {severity}\n"
            "Scope: {scope}\n\n"
            "Summary:\n{summary}\n\n"
            "Mitigation Plan (proposed):\n{mitigation}\n\n"
            "Evidence: Screen recording available and included in artifacts.\n\n"
            "Best,\nK1 Operator"
        ),
    },
    "hackerone": {
        "subject": "[H1] {title} ({severity})",
        "body": "Hi Team,\n\n{summary}\n\nMitigation: {mitigation}\n\nRegards,\nK1",
    },
    "bugcrowd": {
        "subject": "[Bugcrowd] {title} — {severity}",
        "body": "Hello,\n\n{summary}\n\nMitigation: {mitigation}\n\nThanks,\nK1",
    },
}


def list_templates() -> Dict[str, Any]:
    return {k: {"subject": v["subject"]} for k, v in TEMPLATES.items()}


def render(stakeholder: str, ctx: Dict[str, Any]) -> Dict[str, str]:
    t = TEMPLATES.get(stakeholder)
    if not t:
        return {"subject": ctx.get("title", "Bug Report"), "body": ctx.get("summary", "")}
    return {
        "subject": t["subject"].format(**ctx),
        "body": t["body"].format(**ctx),
    }
