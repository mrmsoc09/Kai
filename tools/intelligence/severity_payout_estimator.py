from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DEFAULT_FREQUENCY_PATH = Path("tools/knowledge/bug_bounty_detection_frequency.yaml")
DEFAULT_TARGET_PROFILE_PATH = Path("tools/knowledge/bug_bounty_target_detection_profile.yaml")


class SeverityPayoutEstimator:
    """
    Data-backed severity and payout estimator for detection findings.

    Uses Prompt 5 frequency/payout artifacts and target context adjustments.
    """

    def __init__(
        self,
        frequency_path: str | Path = DEFAULT_FREQUENCY_PATH,
        target_profile_path: str | Path = DEFAULT_TARGET_PROFILE_PATH,
    ) -> None:
        self.frequency_path = Path(frequency_path)
        self.target_profile_path = Path(target_profile_path)

        self.frequency_data = self._read_yaml(self.frequency_path)
        self.target_profile_data = self._read_yaml(self.target_profile_path)

        self.vuln_catalog = self._build_vuln_catalog()

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Missing artifact: {path}")
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid YAML payload: {path}")
        return payload

    @staticmethod
    def _normalize(text: str | None) -> str:
        return (text or "").strip().lower()

    def _build_vuln_catalog(self) -> dict[str, dict[str, Any]]:
        rows = self.frequency_data.get("detection_frequency_analysis", {}).get("ranked_detection_types", [])
        catalog: dict[str, dict[str, Any]] = {}
        for row in rows:
            vuln_type = self._normalize(str(row.get("vulnerability_type", "")))
            if vuln_type:
                catalog[vuln_type] = dict(row)
        return catalog

    def _resolve_vuln_type(self, finding: dict[str, Any]) -> str:
        raw = self._normalize(str(finding.get("vulnerability_type", "")))
        aliases = {
            "xss": "cross-site scripting (xss)",
            "sqli": "sql injection",
            "idor": "insecure direct object reference (idor)",
            "api_authz": "api authorization flaws (bola/bfla)",
            "auth_bypass": "weak authentication / session management",
            "weak_auth": "weak authentication / session management",
            "misconfiguration": "security misconfiguration",
            "crypto": "tls / cryptographic weakness",
            "information_disclosure": "information disclosure",
            "business_logic": "business logic flaws",
            "ssrf": "server-side request forgery (ssrf)",
        }
        return aliases.get(raw, raw)

    def _base_severity(self, vuln_type: str) -> float:
        # CVSS-like baseline from payout and type class.
        row = self.vuln_catalog.get(vuln_type, {})
        payout = float(row.get("average_payout_usd", 1200))

        if payout >= 6000:
            return 8.8
        if payout >= 4500:
            return 8.1
        if payout >= 3000:
            return 7.4
        if payout >= 2000:
            return 6.8
        if payout >= 1200:
            return 6.2
        return 5.6

    def target_adjustment_factor(self, finding: dict[str, Any], target_context: dict[str, Any]) -> float:
        target_type = self._normalize(str(target_context.get("target_type", "")))
        vuln_type = self._resolve_vuln_type(finding)

        if target_type == "fintech_regulated" and (
            "authentication" in vuln_type
            or "authorization" in vuln_type
            or "sql injection" in vuln_type
            or "ssrf" in vuln_type
        ):
            return 9.0
        if target_type == "enterprise_multi_property" and "business logic" in vuln_type:
            return 8.2
        if target_type == "consumer_ecommerce" and "business logic" in vuln_type:
            return 8.6
        if target_type == "early_stage_saas" and "xss" in vuln_type:
            return 7.2
        return 6.5

    def estimate_business_impact(self, finding: dict[str, Any], target_context: dict[str, Any]) -> float:
        target_type = self._normalize(str(target_context.get("target_type", "")))
        vuln_type = self._resolve_vuln_type(finding)

        if "sql injection" in vuln_type:
            return 9.3 if "fintech" in target_type else 8.2
        if "authentication" in vuln_type or "authorization" in vuln_type:
            return 9.1 if "fintech" in target_type else 8.0
        if "business logic" in vuln_type:
            return 8.8 if "ecommerce" in target_type else 8.1
        if "information disclosure" in vuln_type:
            return 7.8
        if "xss" in vuln_type:
            return 7.5 if "fintech" in target_type else 6.4
        return 6.0

    @staticmethod
    def estimate_exploit_difficulty(finding: dict[str, Any]) -> str:
        method = str(finding.get("detection_method", "")).lower()
        if any(k in method for k in ["blind", "timing", "chain", "complex"]):
            return "Hard"
        if any(k in method for k in ["stored", "token", "authz", "api"]):
            return "Medium"
        return "Low-Medium"

    @staticmethod
    def score_to_level(score: float) -> str:
        if score >= 9.0:
            return "CRITICAL"
        if score >= 7.0:
            return "HIGH"
        if score >= 4.0:
            return "MEDIUM"
        return "LOW"

    def estimate_severity(self, finding: dict[str, Any], target_context: dict[str, Any]) -> dict[str, Any]:
        vuln_type = self._resolve_vuln_type(finding)
        base_severity = self._base_severity(vuln_type)
        target_adj = self.target_adjustment_factor(finding, target_context)
        biz_impact = self.estimate_business_impact(finding, target_context)
        exploit_difficulty = self.estimate_exploit_difficulty(finding)

        severity_score = round((base_severity * 0.5) + (target_adj * 0.3) + (biz_impact * 0.2), 2)

        return {
            "severity_score": severity_score,
            "severity_level": self.score_to_level(severity_score),
            "base_severity": round(base_severity, 2),
            "target_adjustment": round(target_adj, 2),
            "business_impact": round(biz_impact, 2),
            "exploit_difficulty": exploit_difficulty,
            "rationale": (
                f"Severity derived from base risk for '{vuln_type}', adjusted for "
                f"target archetype '{target_context.get('target_type', 'unknown')}' and business impact."
            ),
        }

    def target_payout_multiplier(self, target_context: dict[str, Any]) -> float:
        program_type = self._normalize(str(target_context.get("program_type", "platform")))
        target_type = self._normalize(str(target_context.get("target_type", "")))

        mult = 1.0
        if program_type == "direct":
            mult *= 1.4
        if "fintech" in target_type:
            mult *= 1.25
        elif "enterprise" in target_type:
            mult *= 1.15
        return mult

    @staticmethod
    def finding_quality_multiplier(finding: dict[str, Any]) -> float:
        has_poc = bool(finding.get("proof_of_concept"))
        has_repro = bool(finding.get("reproduction_steps"))
        has_remediation = bool(finding.get("remediation_guidance"))

        score = 1.0
        if has_poc:
            score += 0.10
        if has_repro:
            score += 0.08
        if has_remediation:
            score += 0.05
        return round(score, 2)

    def estimate_payout(self, finding: dict[str, Any], target_context: dict[str, Any]) -> dict[str, Any]:
        vuln_type = self._resolve_vuln_type(finding)
        row = self.vuln_catalog.get(vuln_type, {})

        base_payout = float(row.get("average_payout_usd", 1200))
        severity_data = self.estimate_severity(finding, target_context)

        severity_multiplier = round(1.0 + ((severity_data["severity_score"] - 5.0) / 10.0), 2)
        target_multiplier = self.target_payout_multiplier(target_context)
        quality_multiplier = self.finding_quality_multiplier(finding)

        estimated_payout = round(base_payout * severity_multiplier * target_multiplier * quality_multiplier)
        low = int(round(estimated_payout * 0.75))
        high = int(round(estimated_payout * 1.35))

        return {
            "estimated_payout_usd": estimated_payout,
            "payout_range_usd": [low, high],
            "base_payout_usd": int(round(base_payout)),
            "severity_multiplier": severity_multiplier,
            "target_multiplier": round(target_multiplier, 2),
            "quality_multiplier": quality_multiplier,
        }

    def enrich_finding(self, finding: dict[str, Any], target_context: dict[str, Any]) -> dict[str, Any]:
        out = dict(finding)
        out["severity"] = self.estimate_severity(finding, target_context)
        out["payout"] = self.estimate_payout(finding, target_context)
        return out


__all__ = ["SeverityPayoutEstimator"]
