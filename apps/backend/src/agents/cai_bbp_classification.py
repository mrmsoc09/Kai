"""
CAI Vulnerability Classification for Bug Bounty Programs
Bounty-optimized severity taxonomy with reward weights
"""
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum

class BountyTier(Enum):
    P0 = "critical"      # $50K+
    P1 = "high"          # $10K-$50K
    P2 = "medium"        # $1K-$10K
    P3 = "low"           # $100-$1K
    INFO = "informational"  # $0-$100

@dataclass
class BBPVulnClass:
    """BBP-optimized vulnerability classification."""
    name: str
    cwe_id: str
    bounty_tier: BountyTier
    cvss_base: float
    likelihood_public_bbp: str  # high/medium/low
    likelihood_private: str
    auto_exploit_safe: bool
    reward_multiplier: float
    report_template: str

class CAIBBPClassification:
    """
    CAI vulnerability classification optimized for BBP workflows.
    Maps standard CVE/CWE to bounty tiers and reward structures.
    """

    VULN_CLASSES = {
        # Critical ($50K+)
        "rce": BBPVulnClass(
            name="Remote Code Execution",
            cwe_id="CWE-94",
            bounty_tier=BountyTier.P0,
            cvss_base=9.8,
            likelihood_public_bbp="low",
            likelihood_private="high",
            auto_exploit_safe=False,
            reward_multiplier=20.0,
            report_template="rce_critical"
        ),
        "sqli": BBPVulnClass(
            name="SQL Injection",
            cwe_id="CWE-89",
            bounty_tier=BountyTier.P0,
            cvss_base=9.1,
            likelihood_public_bbp="medium",
            likelihood_private="high",
            auto_exploit_safe=False,
            reward_multiplier=15.0,
            report_template="sqli_critical"
        ),
        "idor_critical": BBPVulnClass(
            name="IDOR - Critical Data Access",
            cwe_id="CWE-639",
            bounty_tier=BountyTier.P0,
            cvss_base=8.6,
            likelihood_public_bbp="high",
            likelihood_private="high",
            auto_exploit_safe=True,
            reward_multiplier=12.0,
            report_template="idor_critical"
        ),

        # High ($10K-$50K)
        "ssrf": BBPVulnClass(
            name="Server-Side Request Forgery",
            cwe_id="CWE-918",
            bounty_tier=BountyTier.P1,
            cvss_base=8.6,
            likelihood_public_bbp="medium",
            likelihood_private="high",
            auto_exploit_safe=False,
            reward_multiplier=10.0,
            report_template="ssrf_high"
        ),
        "stored_xss": BBPVulnClass(
            name="Stored XSS",
            cwe_id="CWE-79",
            bounty_tier=BountyTier.P1,
            cvss_base=6.1,
            likelihood_public_bbp="high",
            likelihood_private="medium",
            auto_exploit_safe=True,
            reward_multiplier=8.0,
            report_template="xss_stored"
        ),
        "auth_bypass": BBPVulnClass(
            name="Authentication Bypass",
            cwe_id="CWE-306",
            bounty_tier=BountyTier.P1,
            cvss_base=8.1,
            likelihood_public_bbp="medium",
            likelihood_private="high",
            auto_exploit_safe=True,
            reward_multiplier=9.0,
            report_template="auth_bypass"
        ),

        # Medium ($1K-$10K)
        "reflected_xss": BBPVulnClass(
            name="Reflected XSS",
            cwe_id="CWE-79",
            bounty_tier=BountyTier.P2,
            cvss_base=6.1,
            likelihood_public_bbp="high",
            likelihood_private="medium",
            auto_exploit_safe=True,
            reward_multiplier=5.0,
            report_template="xss_reflected"
        ),
        "idor_medium": BBPVulnClass(
            name="IDOR - Limited Data Access",
            cwe_id="CWE-639",
            bounty_tier=BountyTier.P2,
            cvss_base=5.3,
            likelihood_public_bbp="high",
            likelihood_private="high",
            auto_exploit_safe=True,
            reward_multiplier=4.0,
            report_template="idor_medium"
        ),
        "info_disclosure": BBPVulnClass(
            name="Sensitive Information Disclosure",
            cwe_id="CWE-200",
            bounty_tier=BountyTier.P2,
            cvss_base=5.3,
            likelihood_public_bbp="high",
            likelihood_private="medium",
            auto_exploit_safe=True,
            reward_multiplier=3.0,
            report_template="info_disclosure"
        ),

        # Low ($100-$1K)
        "missing_headers": BBPVulnClass(
            name="Missing Security Headers",
            cwe_id="CWE-693",
            bounty_tier=BountyTier.P3,
            cvss_base=3.7,
            likelihood_public_bbp="very_high",
            likelihood_private="low",
            auto_exploit_safe=True,
            reward_multiplier=1.0,
            report_template="headers_low"
        ),
        "verbose_error": BBPVulnClass(
            name="Verbose Error Messages",
            cwe_id="CWE-209",
            bounty_tier=BountyTier.P3,
            cvss_base=4.0,
            likelihood_public_bbp="high",
            likelihood_private="low",
            auto_exploit_safe=True,
            reward_multiplier=1.0,
            report_template="error_info"
        )
    }

    @classmethod
    def classify(cls, vuln_type: str) -> BBPVulnClass:
        return cls.VULN_CLASSES.get(vuln_type)

    @classmethod
    def get_by_tier(cls, tier: BountyTier) -> List[BBPVulnClass]:
        return [v for v in cls.VULN_CLASSES.values() if v.bounty_tier == tier]

    @classmethod
    def estimate_bounty(cls, vuln_type: str, program_type: str = "public") -> Dict[str, Any]:
        """Estimate bounty range based on vuln type and program."""
        vuln = cls.classify(vuln_type)
        if not vuln:
            return {"error": "Unknown vuln type"}

        ranges = {
            "critical": {"public": (5000, 50000), "private": (10000, 100000)},
            "high": {"public": (1000, 10000), "private": (5000, 50000)},
            "medium": {"public": (200, 2000), "private": (1000, 10000)},
            "low": {"public": (100, 500), "private": (500, 2000)},
            "informational": {"public": (0, 100), "private": (0, 500)}
        }

        tier = vuln.bounty_tier.value
        prog_range = ranges.get(tier, {}).get(program_type, (0, 0))

        return {
            "vuln_type": vuln_type,
            "tier": tier,
            "cvss": vuln.cvss_base,
            "estimated_range": prog_range,
            "multiplier": vuln.reward_multiplier,
            "template": vuln.report_template
        }

if __name__ == '__main__':
    import json
    estimate = CAIBBPClassification.estimate_bounty("idor_critical", "public")
    print(json.dumps(estimate, indent=2))
