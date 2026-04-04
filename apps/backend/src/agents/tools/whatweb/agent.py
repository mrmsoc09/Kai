from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


_NOISE_TECH = {"html5", "utf-8", "jquery", "javascript"}

_TEMPLATE_MAP = {
    "spring": ["spring-actuator", "spring-core-cves"],
    "wordpress": ["wordpress-cves", "wp-plugin-audit"],
    "apache": ["apache-httpd-cves", "apache-path-traversal"],
    "nginx": ["nginx-misconfig", "nginx-cves"],
    "iis": ["microsoft-iis", "aspnet-cves"],
}


class WhatwebAgent(BaseToolAgent):
    TOOL_NAME = "whatweb"
    def _get_tool_name(self) -> str:
        return self.TOOL_NAME


    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        output_file = opts.get("output_file", f"{opts.get('artifact_dir', '/tmp')}/whatweb.json")
        return ["whatweb", f"--log-json={output_file}", "--aggression", str(opts.get("aggression", 1)),
                "--open-timeout=30", "--read-timeout=60", target]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            plugins = payload.get("plugins", {})
            if not isinstance(plugins, dict):
                continue

            for tech_name, details in plugins.items():
                if not isinstance(tech_name, str):
                    continue
                detail_text = ""
                version = ""
                if isinstance(details, dict):
                    strings = details.get("string")
                    versions = details.get("version")
                    if isinstance(strings, list):
                        detail_text = ", ".join(str(v) for v in strings[:5])
                    if isinstance(versions, list) and versions:
                        version = str(versions[0])
                value = tech_name if not version else f"{tech_name} {version}"
                findings.append(
                    {
                        "type": "technology_fingerprint",
                        "value": value,
                        "target": target,
                        "severity": "info",
                        "confidence": 0.85 if version else 0.7,
                        "source_tool": self.TOOL_NAME,
                        "raw_evidence": line,
                        "context": {
                            "technology_category": self._categorize_technology(tech_name),
                            "version": version,
                            "detail": detail_text,
                        },
                        "recommended_next_tools": ["nuclei_scan"],  # searchsploit added in Wave 3
                        "recommended_next_actions": ["select_templates_by_stack", "correlate_versions_with_cves"],
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
            value = str(finding.get("value", "")).lower()
            if f"{finding.get('target', '').lower()}|technology_fingerprint|{value}" in known:
                noise.append(finding)
                continue

            if any(token in value for token in _NOISE_TECH):
                finding["confidence"] = 0.4
                noise.append(finding)
                continue
            if str(finding.get("context", {}).get("version", "")).strip():
                finding["severity"] = "medium"
                finding["confidence"] = 0.92
            signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        detected = [str(item.get("value", "")).strip() for item in signal if str(item.get("value", "")).strip()]
        recommendations: list[str] = []
        for tech in detected:
            lowered = tech.lower()
            for token, templates in _TEMPLATE_MAP.items():
                if token in lowered:
                    recommendations.extend(templates)

        deduped_templates = sorted(set(recommendations))
        return {
            "next_agents": ["nuclei_scan"],  # searchsploit added in Wave 3
            "detected_technologies": detected,
            "template_recommendations": deduped_templates,
            "operator_summary": (
                f"WhatWeb fingerprinted {len(detected)} technologies for {target}. "
                f"Generated {len(deduped_templates)} template recommendations for targeted scanning."
            ),
        }

    @staticmethod
    def _categorize_technology(name: str) -> str:
        token = name.lower()
        if "wordpress" in token or "drupal" in token or "joomla" in token:
            return "cms"
        if "apache" in token or "nginx" in token or "iis" in token or "server" in token:
            return "server"
        if "spring" in token or "rails" in token or "django" in token or "asp.net" in token:
            return "framework"
        if "jquery" in token or "react" in token or "vue" in token:
            return "javascript_library"
        if "waf" in token or "cloudflare" in token or "akamai" in token:
            return "waf_indicator"
        return "other"
