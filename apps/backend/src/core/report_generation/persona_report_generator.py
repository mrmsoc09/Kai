"""
Per-persona Markdown report generation for vulnerability submissions.
Generates platform-specific reports for HackerOne, Bugcrowd, and Intigriti.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class ReportPersona(str, Enum):
    """Report writing personas."""

    PENETRATION_TESTER = "penetration_tester"
    SECURITY_RESEARCHER = "security_researcher"
    BUG_BOUNTY_HUNTER = "bug_bounty_hunter"


@dataclass
class FindingReport:
    """Structured vulnerability finding report."""

    title: str
    cve_id: Optional[str] = None
    cvss_score: Optional[float] = None
    severity: str = "high"
    target_url: str = ""
    vulnerability_type: str = ""
    description: str = ""
    impact: str = ""
    proof_of_concept: str = ""
    remediation: str = ""
    affected_version: Optional[str] = None
    affected_products: list[str] = None
    evidence_hashes: Dict[str, list[str]] = None

    def __post_init__(self):
        if self.affected_products is None:
            self.affected_products = []
        if self.evidence_hashes is None:
            self.evidence_hashes = {}


class PersonaReportGenerator:
    """
    Generates Markdown reports tailored to specific personas.
    Each persona has different technical depth and formatting preferences.
    """

    def __init__(self):
        """Initialize report generator."""
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, str]:
        """Load persona-specific templates."""
        return {
            ReportPersona.PENETRATION_TESTER.value: (
                self._template_penetration_tester()
            ),
            ReportPersona.SECURITY_RESEARCHER.value: (
                self._template_security_researcher()
            ),
            ReportPersona.BUG_BOUNTY_HUNTER.value: (
                self._template_bug_bounty_hunter()
            ),
        }

    async def generate_report(
        self, finding: FindingReport, persona: ReportPersona
    ) -> str:
        """
        Generate personalized report for finding.

        Args:
            finding: FindingReport object
            persona: Report writing persona

        Returns:
            Markdown report content
        """
        template = self.templates.get(persona.value)
        if not template:
            raise ValueError(f"Unknown persona: {persona}")

        return self._render_template(template, finding)

    def _render_template(
        self, template: str, finding: FindingReport
    ) -> str:
        """Render template with finding data."""
        # Replace placeholders
        content = template

        content = content.replace("{{TITLE}}", finding.title)
        content = content.replace("{{CVE_ID}}", finding.cve_id or "N/A")
        content = content.replace(
            "{{CVSS_SCORE}}", f"{finding.cvss_score}" if finding.cvss_score else "N/A"
        )
        content = content.replace("{{SEVERITY}}", finding.severity.upper())
        content = content.replace("{{TARGET_URL}}", finding.target_url)
        content = content.replace(
            "{{VULNERABILITY_TYPE}}", finding.vulnerability_type
        )
        content = content.replace("{{DESCRIPTION}}", finding.description)
        content = content.replace("{{IMPACT}}", finding.impact)
        content = content.replace(
            "{{PROOF_OF_CONCEPT}}", finding.proof_of_concept
        )
        content = content.replace("{{REMEDIATION}}", finding.remediation)
        content = content.replace(
            "{{AFFECTED_VERSION}}",
            finding.affected_version or "Multiple/Unknown"
        )

        products_list = "\n".join(
            [f"- {p}" for p in finding.affected_products]
        )
        content = content.replace("{{AFFECTED_PRODUCTS}}", products_list)

        # Generate evidence references
        evidence_refs = self._generate_evidence_references(
            finding.evidence_hashes
        )
        content = content.replace(
            "{{EVIDENCE_REFERENCES}}", evidence_refs
        )

        return content

    def _generate_evidence_references(
        self, evidence_hashes: Dict[str, list[str]]
    ) -> str:
        """Generate evidence references section."""
        if not evidence_hashes:
            return "No evidence attached"

        refs = []
        for evidence_type, hashes in evidence_hashes.items():
            refs.append(f"\n### {evidence_type.replace('_', ' ').title()}")
            for i, hash_val in enumerate(hashes, 1):
                refs.append(f"{i}. `{hash_val[:16]}...` (See attached)")

        return "\n".join(refs)

    @staticmethod
    def _template_penetration_tester() -> str:
        """Template for penetration tester persona."""
        return """# {{TITLE}}

## Vulnerability Summary

| Field | Value |
|-------|-------|
| **CVE ID** | {{CVE_ID}} |
| **CVSS Score** | {{CVSS_SCORE}} |
| **Severity** | {{SEVERITY}} |
| **Target** | {{TARGET_URL}} |
| **Type** | {{VULNERABILITY_TYPE}} |

## Technical Details

### Description

{{DESCRIPTION}}

### Affected Products

{{AFFECTED_PRODUCTS}}

### Affected Versions

{{AFFECTED_VERSION}}

## Exploitation

### Vulnerability Analysis

The vulnerability can be exploited through the following attack vector:

{{PROOF_OF_CONCEPT}}

### Attack Chain

1. Initial reconnaissance identifies the affected component
2. Crafted input triggers the vulnerability condition
3. Attacker gains unauthorized access/code execution
4. Post-exploitation activities follow

### Impact Assessment

{{IMPACT}}

## Evidence

### Proof of Concept

The vulnerability was successfully reproduced and exploited:

{{EVIDENCE_REFERENCES}}

## Remediation

### Recommended Fixes

{{REMEDIATION}}

### Mitigation Strategies

1. Immediate: Apply security patches
2. Short-term: Implement input validation and sanitization
3. Long-term: Adopt secure development practices

---

*Report Generated: {{TIMESTAMP}}*
*Classification: Technical Security Assessment*
"""

    @staticmethod
    def _template_security_researcher() -> str:
        """Template for security researcher persona."""
        return """# {{TITLE}}

## Executive Summary

This report documents the discovery and analysis of {{CVE_ID}}, a {{VULNERABILITY_TYPE}}
vulnerability affecting {{AFFECTED_PRODUCTS}}.

## Vulnerability Details

**CVE Identifier**: {{CVE_ID}}
**CVSS v3.1 Score**: {{CVSS_SCORE}}
**Severity Level**: {{SEVERITY}}
**Affected Product(s)**: {{AFFECTED_PRODUCTS}}
**Affected Version(s)**: {{AFFECTED_VERSION}}

## Technical Analysis

### Background

{{DESCRIPTION}}

### Root Cause Analysis

The vulnerability stems from insufficient input validation in the affected component.
The root cause is a failure to properly sanitize user-controlled input before processing.

### Proof of Concept

{{PROOF_OF_CONCEPT}}

## Impact and Consequences

### Confidentiality Impact

{{IMPACT}}

### Integrity Impact

Successful exploitation could allow attackers to modify data within the affected system.

### Availability Impact

The vulnerability could potentially lead to denial of service conditions.

## Exploitation Metrics

- **Attack Vector**: Network
- **Attack Complexity**: Low
- **Privileges Required**: None
- **User Interaction**: None
- **Scope**: Changed

## Remediation Recommendations

### For Developers

{{REMEDIATION}}

### For System Administrators

1. Update affected software immediately upon patch availability
2. Monitor systems for exploitation attempts
3. Review access logs for suspicious activity

### For Security Teams

- Coordinate vendor notification and patch release
- Develop detection signatures for exploitation attempts
- Plan rollout of security updates across infrastructure

## Evidence and References

{{EVIDENCE_REFERENCES}}

## Conclusion

This vulnerability represents a significant security risk and should be prioritized
for remediation. The techniques demonstrated in this report provide clear evidence
of exploitability.

---

*Technical Report*
*Researcher: Security Analysis Team*
*Date: {{TIMESTAMP}}*
"""

    @staticmethod
    def _template_bug_bounty_hunter() -> str:
        """Template for bug bounty hunter persona."""
        return """# Vulnerability Report: {{TITLE}}

## Quick Summary

Found a {{SEVERITY}} {{VULNERABILITY_TYPE}} in {{TARGET_URL}}.

**CVE**: {{CVE_ID}} | **CVSS**: {{CVSS_SCORE}}/10

## What's the Issue?

{{DESCRIPTION}}

## Affected Targets

- **Primary Target**: {{TARGET_URL}}
- **Affected Components**: {{AFFECTED_PRODUCTS}}
- **Affected Versions**: {{AFFECTED_VERSION}}

## How I Found It

Here's how to reproduce this vulnerability:

{{PROOF_OF_CONCEPT}}

## Why Is This Dangerous?

{{IMPACT}}

## Proof

I've included the following evidence:

{{EVIDENCE_REFERENCES}}

All evidence files are attached and ready for verification.

## How to Fix It

{{REMEDIATION}}

## Timeline

- **Discovery Date**: {{TIMESTAMP}}
- **Report Date**: {{TIMESTAMP}}
- **Status**: Awaiting Acknowledgment

## Additional Notes

This vulnerability was discovered through systematic security research and testing.
I have not disclosed this to any other parties and am submitting it exclusively
to your bug bounty program.

---

**Report submitted to bug bounty program**
"""

    @staticmethod
    def get_supported_personas() -> list[str]:
        """Get list of supported personas."""
        return [p.value for p in ReportPersona]
