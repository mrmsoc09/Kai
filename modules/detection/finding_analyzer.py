"""Finding analysis and severity assessment engine."""

from typing import Dict, Any, List, Optional
from enum import Enum


class SeverityLevel(Enum):
    """Vulnerability severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingAnalyzer:
    """Analyze and assess findings for severity, exploitability, impact."""

    # Severity scoring weights
    EXPLOITABILITY_WEIGHT = 0.4
    IMPACT_WEIGHT = 0.4
    AFFECTED_USERS_WEIGHT = 0.2

    # CVSS-inspired scoring
    CVSS_SCORE_MAPPING = {
        (0.0, 0.1): SeverityLevel.INFO,
        (0.1, 3.9): SeverityLevel.LOW,
        (4.0, 6.9): SeverityLevel.MEDIUM,
        (7.0, 8.9): SeverityLevel.HIGH,
        (9.0, 10.0): SeverityLevel.CRITICAL,
    }

    # Vulnerability type to exploitability score (0-1)
    EXPLOITABILITY_SCORES = {
        "sql_injection": 0.95,
        "cross_site_scripting": 0.90,
        "remote_code_execution": 0.98,
        "authentication_bypass": 0.85,
        "authorization_bypass": 0.80,
        "directory_traversal": 0.75,
        "local_file_inclusion": 0.70,
        "remote_file_inclusion": 0.85,
        "xml_external_entity": 0.65,
        "cross_site_request_forgery": 0.60,
        "os_command_injection": 0.95,
        "information_disclosure": 0.50,
        "insecure_deserialization": 0.85,
        "broken_access_control": 0.80,
        "using_components_with_known_vulnerabilities": 0.70,
        "insufficient_logging_monitoring": 0.40,
    }

    # Impact scores (0-1)
    IMPACT_SCORES = {
        "confidentiality": {"critical": 0.9, "high": 0.7, "low": 0.3},
        "integrity": {"critical": 0.9, "high": 0.7, "low": 0.3},
        "availability": {"critical": 0.9, "high": 0.7, "low": 0.3},
    }

    def __init__(self):
        """Initialize finding analyzer."""
        self.analysis_cache: Dict[str, Dict[str, Any]] = {}

    def analyze_finding(
        self, finding: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensively analyze a finding.

        Provides:
        - CVSS score
        - Severity level
        - Exploitability assessment
        - Impact assessment
        - Recommendations
        """
        if context is None:
            context = {}

        analysis = {
            "finding_id": finding.get("id", "unknown"),
            "vulnerability_type": finding.get("vulnerability_type", "unknown"),
        }

        # Extract analysis components
        exploitability_score = self._assess_exploitability(finding)
        impact_score = self._assess_impact(finding, context)
        affected_users_score = self._assess_affected_users(finding, context)

        # Compute CVSS-inspired score
        cvss_score = (
            (exploitability_score * self.EXPLOITABILITY_WEIGHT)
            + (impact_score * self.IMPACT_WEIGHT)
            + (affected_users_score * self.AFFECTED_USERS_WEIGHT)
        ) * 10  # Scale to 0-10

        # Determine severity
        severity = self._score_to_severity(cvss_score)

        analysis.update({
            "cvss_score": round(cvss_score, 1),
            "severity": severity.value,
            "exploitability_score": round(exploitability_score, 2),
            "impact_score": round(impact_score, 2),
            "affected_users_score": round(affected_users_score, 2),
            "exploitability_factors": self._get_exploitability_factors(finding),
            "impact_factors": self._get_impact_factors(finding, context),
            "recommendations": self._get_remediation_recommendations(finding, severity),
            "payout_potential": self._estimate_payout_potential(finding, severity),
        })

        self.analysis_cache[finding.get("id", "unknown")] = analysis
        return analysis

    def batch_analyze(
        self, findings: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Analyze multiple findings."""
        return [self.analyze_finding(f, context) for f in findings]

    def prioritize_findings(
        self,
        findings: List[Dict[str, Any]],
        strategies: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Prioritize findings by different strategies.

        Strategies:
        - severity: Sort by severity level
        - exploitability: Sort by exploitability score
        - impact: Sort by impact
        - payout: Sort by estimated bounty value
        - exploitability_impact: Combined score
        """
        if strategies is None:
            strategies = ["severity", "exploitability", "payout"]

        prioritized = {}

        for strategy in strategies:
            analyzed = self.batch_analyze(findings)

            if strategy == "severity":
                severity_order = {
                    SeverityLevel.CRITICAL.value: 5,
                    SeverityLevel.HIGH.value: 4,
                    SeverityLevel.MEDIUM.value: 3,
                    SeverityLevel.LOW.value: 2,
                    SeverityLevel.INFO.value: 1,
                }
                sorted_findings = sorted(
                    analyzed,
                    key=lambda x: severity_order.get(x.get("severity"), 0),
                    reverse=True,
                )

            elif strategy == "exploitability":
                sorted_findings = sorted(
                    analyzed,
                    key=lambda x: x.get("exploitability_score", 0),
                    reverse=True,
                )

            elif strategy == "impact":
                sorted_findings = sorted(
                    analyzed,
                    key=lambda x: x.get("impact_score", 0),
                    reverse=True,
                )

            elif strategy == "payout":
                sorted_findings = sorted(
                    analyzed,
                    key=lambda x: x.get("payout_potential", {}).get("estimated_min", 0),
                    reverse=True,
                )

            elif strategy == "exploitability_impact":
                sorted_findings = sorted(
                    analyzed,
                    key=lambda x: (
                        x.get("exploitability_score", 0)
                        * x.get("impact_score", 0)
                    ),
                    reverse=True,
                )

            else:
                sorted_findings = analyzed

            prioritized[strategy] = sorted_findings[:10]  # Top 10 per strategy

        return prioritized

    def _assess_exploitability(self, finding: Dict[str, Any]) -> float:
        """Assess how exploitable the vulnerability is (0-1)."""
        vuln_type = finding.get("vulnerability_type", "unknown").lower()
        base_score = self.EXPLOITABILITY_SCORES.get(vuln_type, 0.5)

        # Adjust based on additional factors
        if finding.get("requires_authentication"):
            base_score *= 0.6  # Much harder to exploit

        if finding.get("requires_user_interaction"):
            base_score *= 0.7  # Harder to exploit

        if finding.get("exploited_publicly"):
            base_score *= 1.1  # Known exploits increase score

        if finding.get("is_zero_day"):
            base_score *= 1.2  # Zero-days are highly exploitable

        return min(1.0, base_score)

    def _assess_impact(self, finding: Dict[str, Any], context: Dict[str, Any]) -> float:
        """Assess impact of the vulnerability (0-1)."""
        impact_factors = finding.get("impact", {})

        confidentiality_impact = impact_factors.get("confidentiality", "low")
        integrity_impact = impact_factors.get("integrity", "low")
        availability_impact = impact_factors.get("availability", "low")

        conf_score = self.IMPACT_SCORES["confidentiality"].get(
            confidentiality_impact, 0.3
        )
        integ_score = self.IMPACT_SCORES["integrity"].get(integrity_impact, 0.3)
        avail_score = self.IMPACT_SCORES["availability"].get(
            availability_impact, 0.3
        )

        # Average of the three
        base_score = (conf_score + integ_score + avail_score) / 3

        # Adjust based on context
        if context.get("is_critical_system"):
            base_score *= 1.3

        if context.get("affects_pii"):
            base_score *= 1.2

        if context.get("affects_payment_processing"):
            base_score *= 1.2

        return min(1.0, base_score)

    def _assess_affected_users(
        self, finding: Dict[str, Any], context: Dict[str, Any]
    ) -> float:
        """Assess how many users are affected (0-1)."""
        if context.get("all_users_affected"):
            return 1.0

        affected_count = finding.get("affected_user_count", 0)
        total_users = context.get("total_user_count", 1000000)

        if affected_count == 0:
            return 0.1  # Few users affected

        ratio = affected_count / total_users if total_users > 0 else 0
        return min(1.0, ratio)

    def _score_to_severity(self, score: float) -> SeverityLevel:
        """Map CVSS score to severity level."""
        for (min_score, max_score), severity in self.CVSS_SCORE_MAPPING.items():
            if min_score <= score <= max_score:
                return severity
        return SeverityLevel.LOW

    def _get_exploitability_factors(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        """Extract exploitability factors from finding."""
        return {
            "requires_authentication": finding.get("requires_authentication", False),
            "requires_user_interaction": finding.get("requires_user_interaction", False),
            "exploited_publicly": finding.get("exploited_publicly", False),
            "is_zero_day": finding.get("is_zero_day", False),
            "attack_complexity": finding.get("attack_complexity", "unknown"),
            "attack_vector": finding.get("attack_vector", "unknown"),
        }

    def _get_impact_factors(
        self, finding: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract impact factors from finding."""
        return {
            "confidentiality": finding.get("impact", {}).get("confidentiality", "none"),
            "integrity": finding.get("impact", {}).get("integrity", "none"),
            "availability": finding.get("impact", {}).get("availability", "none"),
            "is_critical_system": context.get("is_critical_system", False),
            "affects_pii": context.get("affects_pii", False),
            "affects_payment": context.get("affects_payment_processing", False),
        }

    def _get_remediation_recommendations(
        self, finding: Dict[str, Any], severity: SeverityLevel
    ) -> List[str]:
        """Get remediation recommendations based on vulnerability type."""
        vuln_type = finding.get("vulnerability_type", "").lower()

        recommendations = {
            "sql_injection": [
                "Use parameterized queries",
                "Implement input validation",
                "Use ORM frameworks",
                "Apply WAF rules for SQLi",
            ],
            "cross_site_scripting": [
                "Sanitize user input",
                "Use CSP headers",
                "Encode output properly",
                "Use templating engines with auto-escape",
            ],
            "remote_code_execution": [
                "Remove code execution endpoints",
                "Use sandboxing/containerization",
                "Implement strict input validation",
                "Disable dangerous functions",
            ],
            "authentication_bypass": [
                "Review authentication logic",
                "Implement MFA",
                "Use established auth libraries",
                "Add rate limiting",
            ],
            "broken_access_control": [
                "Implement proper authorization checks",
                "Use role-based access control",
                "Audit permission model",
                "Test access controls thoroughly",
            ],
        }

        general_recommendations = [
            "Patch the vulnerable component",
            "Test fix in staging before production",
            "Monitor for exploitation attempts",
            "Update security documentation",
        ]

        specific = recommendations.get(vuln_type, [])
        return specific + general_recommendations

    def _estimate_payout_potential(
        self, finding: Dict[str, Any], severity: SeverityLevel
    ) -> Dict[str, Any]:
        """Estimate bug bounty payout for finding."""
        # Base payout by severity
        base_payouts = {
            SeverityLevel.CRITICAL: (5000, 50000),
            SeverityLevel.HIGH: (1000, 10000),
            SeverityLevel.MEDIUM: (500, 2000),
            SeverityLevel.LOW: (100, 500),
            SeverityLevel.INFO: (0, 100),
        }

        min_payout, max_payout = base_payouts.get(severity, (0, 100))

        # Adjust based on factors
        vuln_type = finding.get("vulnerability_type", "").lower()
        type_multiplier = {
            "remote_code_execution": 3.0,
            "authentication_bypass": 2.5,
            "sql_injection": 2.0,
            "cross_site_scripting": 1.5,
        }.get(vuln_type, 1.0)

        adjusted_min = int(min_payout * type_multiplier)
        adjusted_max = int(max_payout * type_multiplier)

        return {
            "estimated_min": adjusted_min,
            "estimated_max": adjusted_max,
            "currency": "USD",
            "factors": ["severity", "vulnerability_type"],
        }

    def get_analysis_summary(self) -> Dict[str, Any]:
        """Get summary of all analyses performed."""
        if not self.analysis_cache:
            return {"analyses_performed": 0}

        severities = {}
        total_cvss = 0

        for analysis in self.analysis_cache.values():
            severity = analysis.get("severity", "unknown")
            severities[severity] = severities.get(severity, 0) + 1
            total_cvss += analysis.get("cvss_score", 0)

        avg_cvss = total_cvss / len(self.analysis_cache) if self.analysis_cache else 0

        return {
            "analyses_performed": len(self.analysis_cache),
            "severity_distribution": severities,
            "average_cvss_score": round(avg_cvss, 1),
        }
