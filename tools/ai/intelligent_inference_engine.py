from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools.ai.ai_operations_safety_gates import AIOperationsSafetyGates, SafetyViolation


@dataclass(slots=True)
class InferenceRule:
    name: str
    trigger_vulnerability_types: list[str]
    trigger_min_count: int
    inference: str
    suggested_testing: str
    rationale: str
    confidence: float
    effort: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "trigger_vulnerability_types": self.trigger_vulnerability_types,
            "trigger_min_count": self.trigger_min_count,
            "inference": self.inference,
            "suggested_testing": self.suggested_testing,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "effort": self.effort,
        }


class IntelligentInferenceEngine:
    """
    Detection-only inference engine.

    Infers likely related vulnerabilities and recommends additional safe testing
    based on already-detected findings.
    """

    def __init__(self, *, safety_gates: AIOperationsSafetyGates | None = None) -> None:
        self.safety_gates = safety_gates or AIOperationsSafetyGates()
        self.rules = self._build_rules()

    @staticmethod
    def _normalize(value: str | None) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def _vuln_type(finding: dict[str, Any]) -> str:
        return (finding.get("vulnerability_type") or "").strip().lower()

    def _build_rules(self) -> list[InferenceRule]:
        # 12 inference rules (target: 10-15)
        return [
            InferenceRule(
                name="xss_to_csrf",
                trigger_vulnerability_types=["cross-site scripting (xss)", "xss"],
                trigger_min_count=1,
                inference="XSS on a workflow often indicates weak request-integrity controls nearby.",
                suggested_testing="Test and validate CSRF protections on the same form/endpoints with safe replay checks.",
                rationale="XSS and CSRF co-occur when output encoding and token validation are both weak.",
                confidence=0.80,
                effort="Low",
            ),
            InferenceRule(
                name="sqli_to_auth_weakness",
                trigger_vulnerability_types=["sql injection", "sqli"],
                trigger_min_count=1,
                inference="SQLi suggests broader validation/control weaknesses in auth-facing paths.",
                suggested_testing="Identify and test authentication/session endpoints for weak token validation and predictable flows.",
                rationale="Input validation gaps often correlate with adjacent auth/session control gaps.",
                confidence=0.75,
                effort="Medium",
            ),
            InferenceRule(
                name="idor_to_systemic_authz",
                trigger_vulnerability_types=["insecure direct object reference (idor)", "idor"],
                trigger_min_count=1,
                inference="IDOR in one resource often indicates systemic object-level authorization weakness.",
                suggested_testing="Test and identify similar object-id endpoints in-scope for authorization consistency checks.",
                rationale="Authorization defects usually replicate in shared endpoint patterns.",
                confidence=0.85,
                effort="Medium",
            ),
            InferenceRule(
                name="weak_auth_to_privesc",
                trigger_vulnerability_types=["weak authentication / session management", "auth bypass", "weak_auth"],
                trigger_min_count=1,
                inference="Weak auth increases likelihood of privilege control weaknesses.",
                suggested_testing="Validate role boundaries and test horizontal/vertical authorization controls safely.",
                rationale="Identity weaknesses frequently pair with weak authorization boundaries.",
                confidence=0.78,
                effort="Medium",
            ),
            InferenceRule(
                name="api_key_disclosure_to_api_access_review",
                trigger_vulnerability_types=["information disclosure", "secrets exposure / credential leakage"],
                trigger_min_count=1,
                inference="Disclosed secrets often imply additional unauthorized API access paths.",
                suggested_testing="Identify and test in-scope API routes for key scope and authorization boundary validation.",
                rationale="Credential disclosure can expand effective attack surface if controls are weak.",
                confidence=0.90,
                effort="Low",
            ),
            InferenceRule(
                name="multi_auth_findings_to_enumeration",
                trigger_vulnerability_types=["weak authentication / session management", "api authorization flaws (bola/bfla)"],
                trigger_min_count=2,
                inference="Multiple auth-related issues may indicate account enumeration paths.",
                suggested_testing="Test and verify user/account enumeration signals in login, registration, and recovery flows.",
                rationale="Auth control fragmentation can leak user-state metadata.",
                confidence=0.72,
                effort="Low",
            ),
            InferenceRule(
                name="misconfig_to_disclosure",
                trigger_vulnerability_types=["security misconfiguration", "misconfiguration"],
                trigger_min_count=1,
                inference="Misconfiguration frequently correlates with information disclosure.",
                suggested_testing="Identify and validate debug/error metadata exposure on related endpoints.",
                rationale="Configuration drift often exposes sensitive server/runtime details.",
                confidence=0.82,
                effort="Low",
            ),
            InferenceRule(
                name="ssrf_to_internal_surface",
                trigger_vulnerability_types=["server-side request forgery (ssrf)", "ssrf"],
                trigger_min_count=1,
                inference="SSRF indicators suggest broader internal request boundary risk.",
                suggested_testing="Test and verify outbound request policy enforcement against in-scope allowlist rules.",
                rationale="Request proxy behavior can expose internal metadata/services when filtering is weak.",
                confidence=0.84,
                effort="Medium",
            ),
            InferenceRule(
                name="cors_plus_xss_risk",
                trigger_vulnerability_types=["cors misconfiguration", "cross-site scripting (xss)", "xss"],
                trigger_min_count=2,
                inference="CORS misconfig plus XSS elevates cross-origin data/session risk.",
                suggested_testing="Validate cross-origin credential handling and test origin restrictions on affected endpoints.",
                rationale="Script execution plus broad origin trust compounds data exposure.",
                confidence=0.83,
                effort="Medium",
            ),
            InferenceRule(
                name="rate_limit_to_credential_abuse",
                trigger_vulnerability_types=["rate-limit and brute-force weaknesses", "weak authentication / session management"],
                trigger_min_count=2,
                inference="Weak rate controls and auth weaknesses increase credential abuse risk.",
                suggested_testing="Test and verify lockout/challenge behavior under safe throttled request patterns.",
                rationale="Combined controls determine resistance to automated credential attacks.",
                confidence=0.79,
                effort="Low",
            ),
            InferenceRule(
                name="graphql_to_bola",
                trigger_vulnerability_types=["graphql schema/authorization misconfiguration", "api authorization flaws (bola/bfla)"],
                trigger_min_count=1,
                inference="GraphQL authorization gaps often manifest as object-level API authorization flaws.",
                suggested_testing="Identify and test GraphQL object access controls with role-based query validation.",
                rationale="Resolver-level checks often diverge from REST/API authz controls.",
                confidence=0.81,
                effort="Medium",
            ),
            InferenceRule(
                name="path_traversal_to_secret_disclosure",
                trigger_vulnerability_types=["path traversal / arbitrary file read", "information disclosure"],
                trigger_min_count=1,
                inference="Path traversal findings may indicate broader sensitive file disclosure risk.",
                suggested_testing="Validate file path normalization and identify exposure of secrets/config files in-scope.",
                rationale="File path handling flaws can reveal configuration and credential artifacts.",
                confidence=0.80,
                effort="Medium",
            ),
        ]

    def rule_summary(self) -> dict[str, Any]:
        return {"rule_count": len(self.rules), "rules": [r.as_dict() for r in self.rules]}

    def _rule_triggered(self, findings: list[dict[str, Any]], rule: InferenceRule) -> tuple[bool, list[dict[str, Any]]]:
        matched = []
        trigger_types = [self._normalize(x) for x in rule.trigger_vulnerability_types]

        for finding in findings:
            ftype = self._vuln_type(finding)
            if any(tt in ftype or ftype in tt for tt in trigger_types):
                matched.append(finding)

        return len(matched) >= rule.trigger_min_count, matched

    def _priority(self, confidence: float, effort: str, finding: dict[str, Any]) -> str:
        severity = self._normalize(str((finding.get("severity") or {}).get("severity_level", "MEDIUM")))
        effort_norm = self._normalize(effort)
        base = confidence
        if severity == "critical":
            base += 0.08
        elif severity == "high":
            base += 0.04

        if effort_norm == "low":
            base += 0.03
        elif effort_norm == "medium":
            base += 0.0
        else:
            base -= 0.03

        if base >= 0.85:
            return "P1"
        if base >= 0.72:
            return "P2"
        return "P3"

    def infer_related_vulnerabilities(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []

        for rule in self.rules:
            triggered, matched = self._rule_triggered(findings, rule)
            if not triggered:
                continue

            for finding in matched:
                rec = {
                    "finding": finding,
                    "triggered_rule": rule.name,
                    "inference": rule.inference,
                    "suggested_testing": rule.suggested_testing,
                    "rationale": rule.rationale,
                    "confidence": rule.confidence,
                    "effort": rule.effort,
                    "priority": self._priority(rule.confidence, rule.effort, finding),
                }
                try:
                    self.safety_gates.validate_ai_recommendation(rec)
                except SafetyViolation:
                    rec = self.safety_gates.sanitize_recommendation(rec)
                    self.safety_gates.validate_ai_recommendation(rec)
                recommendations.append(rec)

        recommendations.sort(
            key=lambda r: (
                {"P1": 3, "P2": 2, "P3": 1}.get(str(r.get("priority", "P3")), 1),
                float(r.get("confidence", 0.0)),
            ),
            reverse=True,
        )
        return recommendations


__all__ = ["IntelligentInferenceEngine", "InferenceRule"]
