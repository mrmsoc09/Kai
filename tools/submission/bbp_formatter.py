"""
BBP Submission Formatter
Platform-specific formatters for HackerOne, Bugcrowd, and self-hosted programs
"""
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum

class Platform(Enum):
    HACKERONE = "hackerone"
    BUGCROWD = "bugcrowd"
    SELF_HOSTED = "self_hosted"

@dataclass
class FormattedSubmission:
    platform: str
    title: str
    body: str
    severity: str
    metadata: Dict[str, Any]

class BBPSubmissionFormatter:
    """
    Formats vulnerability reports for specific BBP platforms.
    Optimizes presentation for maximum bounty potential.
    """

    TEMPLATES = {
        Platform.HACKERONE: {
            "structure": [
                "## Summary",
                "## Steps To Reproduce",
                "## Impact", 
                "## Mitigation",
                "## References"
            ],
            "severity_map": {
                "critical": "critical",
                "high": "high", 
                "medium": "medium",
                "low": "low"
            }
        },
        Platform.BUGCROWD: {
            "structure": [
                "## Description",
                "## Proof of Concept",
                "## Impact",
                "## Remediation",
                "## CVSS Score"
            ],
            "severity_map": {
                "critical": "5",
                "high": "4",
                "medium": "3", 
                "low": "2"
            }
        }
    }

    @classmethod
    def format_for_platform(cls, finding: Dict, platform: Platform,
                           bbp_mode: str = "public_bbp") -> FormattedSubmission:
        """
        Format a finding for specific BBP platform submission.

        Args:
            finding: Normalized vuln finding
            platform: Target platform (HackerOne, Bugcrowd, etc)
            bbp_mode: public_bbp, private_contract, enterprise_audit
        """
        template = cls.TEMPLATES.get(platform, cls.TEMPLATES[Platform.HACKERONE])

        # Build sections
        sections = []

        for section in template["structure"]:
            if section == "## Summary":
                content = cls._build_summary(finding, bbp_mode)
            elif section in ["## Steps To Reproduce", "## Proof of Concept"]:
                content = cls._build_poc(finding)
            elif section == "## Impact":
                content = cls._build_impact(finding, bbp_mode)
            elif section in ["## Mitigation", "## Remediation"]:
                content = cls._build_remediation(finding)
            elif section == "## CVSS Score":
                content = f"CVSS: {finding.get('cvss', 'N/A')}"
            else:
                content = ""

            sections.append(f"{section}\n{content}\n")

        body = "\n".join(sections)

        return FormattedSubmission(
            platform=platform.value,
            title=cls._build_title(finding),
            body=body,
            severity=template["severity_map"].get(
                finding.get("severity", "medium"), "medium"),
            metadata={
                "cwe_id": finding.get("cwe_id"),
                "cvss": finding.get("cvss"),
                "bounty_estimate": cls._estimate_bounty(finding, platform),
                "autocomplete_hints": cls._autocomplete_hints(finding, platform)
            }
        )

    @classmethod
    def _build_title(cls, finding: Dict) -> str:
        """Construct compelling title for maximum reviewer attention."""
        vuln_type = finding.get("type", "Vulnerability").upper()
        target = finding.get("target", "Application")

        # Impact-focused titles get faster triage
        impact_phrases = {
            "rce": "Remote Code Execution",
            "sqli": "SQL Injection", 
            "xss": "Cross-Site Scripting",
            "idor": "IDOR - Access Control Bypass",
            "ssrf": "Server-Side Request Forgery",
            "auth_bypass": "Authentication Bypass"
        }

        impact = impact_phrases.get(finding.get("type", "").lower(), vuln_type)
        return f"[{impact}] {vuln_type} in {target}"

    @classmethod
    def _build_summary(cls, finding: Dict, mode: str) -> str:
        """Write executive summary optimized for the BBP mode."""
        if mode == "public_bbp":
            # Quick impact statement for public programs
            return f"""
A {finding.get('severity', 'medium')} severity {finding.get('type', 'vulnerability')} 
was identified in {finding.get('target', 'the target')}. 

**Impact:** {finding.get('impact', 'Attackers may exploit this vulnerability')}

**Quick Win:** This finding is easily exploitable and presents immediate risk.
""".strip()
        else:
            # Detailed for private/enterprise
            return f"""
During security assessment of {finding.get('target', 'the target')}, 
a {finding.get('severity', 'medium')} severity {finding.get('type', 'vulnerability')} 
was identified.

**Technical Details:**
- CWE: {finding.get('cwe_id', 'Unknown')}
- CVSS: {finding.get('cvss', 'N/A')}
- Location: {finding.get('location', 'See reproduction steps')}

**Business Impact:**
{finding.get('impact', 'This vulnerability could lead to data compromise')}
""".strip()

    @classmethod
    def _build_poc(cls, finding: Dict) -> str:
        """Build proof of concept with clear reproduction steps."""
        steps = finding.get("poc_steps", [])

        if not steps:
            # Generate generic steps if none provided
            steps = [
                f"1. Navigate to {finding.get('target', 'target endpoint')}",
                f"2. Identify {finding.get('type', 'vulnerability')} injection point",
                "3. Submit malicious payload",
                "4. Observe vulnerability trigger"
            ]

        poc = "\n".join(steps)

        # Add payload example if available
        if finding.get("payload"):
            poc += f"\n\n**Payload Used:**\n```\n{finding['payload']}\n```"

        # Add screenshot/video suggestion
        poc += "\n\n**Evidence:** [Attach screenshot showing vulnerability]"

        return poc

    @classmethod  
    def _build_impact(cls, finding: Dict, mode: str) -> str:
        """Describe security and business impact."""
        impact = finding.get("impact", "")

        if not impact:
            # Generate based on vuln type
            impacts = {
                "rce": "An attacker can execute arbitrary code on the server, leading to full system compromise.",
                "sqli": "Database access allows data exfiltration, modification, or deletion.",
                "xss": "Session hijacking, credential theft, or malicious actions on behalf of users.",
                "idor": "Unauthorized access to other users' data or administrative functions.",
                "ssrf": "Internal network access, cloud metadata exploitation, or lateral movement."
            }
            impact = impacts.get(finding.get("type", "").lower(), 
                               "This vulnerability presents security risk to the application.")

        # Add business context for enterprise
        if mode == "enterprise_audit"::
            impact += "\n\n**Compliance Impact:** This finding may affect SOC 2, ISO 27001, or PCI-DSS compliance requirements."

        return impact

    @classmethod
    def _build_remediation(cls, finding: Dict) -> str:
        """Provide actionable remediation guidance."""
        remediation = finding.get("remediation", "")

        if not remediation:
            # Generic guidance by vuln type
            remediations = {
                "xss": "Implement Content-Security-Policy headers and context-aware output encoding.",
                "sqli": "Use parameterized queries/prepared statements. Never concatenate user input into SQL.",
                "idor": "Implement proper access control checks. Verify user authorization for each resource.",
                "rce": "Disable dangerous functions, use allowlists for input, implement sandboxing."
            }
            remediation = remediations.get(finding.get("type", "").lower(),
                                         "Apply secure coding practices and input validation.")

        return f"{remediation}\n\n**Verification:** After implementing the fix, confirm the vulnerability is resolved by re-running the reproduction steps."

    @classmethod
    def _estimate_bounty(cls, finding: Dict, platform: Platform) -> str:
        """Estimate bounty based on platform and severity."""
        severity = finding.get("severity", "medium")

        ranges = {
            Platform.HACKERONE: {
                "critical": "$10,000 - $50,000+",
                "high": "$2,500 - $10,000", 
                "medium": "$500 - $2,500",
                "low": "$100 - $500"
            },
            Platform.BUGCROWD: {
                "critical": "$5,000 - $50,000+",
                "high": "$1,500 - $7,500",
                "medium": "$300 - $1,500", 
                "low": "$100 - $300"
            }
        }

        return ranges.get(platform, ranges[Platform.HACKERONE]).get(severity, "Unknown")

    @classmethod
    def _autocomplete_hints(cls, finding: Dict, platform: Platform) -> Dict:
        """Hints for automated form completion."""
        return {
            "weakness_id": finding.get("cwe_id", ""),
            "severity": finding.get("severity", "medium"),
            "attack_vector": finding.get("attack_vector", "Network"),
            "impact": finding.get("confidentiality_impact", "High"),
            "reproducibility": "Always" if finding.get("confirmed") else "Sometimes"
        }

if __name__ == "__main__":
    test_finding = {
        "type": "xss",
        "severity": "high",
        "target": "https://example.com/search",
        "impact": "Session hijacking possible"
    }

    formatted = BBPSubmissionFormatter.format_for_platform(
        test_finding, Platform.HACKERONE
    )

    print(f"Title: {formatted.title}")
    print(f"Platform: {formatted.platform}")
    print(f"Severity: {formatted.severity}")
