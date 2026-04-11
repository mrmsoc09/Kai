"""
CVE applicability filter.
Maps detected technology stack to relevant CVEs from knowledge base.
Prevents indiscriminate playbook execution by filtering to applicable vulnerabilities.
"""

from __future__ import annotations

import logging
import yaml
from typing import Any, Dict, Optional, Set
from dataclasses import dataclass
from pathlib import Path
from .target_reconnaissance import TechStackFingerprint

logger = logging.getLogger(__name__)


@dataclass
class ApplicableCVE:
    """CVE applicable to a target."""

    cve_id: str
    affected_product: str
    affected_versions: list[str]
    vulnerability_type: str
    severity: str
    description: str
    cvss_score: float
    exploit_maturity: str
    affected_version_match: bool = False  # True if specific version match


class CVEApplicabilityFilter:
    """
    Filters CVE knowledge base against detected target tech stack.
    Returns only applicable CVEs to prevent wasted scanning effort.
    """

    def __init__(self, cve_knowledge_path: Optional[str] = None):
        """
        Initialize CVE applicability filter.

        Args:
            cve_knowledge_path: Path to CVE knowledge YAML file
        """
        self.cve_knowledge_path = (
            cve_knowledge_path
            or "tools/knowledge/cve_knowledge.yaml"
        )
        self.cve_db: Dict[str, Any] = {}
        self._load_cve_database()

    def _load_cve_database(self) -> None:
        """Load CVE knowledge base from YAML."""
        try:
            path = Path(self.cve_knowledge_path)
            if not path.exists():
                logger.warning(
                    f"CVE knowledge base not found at {self.cve_knowledge_path}"
                )
                return

            with open(path, "r") as f:
                data = yaml.safe_load(f)
                self.cve_db = data.get("cves", {})
                logger.info(
                    f"Loaded {len(self.cve_db)} CVEs from knowledge base"
                )
        except Exception as e:
            logger.error(f"Error loading CVE database: {str(e)}")

    def filter_applicable_cves(
        self, fingerprint: TechStackFingerprint
    ) -> list[ApplicableCVE]:
        """
        Filter CVEs applicable to detected tech stack.

        Args:
            fingerprint: Target tech stack fingerprint

        Returns:
            List of applicable CVEs sorted by severity
        """
        applicable = []

        for cve_id, cve_data in self.cve_db.items():
            if self._is_applicable(cve_id, cve_data, fingerprint):
                cve_obj = self._build_applicable_cve(
                    cve_id, cve_data, fingerprint
                )
                applicable.append(cve_obj)

        # Sort by CVSS score descending
        applicable.sort(key=lambda x: x.cvss_score, reverse=True)

        logger.info(
            f"Found {len(applicable)} applicable CVEs for {fingerprint.target}"
        )
        return applicable

    def _is_applicable(
        self,
        cve_id: str,
        cve_data: Dict[str, Any],
        fingerprint: TechStackFingerprint,
    ) -> bool:
        """
        Determine if CVE is applicable to target tech stack.

        Args:
            cve_id: CVE identifier
            cve_data: CVE metadata
            fingerprint: Target tech stack

        Returns:
            True if CVE is applicable
        """
        if not cve_data:
            return False

        vulnerability = cve_data.get("vulnerability", {})
        if not vulnerability:
            return False

        affected_product = vulnerability.get("product", "").lower()
        affected_versions = vulnerability.get("versions", [])

        # Merge all detected technologies
        all_techs = (
            fingerprint.web_servers
            | fingerprint.frameworks
            | fingerprint.languages
            | fingerprint.databases
            | fingerprint.cms_platforms
            | fingerprint.services
        )

        # Check if affected product matches any detected tech
        for tech in all_techs:
            tech_lower = tech.lower()

            # Direct product match
            if tech_lower in affected_product or affected_product in tech_lower:
                return True

            # Wildcard products apply to everything
            if affected_product == "*":
                return True

        return False

    def _build_applicable_cve(
        self,
        cve_id: str,
        cve_data: Dict[str, Any],
        fingerprint: TechStackFingerprint,
    ) -> ApplicableCVE:
        """Build ApplicableCVE object from CVE data."""
        metadata = cve_data.get("metadata", {})
        vulnerability = cve_data.get("vulnerability", {})

        cvss_score = float(metadata.get("cvss_score", 7.5))
        severity = metadata.get("severity", "high")

        cve_obj = ApplicableCVE(
            cve_id=cve_id,
            affected_product=vulnerability.get("product", "unknown"),
            affected_versions=vulnerability.get("versions", ["*"]),
            vulnerability_type=vulnerability.get("type", "unknown"),
            severity=severity,
            description=vulnerability.get("description", ""),
            cvss_score=cvss_score,
            exploit_maturity=metadata.get("exploit_maturity", "unproven"),
        )

        # Check if we have specific version match in fingerprint
        if fingerprint.versions:
            product = vulnerability.get("product", "").lower()
            for tech, version in fingerprint.versions.items():
                if tech.lower() in product:
                    if self._version_matches(
                        version, vulnerability.get("versions", [])
                    ):
                        cve_obj.affected_version_match = True

        return cve_obj

    @staticmethod
    def _version_matches(detected_version: str, affected_versions: list[str]) -> bool:
        """Check if detected version matches affected versions."""
        if not affected_versions or affected_versions == ["*"]:
            return True

        detected_parts = detected_version.split(".")
        for affected in affected_versions:
            affected_parts = affected.split(".")

            # Match major.minor at minimum
            if len(detected_parts) >= 2 and len(affected_parts) >= 2:
                if (
                    detected_parts[0] == affected_parts[0]
                    and detected_parts[1] == affected_parts[1]
                ):
                    return True

        return False

    def get_attack_surface(
        self, applicable_cves: list[ApplicableCVE]
    ) -> Dict[str, Any]:
        """
        Analyze attack surface from applicable CVEs.

        Args:
            applicable_cves: List of applicable CVEs

        Returns:
            Summary of attack surface
        """
        if not applicable_cves:
            return {
                "total_cves": 0,
                "attack_surface": "minimal",
                "risk_level": "low",
            }

        # Group by vulnerability type
        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        rce_count = 0
        auth_bypass_count = 0
        privilege_escalation_count = 0

        for cve in applicable_cves:
            vuln_type = cve.vulnerability_type.lower()
            by_type[vuln_type] = by_type.get(vuln_type, 0) + 1
            by_severity[cve.severity] = by_severity.get(cve.severity, 0) + 1

            if "rce" in vuln_type or "remote code" in vuln_type:
                rce_count += 1
            elif "auth" in vuln_type and "bypass" in vuln_type:
                auth_bypass_count += 1
            elif "privilege" in vuln_type or "escalation" in vuln_type:
                privilege_escalation_count += 1

        # Calculate risk level
        critical_count = by_severity.get("critical", 0)
        high_count = by_severity.get("high", 0)

        if critical_count > 0:
            risk_level = "critical"
            attack_surface = "extremely_large"
        elif high_count >= 5:
            risk_level = "high"
            attack_surface = "very_large"
        elif high_count >= 2:
            risk_level = "medium-high"
            attack_surface = "large"
        elif len(applicable_cves) > 10:
            risk_level = "medium"
            attack_surface = "moderate"
        else:
            risk_level = "low-medium"
            attack_surface = "small"

        return {
            "total_cves": len(applicable_cves),
            "by_severity": by_severity,
            "by_type": by_type,
            "rce_vulnerabilities": rce_count,
            "auth_bypass_vulnerabilities": auth_bypass_count,
            "privilege_escalation_vulnerabilities": privilege_escalation_count,
            "attack_surface": attack_surface,
            "risk_level": risk_level,
            "highest_cvss": max(cve.cvss_score for cve in applicable_cves),
            "average_cvss": sum(cve.cvss_score for cve in applicable_cves)
            / len(applicable_cves),
        }

    def get_playbook_recommendations(
        self, applicable_cves: list[ApplicableCVE], playbook_registry: Dict[str, Any]
    ) -> list[Dict[str, Any]]:
        """
        Recommend playbooks based on applicable CVEs.

        Args:
            applicable_cves: List of applicable CVEs
            playbook_registry: Playbook registry mapping

        Returns:
            List of recommended playbooks with reasoning
        """
        recommendations = []
        cve_types = set()

        for cve in applicable_cves:
            cve_types.add(cve.vulnerability_type.lower())

        # Match CVE types to playbooks
        for cve_type in cve_types:
            for playbook_id, playbook_data in playbook_registry.items():
                playbook_name = playbook_data.get("name", "").lower()

                if cve_type in playbook_name or self._fuzzy_match(
                    cve_type, playbook_name
                ):
                    recommendations.append(
                        {
                            "playbook_id": playbook_id,
                            "playbook_name": playbook_data.get("name"),
                            "reason": f"Matches {cve_type} vulnerabilities",
                            "complexity": playbook_data.get("complexity"),
                            "duration_minutes": playbook_data.get("duration_minutes"),
                        }
                    )

        return recommendations

    @staticmethod
    def _fuzzy_match(cve_type: str, playbook_name: str) -> bool:
        """Fuzzy match CVE type to playbook name."""
        # Common mappings
        mappings = {
            "rce": ["rce", "remote code", "command execution"],
            "sqli": ["sql", "injection"],
            "xss": ["xss", "cross-site"],
            "auth": ["authentication", "auth", "bypass"],
            "privilege": ["privilege", "escalation", "privesc"],
            "csrf": ["csrf", "cross-site request"],
            "ssrf": ["ssrf", "server-side"],
        }

        for key, variations in mappings.items():
            if key in cve_type:
                for variation in variations:
                    if variation in playbook_name:
                        return True

        return False
