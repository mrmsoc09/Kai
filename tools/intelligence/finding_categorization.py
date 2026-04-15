from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULT_FREQUENCY_PATH = Path("tools/knowledge/bug_bounty_detection_frequency.yaml")


PRIMARY_CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "client_side_vulnerabilities",
        (
            "xss",
            "cross-site scripting",
            "prototype pollution",
            "clickjacking",
            "client",
            "html injection",
            "javascript injection",
        ),
    ),
    (
        "authentication_and_session",
        (
            "weak authentication",
            "session",
            "jwt",
            "oauth",
            "sso",
            "auth",
            "token",
            "idor",
            "bola",
            "bfla",
        ),
    ),
    (
        "injection_attacks",
        (
            "sql injection",
            "nosql",
            "command injection",
            "template",
            "insecure deserialization",
            "xxe",
            "host header",
        ),
    ),
    (
        "server_side_request_risk",
        (
            "ssrf",
            "request forgery",
            "open redirect",
            "cache poisoning",
        ),
    ),
    (
        "misconfiguration_and_exposure",
        (
            "misconfiguration",
            "information disclosure",
            "source code",
            "debug",
            "secret",
            "credential leakage",
            "path traversal",
            "subdomain takeover",
            "dns",
            "tls",
            "crypto",
        ),
    ),
    (
        "business_logic_flaws",
        (
            "business logic",
            "authorization bypass",
            "privilege",
            "race",
            "price manipulation",
            "workflow",
            "account takeover",
        ),
    ),
    (
        "api_and_data_layer_issues",
        (
            "graphql",
            "api",
            "rate-limit",
            "file upload",
            "mass assignment",
            "exposed endpoint",
        ),
    ),
]


CATEGORY_COMPLEXITY = {
    "client_side_vulnerabilities": "Low-Medium",
    "authentication_and_session": "Medium",
    "injection_attacks": "Medium-High",
    "server_side_request_risk": "Medium-High",
    "misconfiguration_and_exposure": "Low-Medium",
    "business_logic_flaws": "High",
    "api_and_data_layer_issues": "Medium",
    "other": "Medium",
}


@dataclass(slots=True)
class FindingCategory:
    category_id: str
    category_name: str
    vulnerability_type: str
    prevalence_in_scope: float
    average_payout_usd: int
    remediation_complexity: str
    confidence: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id,
            "category_name": self.category_name,
            "vulnerability_type": self.vulnerability_type,
            "prevalence_in_scope": self.prevalence_in_scope,
            "average_payout_usd": self.average_payout_usd,
            "remediation_complexity": self.remediation_complexity,
            "confidence": self.confidence,
        }


class FindingCategorizer:
    """
    Detection-only finding categorization layer.

    Produces a 20-30 vulnerability taxonomy grounded in Prompt 5 frequency/payout
    data and maps raw findings to category metadata.
    """

    def __init__(self, frequency_path: str | Path = DEFAULT_FREQUENCY_PATH) -> None:
        self.frequency_path = Path(frequency_path)
        self.frequency_data = self._read_yaml(self.frequency_path)
        self.ranked_detection_types: list[dict[str, Any]] = (
            self.frequency_data.get("detection_frequency_analysis", {}).get("ranked_detection_types", [])
        )
        self.taxonomy = self._build_taxonomy()

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Missing frequency artifact: {path}")
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid YAML structure: {path}")
        return payload

    @staticmethod
    def _normalize(text: str | None) -> str:
        return (text or "").strip().lower()

    def _map_primary_category(self, vuln_type: str) -> str:
        value = self._normalize(vuln_type)
        for category, keys in PRIMARY_CATEGORY_RULES:
            if any(k in value for k in keys):
                return category
        return "other"

    @staticmethod
    def _display_name(category_id: str) -> str:
        return category_id.replace("_", " ").title()

    def _build_taxonomy(self) -> dict[str, FindingCategory]:
        taxonomy: dict[str, FindingCategory] = {}
        for row in self.ranked_detection_types:
            vuln_type = str(row.get("vulnerability_type", "")).strip()
            if not vuln_type:
                continue
            category_id = self._map_primary_category(vuln_type)
            item = FindingCategory(
                category_id=category_id,
                category_name=self._display_name(category_id),
                vulnerability_type=vuln_type,
                prevalence_in_scope=float(row.get("detection_frequency", 0.0)),
                average_payout_usd=int(row.get("average_payout_usd", 0)),
                remediation_complexity=CATEGORY_COMPLEXITY.get(category_id, "Medium"),
                confidence=str(row.get("confidence", "MEDIUM")),
            )
            taxonomy[self._normalize(vuln_type)] = item
        return taxonomy

    def taxonomy_summary(self) -> dict[str, Any]:
        grouped: dict[str, int] = {}
        for item in self.taxonomy.values():
            grouped[item.category_id] = grouped.get(item.category_id, 0) + 1

        return {
            "taxonomy_version": "1.0",
            "total_vulnerability_categories": len(self.taxonomy),
            "primary_category_breakdown": grouped,
            "data_source": str(self.frequency_path),
        }

    def determine_subcategory(self, vulnerability_type: str, raw_finding: dict[str, Any]) -> str:
        vuln = self._normalize(vulnerability_type)
        method = self._normalize(str(raw_finding.get("detection_method", "")))
        title = self._normalize(str(raw_finding.get("title", "")))

        if "xss" in vuln:
            if "dom" in method or "dom" in title:
                return "dom_based_xss"
            if "stored" in method or "stored" in title:
                return "stored_xss"
            if "reflected" in method or "reflected" in title:
                return "reflected_xss"
            return "xss_generic"
        if "sql injection" in vuln or "sqli" in vuln:
            if "time" in method or "blind" in method:
                return "time_or_blind_sqli"
            if "union" in method:
                return "union_based_sqli"
            return "sqli_generic"
        if "auth" in vuln or "session" in vuln:
            if "token" in title or "jwt" in title:
                return "token_validation"
            return "authentication_or_session"
        if "misconfiguration" in vuln:
            return "security_misconfiguration"
        if "information disclosure" in vuln:
            return "sensitive_information_disclosure"
        if "ssrf" in vuln:
            return "server_side_request_forgery"
        return "general"

    def estimate_severity(self, category: str, raw_finding: dict[str, Any]) -> str:
        confidence = self._normalize(str(raw_finding.get("confidence", "")))
        base = {
            "injection_attacks": "HIGH",
            "authentication_and_session": "HIGH",
            "business_logic_flaws": "HIGH",
            "server_side_request_risk": "HIGH",
            "misconfiguration_and_exposure": "MEDIUM",
            "client_side_vulnerabilities": "MEDIUM",
            "api_and_data_layer_issues": "MEDIUM",
            "other": "MEDIUM",
        }.get(category, "MEDIUM")

        if confidence == "critical" and base in {"MEDIUM", "HIGH"}:
            return "CRITICAL" if base == "HIGH" else "HIGH"
        return base

    def estimate_payout(self, category_item: FindingCategory, raw_finding: dict[str, Any]) -> int:
        severity = self.estimate_severity(category_item.category_id, raw_finding)
        mult = {"LOW": 0.8, "MEDIUM": 1.0, "HIGH": 1.25, "CRITICAL": 1.5}[severity]
        quality_mult = 1.1 if raw_finding.get("proof_of_concept") else 0.95
        return int(round(category_item.average_payout_usd * mult * quality_mult))

    def categorize_finding(self, raw_finding: dict[str, Any]) -> dict[str, Any]:
        vuln_type = str(raw_finding.get("vulnerability_type", "")).strip()
        if not vuln_type:
            vuln_type = "Information Disclosure"

        key = self._normalize(vuln_type)
        category_item = self.taxonomy.get(key)
        if not category_item:
            fallback = FindingCategory(
                category_id="other",
                category_name="Other",
                vulnerability_type=vuln_type,
                prevalence_in_scope=0.1,
                average_payout_usd=1200,
                remediation_complexity="Medium",
                confidence="LOW",
            )
            category_item = fallback

        severity_estimate = self.estimate_severity(category_item.category_id, raw_finding)
        payout_estimate = self.estimate_payout(category_item, raw_finding)

        return {
            "category": category_item.category_name,
            "category_id": category_item.category_id,
            "subcategory": self.determine_subcategory(vuln_type, raw_finding),
            "vulnerability_type": category_item.vulnerability_type,
            "prevalence_in_scope": category_item.prevalence_in_scope,
            "average_payout_usd": category_item.average_payout_usd,
            "remediation_complexity": category_item.remediation_complexity,
            "severity_estimate": severity_estimate,
            "payout_estimate_usd": payout_estimate,
            "confidence": category_item.confidence,
        }

    def categorize_findings(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for finding in findings:
            merged = dict(finding)
            merged["categorization"] = self.categorize_finding(finding)
            out.append(merged)
        return out


__all__ = ["FindingCategorizer", "FindingCategory"]
