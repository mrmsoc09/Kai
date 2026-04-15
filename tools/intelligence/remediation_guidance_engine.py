from __future__ import annotations

from typing import Any


class RemediationGuidanceEngine:
    """
    Generates remediation and verification guidance for detection findings.
    """

    @staticmethod
    def _normalize(value: str | None) -> str:
        return (value or "").strip().lower()

    def _vuln_type(self, finding: dict[str, Any]) -> str:
        return self._normalize(str(finding.get("vulnerability_type", "")))

    def _tech_stack(self, target_context: dict[str, Any]) -> list[str]:
        stack = target_context.get("tech_stack") or []
        if isinstance(stack, str):
            return [stack]
        if isinstance(stack, list):
            return [str(x) for x in stack]
        return []

    def remediation_steps(self, vuln_type: str, target_context: dict[str, Any]) -> list[str]:
        stack = " ".join(self._tech_stack(target_context)).lower()

        if "xss" in vuln_type:
            steps = [
                "Apply context-aware output encoding for HTML/attribute/JavaScript/URL contexts.",
                "Sanitize untrusted HTML with an allowlist sanitizer (for example DOMPurify).",
                "Adopt strict Content-Security-Policy with nonce/hash-based script controls.",
                "Block unsafe inline script sinks and centralize templating helpers.",
            ]
            if "react" in stack or "vue" in stack:
                steps.append("Audit framework escape bypasses (`dangerouslySetInnerHTML`, raw render directives).")
            return steps

        if "sql injection" in vuln_type:
            return [
                "Convert vulnerable queries to parameterized statements/prepared queries.",
                "Enforce allowlist validation for queryable columns, sort fields, and filters.",
                "Apply least-privilege DB roles for application accounts.",
                "Add centralized query-layer protections and SQL error suppression.",
            ]

        if "weak authentication" in vuln_type or "session" in vuln_type or "auth" in vuln_type:
            return [
                "Enforce strong authentication policy and adaptive rate limits on auth endpoints.",
                "Harden session lifecycle (rotation on login/privilege change, short idle timeout).",
                "Use signed, high-entropy, audience-bound tokens with strict expiry checks.",
                "Remove account enumeration signals from error responses and timing patterns.",
            ]

        if "misconfiguration" in vuln_type or "information disclosure" in vuln_type:
            return [
                "Disable debug endpoints and remove verbose error traces in production.",
                "Restrict access to sensitive metadata files, backups, and admin interfaces.",
                "Apply secure default headers and least-exposure server configuration baselines.",
                "Implement secret scanning and rotation for exposed credentials.",
            ]

        if "ssrf" in vuln_type:
            return [
                "Implement outbound request allowlists at application and network layers.",
                "Block internal IP ranges, link-local addresses, and cloud metadata endpoints.",
                "Normalize and re-resolve URLs server-side before request dispatch.",
                "Disable unsafe URL schemes and enforce protocol restrictions.",
            ]

        if "business logic" in vuln_type:
            return [
                "Define and enforce explicit server-side state transition rules.",
                "Require authorization checks on every sensitive business action.",
                "Add anti-automation controls for value-changing or quota-sensitive workflows.",
                "Instrument anomaly detection for workflow abuse indicators.",
            ]

        return [
            "Apply secure-by-default configuration and strict input/output validation.",
            "Add endpoint-specific authorization checks and error-handling hardening.",
            "Document regression tests to prevent reintroduction.",
        ]

    @staticmethod
    def prevention_guidance(vuln_type: str) -> list[str]:
        base = [
            "Adopt threat modeling for new features and APIs before release.",
            "Integrate SAST/DAST checks into CI with security quality gates.",
            "Maintain dependency and configuration baselines with drift detection.",
        ]
        if "xss" in vuln_type:
            base.append("Standardize frontend rendering policies and sink-safe abstractions.")
        if "sql" in vuln_type:
            base.append("Require data-access layer parameterization by policy.")
        if "auth" in vuln_type:
            base.append("Perform periodic authentication and session control audits.")
        return base

    @staticmethod
    def testing_verification_steps(vuln_type: str) -> list[str]:
        return [
            "Re-run the original detection payload and verify non-reproducibility.",
            "Execute negative tests for related endpoints and parameters.",
            "Validate logs/alerts confirm blocked behavior without false positives.",
            f"Add automated regression tests for {vuln_type or 'the vulnerability class'}.",
        ]

    @staticmethod
    def references(vuln_type: str) -> list[str]:
        refs = [
            "https://owasp.org/Top10/",
            "https://cheatsheetseries.owasp.org/",
        ]
        if "xss" in vuln_type:
            refs.append("https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html")
        if "sql" in vuln_type:
            refs.append("https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html")
        if "auth" in vuln_type:
            refs.append("https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html")
        if "ssrf" in vuln_type:
            refs.append("https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html")
        return refs

    @staticmethod
    def estimate_fix_time(vuln_type: str) -> str:
        if any(k in vuln_type for k in ["business logic", "authorization", "auth"]):
            return "2-6 developer days"
        if any(k in vuln_type for k in ["sql injection", "ssrf"]):
            return "1-4 developer days"
        if any(k in vuln_type for k in ["xss", "misconfiguration", "information disclosure"]):
            return "0.5-2 developer days"
        return "1-3 developer days"

    def generate_remediation_guidance(self, finding: dict[str, Any], target_context: dict[str, Any]) -> dict[str, Any]:
        vuln_type = self._vuln_type(finding)
        endpoint = finding.get("target_endpoint") or finding.get("endpoint") or "unknown endpoint"

        summary = (
            f"Detected {finding.get('vulnerability_type', 'security issue')} at {endpoint}. "
            "Issue is reportable within detection-only workflow and should be remediated with server-side controls."
        )

        details = {
            "endpoint": endpoint,
            "parameter": finding.get("vulnerable_parameter") or finding.get("parameter"),
            "detection_method": finding.get("detection_method"),
            "evidence_id": finding.get("evidence_id"),
        }

        return {
            "vulnerability_summary": summary,
            "technical_details": details,
            "remediation_steps": self.remediation_steps(vuln_type, target_context),
            "prevention_guidance": self.prevention_guidance(vuln_type),
            "testing_verification": self.testing_verification_steps(vuln_type),
            "references": self.references(vuln_type),
            "estimated_fix_time": self.estimate_fix_time(vuln_type),
        }


__all__ = ["RemediationGuidanceEngine"]
