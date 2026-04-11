"""CVE knowledge base for vulnerability intelligence and exploitation guidance.

This module provides CVEKnowledgeBase for querying CVE data, identifying
exploitable versions, and mapping findings to personas and playbooks.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class CVEKnowledgeBase:
    """Load and query CVE knowledge base for vulnerability intelligence."""

    def __init__(self, cve_knowledge_file: str | Path) -> None:
        """Initialize with path to cve_knowledge.yaml.

        Args:
            cve_knowledge_file: Path to CVE knowledge YAML file.

        Raises:
            FileNotFoundError: If CVE knowledge file does not exist.
            yaml.YAMLError: If file is malformed YAML.
        """
        self.cve_knowledge_file = Path(cve_knowledge_file)
        if not self.cve_knowledge_file.exists():
            raise FileNotFoundError(f"CVE knowledge file not found: {self.cve_knowledge_file}")

        try:
            with self.cve_knowledge_file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                self._cve_index = data.get("cve_index", {})
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in CVE knowledge file: {e}") from e

        # Build indices for efficient lookups
        self._product_index: dict[str, list[str]] = {}
        self._type_index: dict[str, list[str]] = {}
        self._severity_index: dict[str, list[str]] = {}
        self._persona_index: dict[str, list[str]] = {}
        self._playbook_index: dict[str, list[str]] = {}
        self._build_indices()

        logger.info(f"Loaded {len(self._cve_index)} CVEs into knowledge base")

    def _build_indices(self) -> None:
        """Build lookup indices for efficient queries."""
        for cve_id, cve_data in self._cve_index.items():
            if not isinstance(cve_data, dict):
                continue

            # Product index
            product = cve_data.get("vulnerability", {}).get("product", "Unknown")
            if product not in self._product_index:
                self._product_index[product] = []
            self._product_index[product].append(cve_id)

            # Type index
            vuln_type = cve_data.get("vulnerability", {}).get("vulnerability_type", "Unknown")
            if vuln_type not in self._type_index:
                self._type_index[vuln_type] = []
            self._type_index[vuln_type].append(cve_id)

            # Severity index
            severity = cve_data.get("metadata", {}).get("severity", "UNKNOWN")
            if severity not in self._severity_index:
                self._severity_index[severity] = []
            self._severity_index[severity].append(cve_id)

            # Persona index
            personas = cve_data.get("persona_mapping", {}).get("relevant_personas", [])
            for persona_info in personas:
                if isinstance(persona_info, dict):
                    persona = persona_info.get("persona")
                    if persona:
                        if persona not in self._persona_index:
                            self._persona_index[persona] = []
                        self._persona_index[persona].append(cve_id)

            # Playbook index
            playbooks = cve_data.get("persona_mapping", {}).get("playbooks", [])
            for playbook_info in playbooks:
                if isinstance(playbook_info, dict):
                    playbook = playbook_info.get("playbook")
                    if playbook:
                        if playbook not in self._playbook_index:
                            self._playbook_index[playbook] = []
                        self._playbook_index[playbook].append(cve_id)

    def get_cve_by_id(self, cve_id: str) -> dict[str, Any]:
        """Retrieve complete CVE record by CVE ID.

        Args:
            cve_id: CVE identifier (e.g., 'CVE-2021-41773').

        Returns:
            Dictionary containing complete CVE metadata and details.

        Raises:
            KeyError: If CVE is not found.
        """
        if cve_id not in self._cve_index:
            raise KeyError(f"CVE {cve_id} not found in knowledge base")

        return self._cve_index[cve_id]

    def find_cves_by_product(
        self, product_name: str, version: str | None = None
    ) -> list[dict[str, Any]]:
        """Find all CVEs affecting a product, optionally filtered by version.

        Args:
            product_name: Product name (e.g., 'Apache HTTP Server').
            version: Optional version to match against affected_versions.

        Returns:
            List of CVE records sorted by CVSS score (descending).
        """
        cve_ids = self._product_index.get(product_name, [])
        cves = []

        for cve_id in cve_ids:
            cve = self._cve_index.get(cve_id)
            if not cve:
                continue

            # If version specified, check if CVE affects this version
            if version:
                affected = cve.get("vulnerability", {}).get("affected_versions", [])
                if not self._version_matches(version, affected):
                    continue

            cves.append(cve)

        # Sort by CVSS score descending
        cves.sort(
            key=lambda x: x.get("metadata", {}).get("cvss_score", 0),
            reverse=True,
        )

        return cves

    def find_cves_by_type(self, vulnerability_type: str) -> list[dict[str, Any]]:
        """Find CVEs by vulnerability type.

        Args:
            vulnerability_type: Type (SQL Injection, XSS, RCE, etc.).

        Returns:
            List of CVE records.
        """
        cve_ids = self._type_index.get(vulnerability_type, [])
        cves = []

        for cve_id in cve_ids:
            cve = self._cve_index.get(cve_id)
            if cve:
                cves.append(cve)

        cves.sort(
            key=lambda x: x.get("metadata", {}).get("cvss_score", 0),
            reverse=True,
        )

        return cves

    def find_cves_by_severity(self, severity: str) -> list[dict[str, Any]]:
        """Find CVEs by severity level.

        Args:
            severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW, INFO).

        Returns:
            List of CVE records.
        """
        cve_ids = self._severity_index.get(severity, [])
        cves = []

        for cve_id in cve_ids:
            cve = self._cve_index.get(cve_id)
            if cve:
                cves.append(cve)

        return cves

    def find_cves_by_persona(self, persona_name: str) -> list[dict[str, Any]]:
        """Find all CVEs relevant to a specific persona.

        Args:
            persona_name: Name of the persona.

        Returns:
            List of CVE records relevant to persona.
        """
        cve_ids = self._persona_index.get(persona_name, [])
        cves = []

        for cve_id in cve_ids:
            cve = self._cve_index.get(cve_id)
            if cve:
                cves.append(cve)

        cves.sort(
            key=lambda x: x.get("metadata", {}).get("cvss_score", 0),
            reverse=True,
        )

        return cves

    def find_cves_for_playbook(self, playbook_name: str) -> list[dict[str, Any]]:
        """Find all CVEs used in a specific playbook.

        Args:
            playbook_name: Name of the playbook.

        Returns:
            List of CVE records used in playbook.
        """
        cve_ids = self._playbook_index.get(playbook_name, [])
        cves = []

        for cve_id in cve_ids:
            cve = self._cve_index.get(cve_id)
            if cve:
                cves.append(cve)

        return cves

    def get_exploitation_patterns(self, cve_id: str) -> list[dict[str, str]]:
        """Get exploitation techniques and PoC patterns for a CVE.

        Args:
            cve_id: CVE identifier.

        Returns:
            List of exploitation pattern dictionaries.

        Raises:
            KeyError: If CVE not found.
        """
        cve = self.get_cve_by_id(cve_id)
        exploitation = cve.get("exploitation", {})
        return exploitation.get("poc_patterns", [])

    def validate_cve_knowledge(self) -> tuple[bool, list[str]]:
        """Validate CVE knowledge base for completeness and consistency.

        Returns:
            Tuple of (is_valid, list_of_issues).
        """
        issues: list[str] = []

        # Check for duplicate CVE IDs
        seen_cves = set()
        for cve_id in self._cve_index.keys():
            if cve_id in seen_cves:
                issues.append(f"Duplicate CVE ID: {cve_id}")
            seen_cves.add(cve_id)

        # Validate CVE structure
        required_fields = {
            "metadata": ["cve_id", "cvss_score", "severity"],
            "vulnerability": ["product", "affected_versions", "vulnerability_type"],
            "exploitation": ["exploitability"],
            "impact": ["confidentiality"],
            "remediation": [],
            "persona_mapping": ["relevant_personas"],
        }

        for cve_id, cve_data in self._cve_index.items():
            for section, fields in required_fields.items():
                if section not in cve_data:
                    issues.append(f"{cve_id} missing section: {section}")
                else:
                    section_data = cve_data[section]
                    for field in fields:
                        if field not in section_data:
                            issues.append(f"{cve_id} missing {section}.{field}")

        return len(issues) == 0, issues

    def list_indexed_cves(self) -> list[str]:
        """Return list of all CVE IDs in knowledge base.

        Returns:
            Sorted list of CVE identifiers.
        """
        return sorted(self._cve_index.keys())

    def get_statistics(self) -> dict[str, int]:
        """Return statistics about CVE knowledge base.

        Returns:
            Dictionary with statistics.
        """
        # Count by severity
        severity_counts = {}
        for severity in self._severity_index.keys():
            severity_counts[severity] = len(self._severity_index[severity])

        return {
            "total_cves": len(self._cve_index),
            "total_products": len(self._product_index),
            "total_vulnerability_types": len(self._type_index),
            "total_personas": len(self._persona_index),
            "total_playbooks": len(self._playbook_index),
            "by_severity": severity_counts,
        }

    @staticmethod
    def _version_matches(version: str, affected_versions: list[str]) -> bool:
        """Check if a version matches the affected versions list.

        Args:
            version: Version to check (e.g., '2.4.49').
            affected_versions: List of affected versions or ranges.

        Returns:
            True if version matches any affected version.
        """
        version_str = version.lower().strip()

        for affected in affected_versions:
            affected_str = affected.lower().strip()

            # Exact match
            if version_str == affected_str:
                return True

            # Range match (e.g., "2.4.49-2.4.50")
            if "-" in affected_str:
                parts = affected_str.split("-")
                if len(parts) == 2:
                    start, end = parts[0].strip(), parts[1].strip()
                    # Simple string comparison for version ranges
                    if start <= version_str <= end:
                        return True

            # Prefix match
            if version_str.startswith(affected_str):
                return True

        return False
