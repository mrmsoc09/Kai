from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class SearchsploitAgent(BaseToolAgent):
    TOOL_NAME = "searchsploit"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        version = str(opts.get("software_version", target))
        return [
            "searchsploit",
            "--json",
            version,
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_output = raw_output.strip()
        if not raw_output:
            return findings

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            return findings

        results = data.get("RESULTS", [])
        if not isinstance(results, list):
            return findings

        for result in results:
            if not isinstance(result, dict):
                continue

            title = str(result.get("Title", ""))
            exploit_type = str(result.get("Type", "")).lower()

            severity_map = {
                "remote code execution": "critical",
                "privilege escalation": "high",
                "sql injection": "high",
                "authentication bypass": "high",
                "xss": "medium",
                "denial of service": "low",
            }

            severity = "medium"
            for key_pattern, sev in severity_map.items():
                if key_pattern.lower() in title.lower():
                    severity = sev
                    break

            skip_types = ["local", "dos", "denial"]
            if any(skip in exploit_type for skip in skip_types):
                continue

            findings.append(
                {
                    "type": "known_cve_match",
                    "value": title,
                    "target": target,
                    "severity": severity,
                    "confidence": 0.85,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(result)[:500],
                    "context": {
                        "exploitdb_id": result.get("EDB-ID", ""),
                        "type": exploit_type,
                        "platform": result.get("Platform", ""),
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent", "nuclei_scan"],
                    "recommended_next_actions": ["cve_validation"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()

        for finding in findings:
            key = f"{finding['target'].lower()}|cve|{finding['value'].lower()}"
            if key in known:
                noise.append(finding)
                continue

            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        critical = [f for f in signal if f.get("severity") == "critical"]
        high = [f for f in signal if f.get("severity") == "high"]
        return {
            "next_agents": ["EvidenceAnalystAgent", "nuclei_scan"],
            "total_matches": len(signal),
            "critical_cves": len(critical),
            "high_cves": len(high),
            "operator_summary": (
                f"SearchSploit matched {len(signal)} known exploits for {target}. "
                f"Critical: {len(critical)}, High: {len(high)}. "
                "Feed critical CVE IDs to Nuclei for template-based validation."
            ),
        }
