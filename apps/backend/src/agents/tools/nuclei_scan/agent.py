from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class NucleiScanAgent(BaseToolAgent):
    TOOL_NAME = "nuclei_scan"

    # Tech-to-Template Mapping for Smart Selection
    TECH_TEMPLATE_MAP = {
        "spring": "tags/spring,tags/java",
        "django": "tags/django,tags/python",
        "flask": "tags/flask,tags/python",
        "wordpress": "tags/wordpress,tags/wp",
        "php": "tags/php",
        "node": "tags/nodejs",
        "react": "tags/react",
        "angular": "tags/angular",
        "laravel": "tags/laravel",
        "iis": "tags/iis",
        "apache": "tags/apache",
        "nginx": "tags/nginx",
        "kubernetes": "tags/k8s",
        "docker": "tags/docker",
    }

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        input_file = opts.get("input_file", "urls.txt")
        # Base nuclei command with JSON output and silent mode
        cmd = ["nuclei", "-l", input_file, "-silent", "-jsonl"]
        
        # Smart Selection: Select templates based on tech output
        tech_list = opts.get("tech_list", [])
        tags = set()
        for tech in tech_list:
            tech = tech.lower()
            for t, tag_list in self.TECH_TEMPLATE_MAP.items():
                if t in tech:
                    tags.update(tag_list.split(","))
        
        if tags:
            cmd += ["-t", ",".join(tags)]
        else:
            # Fallback to general high-impact tags
            cmd += ["-t", "cves,vulnerabilities,misconfiguration,exposure"]
            
        # Priority on severity
        severity = opts.get("severity", "critical,high,medium")
        cmd += ["-s", severity]
        
        if opts.get("threads"):
            cmd += ["-c", str(opts["threads"])]
            
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                info = data.get("info", {})
                findings.append({
                    "template_id": data.get("template-id", ""),
                    "vuln_name": info.get("name", ""),
                    "severity": info.get("severity", ""),
                    "matched_at": data.get("matched-at", ""),
                    "description": info.get("description", ""),
                    "reference": info.get("reference", []),
                    "type": data.get("type", ""),
                    "curl_command": data.get("curl-command", ""),
                    "value": data.get("matched-at", ""),
                    "source": "nuclei",
                    "target": target,
                })
            except json.JSONDecodeError:
                pass
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        for item in findings:
            severity = item.get("severity", "").lower()
            if severity in ["critical", "high"]:
                item["signal_reason"] = "high_severity_vulnerability"
                signal.append(item)
            elif severity == "medium":
                item["signal_reason"] = "medium_severity_vulnerability"
                signal.append(item)
            elif severity == "low":
                item["noise_reason"] = "low_severity_vulnerability"
                noise.append(item)
            else:
                noise.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        critical = [s for s in signal if s.get("severity", "").lower() == "critical"]
        high = [s for s in signal if s.get("severity", "").lower() == "high"]
        
        return {
            "next_agent": "vulnerability_validator",
            "action": "validate_findings",
            "target": target,
            "critical_findings": critical[:10],
            "high_findings": high[:10],
            "instructions": (
                f"Found {len(critical)} critical and {len(high)} high severity vulnerabilities. "
                "Trigger automated validation and screenshot capture for confirmed findings. "
                "Prioritize template IDs: " + ", ".join(set(s["template_id"] for s in critical[:3]))
            ),
        }
