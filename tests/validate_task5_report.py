"""Task 5 validation: Report Generation Engine."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend", "src"))

from core.report_generation_service import ReportGenerationService, estimate_severity


def main() -> None:
    errors: list[str] = []
    svc = ReportGenerationService()

    # Build mock finding
    finding = {
        "title": "SQL Injection in Login Form",
        "description": "The login endpoint is vulnerable to SQL injection via the username parameter.",
        "asset": "https://api.example.com/login",
        "vulnerability_type": "SQL Injection",
        "cvss_score": 9.8,
        "impact": "An attacker can bypass authentication and extract database contents.",
        "references": ["https://cwe.mitre.org/data/definitions/89.html"],
    }

    evidence_list = [
        {
            "artifact_uri": "s3://evidence/sqli-proof.png",
            "evidence_type": "screenshot",
            "summary": "Screenshot showing SQL error response",
        }
    ]

    report = svc.generate_hackerone_report(
        finding, evidence_list=evidence_list, reproduction_steps="1. Send payload\n2. Observe error"
    )

    # Check all 6 section headers
    required_sections = [
        "## Summary",
        "## Vulnerability Details",
        "## Steps to Reproduce",
        "## Impact",
        "## Evidence",
        "## References",
    ]
    for section in required_sections:
        if section not in report:
            errors.append(f"Missing section header: {section}")

    # Check content
    if "SQL Injection" not in report:
        errors.append("Report should contain vulnerability type")
    if "s3://evidence/sqli-proof.png" not in report:
        errors.append("Report should contain evidence URI")

    # Severity mapping
    cases = [
        (9.5, "critical"),
        (7.0, "high"),
        (4.0, "medium"),
        (1.0, "low"),
        (0.0, "none"),
    ]
    for cvss, expected in cases:
        result = estimate_severity(cvss)
        if result != expected:
            errors.append(f"estimate_severity({cvss}) = '{result}', expected '{expected}'")

    if errors:
        print("TASK 5 FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("TASK 5 PASSED")


if __name__ == "__main__":
    main()
