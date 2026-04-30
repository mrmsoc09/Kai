from __future__ import annotations

import json
from typing import Any

from apps.backend.src.core.secret_manager import get_secret_manager
from ..base_tool_agent import BaseToolAgent


class NvdNistAgent(BaseToolAgent):
    """NVD/NIST CVE data agent for nuclei template selection."""

    TOOL_NAME = "nvd-nist"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(
        self, target: str, options: dict[str, Any] | None = None
    ) -> list[str]:
        opts = options or {}
        prior = opts.get("prior_phase_findings", {})
        version = target
        if isinstance(prior, dict):
            candidate = prior.get("software_version")
            if isinstance(candidate, str) and candidate.strip():
                version = candidate.strip()

        api_key = get_secret_manager().get_optional("NVD_NIST_API_KEY") or ""
        return [
            "python3",
            "-c",
            f"""
import requests, json
headers = {{'apiKey': '{api_key}'}} if '{api_key}' else {{}}
try:
    r = requests.get(
        'https://services.nvd.nist.gov/rest/json/cves/2.0',
        params={{
            'keywordSearch': '{version}',
            'resultsPerPage': 20
        }},
        headers=headers,
        timeout=30
    )
    print(json.dumps(r.json() if r.ok else {{}}, default=str))
except Exception:
    print(json.dumps({{}}, default=str))
""",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        try:
            data = json.loads(raw_output.strip())
        except (json.JSONDecodeError, TypeError):
            return findings

        if not isinstance(data, dict):
            return findings

        vulns = data.get("vulnerabilities", [])
        if not isinstance(vulns, list):
            return findings

        for item in vulns:
            if not isinstance(item, dict):
                continue

            cve = item.get("cve", {})
            if not isinstance(cve, dict):
                continue

            cve_id = cve.get("id", "")
            metrics = cve.get("metrics", {})
            if not isinstance(metrics, dict):
                metrics = {}

            cvss = self._extract_cvss_data(metrics)
            score = float(cvss.get("baseScore", 0.0) or 0.0)

            severity = "info"
            if score >= 9.0:
                severity = "critical"
            elif score >= 7.0:
                severity = "high"
            elif score >= 4.0:
                severity = "medium"
            elif score > 0:
                severity = "low"

            descriptions = cve.get("descriptions", [])
            description = ""
            if isinstance(descriptions, list):
                description = next(
                    (
                        str(desc.get("value", ""))
                        for desc in descriptions
                        if isinstance(desc, dict) and desc.get("lang") == "en"
                    ),
                    "",
                )

            findings.append(
                {
                    "type": "known_cve",
                    "value": cve_id,
                    "target": target,
                    "severity": severity,
                    "confidence": 0.7,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": f"{cve_id}: {description[:200]}",
                    "context": {
                        "cvss_score": score,
                        "cvss_vector": cvss.get("vectorString", ""),
                        "description": description[:500],
                    },
                    "recommended_next_tools": ["nuclei_scan", "searchsploit"],
                    "recommended_next_actions": ["run_cve_specific_template"],
                }
            )

        return findings

    @staticmethod
    def _extract_cvss_data(metrics: dict[str, Any]) -> dict[str, Any]:
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            collection = metrics.get(key, [])
            if not isinstance(collection, list) or not collection:
                continue
            first = collection[0]
            if not isinstance(first, dict):
                continue
            data = first.get("cvssData", {})
            if isinstance(data, dict):
                return data
        return {}

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []

        for finding in findings:
            score = float(finding.get("context", {}).get("cvss_score", 0) or 0)
            if score >= 7.0:
                signal.append(finding)
            elif score >= 4.0:
                finding["severity"] = "medium"
                signal.append(finding)
            else:
                noise.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        cve_ids = [
            finding.get("value", "")
            for finding in signal
            if finding.get("severity") in {"high", "critical"}
        ]
        return {
            "next_agents": ["nuclei_scan", "searchsploit"],
            "cve_ids": cve_ids,
            "operator_summary": (
                f"NVD found {len(signal)} CVEs for {target} version. "
                f"{len(cve_ids)} are high/critical severity. Feeding nuclei "
                "for CVE-specific template selection."
            ),
        }
