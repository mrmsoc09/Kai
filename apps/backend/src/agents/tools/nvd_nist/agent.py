from __future__ import annotations

import json
import os
from typing import Any

from ..base_tool_agent import BaseToolAgent


class NvdNistAgent(BaseToolAgent):
    """NVD/NIST CVE data agent for nuclei template selection."""

    TOOL_NAME = "nvd-nist"

    def build_command(
        self, target: str, options: dict[str, Any] | None = None
    ) -> list[str]:
        api_key = os.environ.get("NVD_NIST_API_KEY", "")
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
            'keywordSearch': '{target}',
            'resultsPerPage': 20
        }},
        headers=headers,
        timeout=30
    )
    print(json.dumps(r.json() if r.ok else {{}}, default=str))
except Exception as e:
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

        for v in vulns:
            if not isinstance(v, dict):
                continue

            cve = v.get("cve", {})
            cve_id = cve.get("id", "")
            metrics = cve.get("metrics", {})
            cvss = metrics.get("cvssMetricV31", [{}])[0].get("cvssData", {})
            score = cvss.get("baseScore", 0.0)

            severity = "info"
            if score >= 9.0:
                severity = "critical"
            elif score >= 7.0:
                severity = "high"
            elif score >= 4.0:
                severity = "medium"
            elif score > 0:
                severity = "low"

            descs = cve.get("descriptions", [])
            desc = next(
                (d["value"] for d in descs if d.get("lang") == "en"),
                "",
            )

            findings.append(
                {
                    "type": "known_cve",
                    "value": cve_id,
                    "target": target,
                    "severity": severity,
                    "confidence": 0.7,
                    "source_tool": "nvd-nist",
                    "raw_evidence": f"{cve_id}: {desc[:200]}",
                    "context": {
                        "cvss_score": score,
                        "cvss_vector": cvss.get("vectorString", ""),
                        "description": desc[:500],
                    },
                    "recommended_next_tools": ["nuclei_scan", "searchsploit"],
                    "recommended_next_actions": ["run_cve_specific_template"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]], target: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal = []
        noise = []

        for f in findings:
            score = f["context"].get("cvss_score", 0)
            if score >= 7.0:
                signal.append(f)
            elif score >= 4.0:
                f["severity"] = "medium"
                signal.append(f)
            else:
                noise.append(f)

        return signal, noise

    def _generate_next_agent_instructions(
        self, result: dict[str, Any], target: str
    ) -> dict[str, Any]:
        findings = result.get("findings", [])
        cve_ids = [f["value"] for f in findings if f.get("severity") in ["high", "critical"]]
        return {
            "next_agents": ["nuclei_scan", "searchsploit"],
            "cve_ids": cve_ids,
            "operator_summary": (
                f"NVD found {len(findings)} CVEs for {target} version. "
                f"{len(cve_ids)} are high/critical severity. Feeding nuclei "
                f"for CVE-specific template selection."
            ),
        }
