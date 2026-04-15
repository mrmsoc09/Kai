from __future__ import annotations

from typing import Any

from tools.ai.pattern_recognition_engine import PatternRecognitionEngine


class AdvancedCorrelationEngine:
    """
    Pattern-backed correlation and chain clustering for detection findings.
    """

    def __init__(self, *, pattern_engine: PatternRecognitionEngine | None = None) -> None:
        self.pattern_engine = pattern_engine or PatternRecognitionEngine()

    @staticmethod
    def _severity_rank(level: str) -> int:
        mapping = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        return mapping.get((level or "").lower(), 2)

    def suggest_unified_remediation(self, pattern_match: dict[str, Any]) -> list[str]:
        pname = str(pattern_match.get("pattern_name", "")).lower()
        base = [
            "Apply defense-in-depth controls across all affected endpoints rather than endpoint-local fixes.",
            "Add regression tests for each indicator in this chain and validate closure together.",
            "Prioritize remediation sequencing by highest shared business impact path first.",
        ]

        if "xss" in pname:
            base.append("Harden output encoding and anti-CSRF token validation in the same release window.")
        if "sqli" in pname or "sql" in pname:
            base.append("Remediate query parameterization and suppress schema/error disclosure in tandem.")
        if "auth" in pname or "idor" in pname or "api" in pname:
            base.append("Standardize authorization middleware and object-level access checks across route families.")
        if "secret" in pname:
            base.append("Rotate exposed credentials and tighten secret handling/storage controls immediately.")
        return base

    def correlate_findings_by_pattern(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        matches = self.pattern_engine.identify_patterns_in_findings(findings)
        clusters = []

        for i, match in enumerate(matches, start=1):
            related = match.get("related_findings", [])
            highest = "MEDIUM"
            max_rank = 2
            for finding in related:
                sev = str((finding.get("severity") or {}).get("severity_level", "MEDIUM"))
                rank = self._severity_rank(sev)
                if rank > max_rank:
                    max_rank = rank
                    highest = sev.upper()

            cluster = {
                "cluster_id": f"chain-{i:03d}",
                "type": "attack_chain",
                "pattern_name": match.get("pattern_name"),
                "pattern_description": match.get("description"),
                "findings": related,
                "finding_count": len(related),
                "confidence": match.get("confidence"),
                "risk_escalation": match.get("risk_escalation"),
                "business_impact": match.get("business_impact"),
                "remediation_priority": match.get("remediation_priority"),
                "highest_severity": highest,
                "unified_remediation": self.suggest_unified_remediation(match),
            }
            clusters.append(cluster)

        clusters.sort(
            key=lambda c: (
                self._severity_rank(str(c.get("highest_severity", "MEDIUM"))),
                float(c.get("confidence", 0.0)),
            ),
            reverse=True,
        )

        return {
            "attack_chain_clusters": clusters,
            "cluster_count": len(clusters),
            "high_confidence_clusters": sum(1 for c in clusters if float(c.get("confidence", 0.0)) >= 0.85),
        }


__all__ = ["AdvancedCorrelationEngine"]
