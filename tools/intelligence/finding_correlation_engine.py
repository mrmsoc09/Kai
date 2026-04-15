from __future__ import annotations

from typing import Any


class FindingCorrelationEngine:
    """
    Correlates detection findings into related-risk clusters.

    Detection-only: provides analyst recommendations and reporting groupings,
    no execution or exploitation logic.
    """

    @staticmethod
    def _normalize(value: str | None) -> str:
        return (value or "").strip().lower()

    def _vuln_type(self, finding: dict[str, Any]) -> str:
        return self._normalize(str(finding.get("vulnerability_type", "")))

    def _endpoint(self, finding: dict[str, Any]) -> str:
        return self._normalize(str(finding.get("target_endpoint", "") or finding.get("endpoint", "")))

    def _system(self, finding: dict[str, Any]) -> str:
        return self._normalize(str(finding.get("target_system", "")))

    def should_correlate(self, finding: dict[str, Any], cluster: dict[str, Any]) -> bool:
        anchor = cluster["primary_vulnerability"]
        a_type = self._vuln_type(anchor)
        b_type = self._vuln_type(finding)

        a_ep = self._endpoint(anchor)
        b_ep = self._endpoint(finding)
        if a_ep and b_ep and a_ep == b_ep:
            if a_type == b_type:
                return True
            high_signal_pairs = {
                ("cross-site scripting (xss)", "csrf"),
                ("information disclosure", "sql injection"),
                ("security misconfiguration", "information disclosure"),
                ("weak authentication / session management", "insecure direct object reference (idor)"),
                ("api authorization flaws (bola/bfla)", "business logic flaws"),
            }
            return (a_type, b_type) in high_signal_pairs or (b_type, a_type) in high_signal_pairs

        a_sys = self._system(anchor)
        b_sys = self._system(finding)
        if a_sys and b_sys and a_sys == b_sys:
            return a_type == b_type

        return False

    def identify_related_risks(self, finding: dict[str, Any]) -> list[str]:
        vuln_type = self._vuln_type(finding)

        related_risks = {
            "cross-site scripting (xss)": [
                "csrf",
                "session hijacking risk",
                "account workflow abuse",
            ],
            "sql injection": [
                "information disclosure",
                "authorization bypass",
                "data integrity compromise",
            ],
            "weak authentication / session management": [
                "account takeover",
                "privilege escalation",
                "session replay risk",
            ],
            "server-side request forgery (ssrf)": [
                "internal service exposure",
                "cloud metadata exposure",
                "network trust boundary bypass",
            ],
            "information disclosure": [
                "credential leakage",
                "attack surface expansion",
                "sensitive metadata exposure",
            ],
            "business logic flaws": [
                "financial abuse",
                "workflow tampering",
                "authorization model gaps",
            ],
        }
        return related_risks.get(vuln_type, [])

    def suggest_related_testing(self, finding: dict[str, Any]) -> list[dict[str, Any]]:
        vuln_type = self._vuln_type(finding)
        out: list[dict[str, Any]] = []

        if "xss" in vuln_type:
            out.append(
                {
                    "suggestion": "Validate anti-CSRF controls on forms sharing the affected origin.",
                    "rationale": "Client-side script execution can weaken CSRF defenses.",
                    "effort": "minimal",
                }
            )
        if "information disclosure" in vuln_type:
            out.append(
                {
                    "suggestion": "Review disclosed metadata/secrets for additional in-scope detection vectors.",
                    "rationale": "Leaked details often reveal adjacent reportable misconfigurations.",
                    "effort": "medium",
                }
            )
        if "sql injection" in vuln_type:
            out.append(
                {
                    "suggestion": "Assess related endpoints using safe, non-destructive input validation checks.",
                    "rationale": "Shared query patterns often replicate across route families.",
                    "effort": "medium",
                }
            )
        return out

    def correlate_findings(self, categorized_findings: list[dict[str, Any]]) -> dict[str, Any]:
        clusters: list[dict[str, Any]] = []

        for finding in categorized_findings:
            assigned = False
            for cluster in clusters:
                if self.should_correlate(finding, cluster):
                    cluster["findings"].append(finding)
                    cluster["related_risks"] = sorted(
                        set(cluster["related_risks"] + self.identify_related_risks(finding))
                    )
                    cluster["suggested_testing"] += self.suggest_related_testing(finding)
                    assigned = True
                    break

            if not assigned:
                clusters.append(
                    {
                        "primary_vulnerability": finding,
                        "findings": [finding],
                        "related_risks": self.identify_related_risks(finding),
                        "suggested_testing": self.suggest_related_testing(finding),
                    }
                )

        for idx, cluster in enumerate(clusters, start=1):
            cluster["cluster_id"] = f"cluster-{idx:03d}"
            cluster["cluster_size"] = len(cluster["findings"])

        return {
            "correlation_clusters": clusters,
            "cluster_count": len(clusters),
            "multi_finding_clusters": sum(1 for c in clusters if c["cluster_size"] > 1),
        }


__all__ = ["FindingCorrelationEngine"]
