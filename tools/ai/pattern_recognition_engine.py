from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AttackChainPattern:
    name: str
    description: str
    required_vulnerability_types: list[str]
    same_endpoint_required: bool
    same_system_required: bool
    risk_escalation: str
    business_impact: str
    remediation_priority: str
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "required_vulnerability_types": self.required_vulnerability_types,
            "same_endpoint_required": self.same_endpoint_required,
            "same_system_required": self.same_system_required,
            "risk_escalation": self.risk_escalation,
            "business_impact": self.business_impact,
            "remediation_priority": self.remediation_priority,
            "confidence": self.confidence,
        }


class PatternRecognitionEngine:
    """
    Detection-only attack chain pattern recognizer.

    Identifies meaningful chains in already-detected findings. It does not execute
    scans or recommend exploitation.
    """

    def __init__(self) -> None:
        self.patterns = self._build_pattern_library()

    @staticmethod
    def _normalize(value: str | None) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def _vuln_type(finding: dict[str, Any]) -> str:
        return (finding.get("vulnerability_type") or "").strip().lower()

    @staticmethod
    def _endpoint(finding: dict[str, Any]) -> str:
        return (finding.get("target_endpoint") or finding.get("endpoint") or "").strip().lower()

    @staticmethod
    def _system(finding: dict[str, Any]) -> str:
        return (finding.get("target_system") or "").strip().lower()

    def _build_pattern_library(self) -> list[AttackChainPattern]:
        # 16 patterns (target requirement: 15-20)
        return [
            AttackChainPattern(
                name="xss_csrf_chain",
                description="XSS and CSRF on shared endpoint/workflow",
                required_vulnerability_types=["cross-site scripting (xss)", "csrf"],
                same_endpoint_required=True,
                same_system_required=False,
                risk_escalation="Client-side script execution can weaken CSRF controls and session safety.",
                business_impact="High",
                remediation_priority="Critical",
                confidence=0.95,
            ),
            AttackChainPattern(
                name="sqli_info_disclosure_chain",
                description="SQL injection combined with disclosure of schema/details",
                required_vulnerability_types=["sql injection", "information disclosure"],
                same_endpoint_required=False,
                same_system_required=True,
                risk_escalation="Disclosed internals increase precision of safe SQLi validation and impact assessment.",
                business_impact="Critical",
                remediation_priority="Immediate",
                confidence=0.88,
            ),
            AttackChainPattern(
                name="auth_privesc_chain",
                description="Weak auth/session with privilege escalation indicators",
                required_vulnerability_types=["weak authentication / session management", "business logic flaws"],
                same_endpoint_required=False,
                same_system_required=True,
                risk_escalation="Weak initial controls plus authorization weakness can lead to high-impact account takeover paths.",
                business_impact="Critical",
                remediation_priority="Immediate",
                confidence=0.92,
            ),
            AttackChainPattern(
                name="api_abuse_chain",
                description="API authz flaws with weak authentication/rate controls",
                required_vulnerability_types=["api authorization flaws (bola/bfla)", "weak authentication / session management"],
                same_endpoint_required=False,
                same_system_required=True,
                risk_escalation="API misuse risk increases when authorization and identity controls are both weak.",
                business_impact="High",
                remediation_priority="High",
                confidence=0.85,
            ),
            AttackChainPattern(
                name="idor_scale_pattern",
                description="IDOR pattern suggesting systemic object-level authorization gaps",
                required_vulnerability_types=["insecure direct object reference (idor)", "api authorization flaws (bola/bfla)"],
                same_endpoint_required=False,
                same_system_required=True,
                risk_escalation="Object-level control weaknesses tend to replicate across related resources.",
                business_impact="Critical",
                remediation_priority="Immediate",
                confidence=0.90,
            ),
            AttackChainPattern(
                name="ssrf_misconfig_chain",
                description="SSRF paired with misconfiguration exposure",
                required_vulnerability_types=["server-side request forgery (ssrf)", "security misconfiguration"],
                same_endpoint_required=False,
                same_system_required=True,
                risk_escalation="Network control weaknesses and server-side request abuse can expose internal trust boundaries.",
                business_impact="High",
                remediation_priority="High",
                confidence=0.84,
            ),
            AttackChainPattern(
                name="graphql_authz_chain",
                description="GraphQL authz weaknesses plus business logic issues",
                required_vulnerability_types=["graphql schema/authorization misconfiguration", "business logic flaws"],
                same_endpoint_required=False,
                same_system_required=True,
                risk_escalation="Graph-level authorization gaps and workflow flaws can expose sensitive actions.",
                business_impact="High",
                remediation_priority="High",
                confidence=0.81,
            ),
            AttackChainPattern(
                name="secret_exposure_abuse_chain",
                description="Secrets exposure with auth/session weakness",
                required_vulnerability_types=["secrets exposure / credential leakage", "weak authentication / session management"],
                same_endpoint_required=False,
                same_system_required=True,
                risk_escalation="Exposed credentials increase risk of unauthorized access attempts.",
                business_impact="Critical",
                remediation_priority="Immediate",
                confidence=0.93,
            ),
            AttackChainPattern(
                name="open_redirect_auth_flow_chain",
                description="Open redirect in auth/session-related flow",
                required_vulnerability_types=["open redirect", "weak authentication / session management"],
                same_endpoint_required=False,
                same_system_required=True,
                risk_escalation="Redirect weaknesses can increase phishing and token interception risk in auth workflows.",
                business_impact="Medium-High",
                remediation_priority="High",
                confidence=0.79,
            ),
            AttackChainPattern(
                name="cors_xss_chain",
                description="CORS misconfiguration with XSS indicators",
                required_vulnerability_types=["cors misconfiguration", "cross-site scripting (xss)"],
                same_endpoint_required=False,
                same_system_required=True,
                risk_escalation="Cross-origin trust issues plus script injection raise session/data exposure risk.",
                business_impact="High",
                remediation_priority="High",
                confidence=0.83,
            ),
            AttackChainPattern(
                name="path_traversal_disclosure_chain",
                description="Path traversal with information disclosure",
                required_vulnerability_types=["path traversal / arbitrary file read", "information disclosure"],
                same_endpoint_required=False,
                same_system_required=True,
                risk_escalation="File read paths can amplify disclosure of secrets/configuration details.",
                business_impact="High",
                remediation_priority="High",
                confidence=0.82,
            ),
            AttackChainPattern(
                name="tls_auth_chain",
                description="Cryptographic weakness with auth/session issues",
                required_vulnerability_types=["tls / cryptographic weakness", "weak authentication / session management"],
                same_endpoint_required=False,
                same_system_required=False,
                risk_escalation="Weak transport/security posture can amplify authentication session risk.",
                business_impact="High",
                remediation_priority="High",
                confidence=0.77,
            ),
            AttackChainPattern(
                name="misconfig_info_chain",
                description="Security misconfiguration with information disclosure",
                required_vulnerability_types=["security misconfiguration", "information disclosure"],
                same_endpoint_required=False,
                same_system_required=True,
                risk_escalation="Misconfigurations frequently produce recurring sensitive data exposure paths.",
                business_impact="High",
                remediation_priority="High",
                confidence=0.86,
            ),
            AttackChainPattern(
                name="rate_limit_auth_chain",
                description="Rate-limit weakness with auth/session issue",
                required_vulnerability_types=["rate-limit and brute-force weaknesses", "weak authentication / session management"],
                same_endpoint_required=False,
                same_system_required=True,
                risk_escalation="Identity controls become more vulnerable when request abuse controls are weak.",
                business_impact="Medium-High",
                remediation_priority="High",
                confidence=0.80,
            ),
            AttackChainPattern(
                name="upload_injection_chain",
                description="File upload validation gaps with injection indicators",
                required_vulnerability_types=["file upload validation gaps", "command injection exposure surface"],
                same_endpoint_required=False,
                same_system_required=True,
                risk_escalation="Upload control gaps can increase server-side command/injection exposure.",
                business_impact="Critical",
                remediation_priority="Immediate",
                confidence=0.76,
            ),
            AttackChainPattern(
                name="subdomain_takeover_secret_chain",
                description="Subdomain takeover signals with secret exposure",
                required_vulnerability_types=["subdomain takeover / dns misconfiguration", "secrets exposure / credential leakage"],
                same_endpoint_required=False,
                same_system_required=False,
                risk_escalation="DNS/control-plane weaknesses can compound leaked secret risk across assets.",
                business_impact="High",
                remediation_priority="High",
                confidence=0.78,
            ),
        ]

    def pattern_library_summary(self) -> dict[str, Any]:
        return {
            "pattern_count": len(self.patterns),
            "patterns": [p.as_dict() for p in self.patterns],
        }

    def _matches_type(self, finding_type: str, required_type: str) -> bool:
        f = self._normalize(finding_type)
        r = self._normalize(required_type)
        return f == r or r in f or f in r

    def _collect_matches(self, findings: list[dict[str, Any]], required_type: str) -> list[dict[str, Any]]:
        out = []
        for finding in findings:
            if self._matches_type(self._vuln_type(finding), required_type):
                out.append(finding)
        return out

    def _same_endpoint_condition(self, matches: list[list[dict[str, Any]]]) -> tuple[bool, list[dict[str, Any]]]:
        endpoint_map: dict[str, list[dict[str, Any]]] = {}
        for group in matches:
            for finding in group:
                endpoint = self._endpoint(finding)
                if not endpoint:
                    continue
                endpoint_map.setdefault(endpoint, []).append(finding)

        for _, grouped in endpoint_map.items():
            types = {self._vuln_type(x) for x in grouped}
            if len(types) >= 2:
                return True, grouped
        return False, []

    def _same_system_condition(self, matches: list[list[dict[str, Any]]]) -> tuple[bool, list[dict[str, Any]]]:
        system_map: dict[str, list[dict[str, Any]]] = {}
        for group in matches:
            for finding in group:
                system = self._system(finding)
                if not system:
                    continue
                system_map.setdefault(system, []).append(finding)

        for _, grouped in system_map.items():
            types = {self._vuln_type(x) for x in grouped}
            if len(types) >= 2:
                return True, grouped
        return False, []

    def calculate_pattern_confidence(
        self,
        pattern: AttackChainPattern,
        indicators_matched: list[dict[str, Any]],
    ) -> float:
        base = pattern.confidence
        confidence_boost = min(0.08, max(0.0, (len(indicators_matched) - 2) * 0.02))
        return round(min(0.99, base + confidence_boost), 2)

    def identify_patterns_in_findings(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        patterns_found: list[dict[str, Any]] = []

        for pattern in self.patterns:
            required = pattern.required_vulnerability_types
            matches = [self._collect_matches(findings, t) for t in required]
            if any(len(group) == 0 for group in matches):
                continue

            if pattern.same_endpoint_required:
                ok, selected = self._same_endpoint_condition(matches)
                if not ok:
                    continue
            elif pattern.same_system_required:
                ok, selected = self._same_system_condition(matches)
                if not ok:
                    continue
            else:
                selected = [x for group in matches for x in group]

            # keep unique findings by id/evidence fallback
            unique: dict[str, dict[str, Any]] = {}
            for finding in selected:
                key = str(finding.get("finding_id") or finding.get("evidence_id") or id(finding))
                unique[key] = finding
            indicators = list(unique.values())

            patterns_found.append(
                {
                    "pattern_name": pattern.name,
                    "description": pattern.description,
                    "indicators_matched": indicators,
                    "risk_escalation": pattern.risk_escalation,
                    "business_impact": pattern.business_impact,
                    "remediation_priority": pattern.remediation_priority,
                    "confidence": self.calculate_pattern_confidence(pattern, indicators),
                    "related_findings": indicators,
                }
            )

        patterns_found.sort(key=lambda x: float(x.get("confidence", 0.0)), reverse=True)
        return patterns_found


__all__ = ["PatternRecognitionEngine", "AttackChainPattern"]
