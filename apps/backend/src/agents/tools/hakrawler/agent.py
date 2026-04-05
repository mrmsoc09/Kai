from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from ..base_tool_agent import BaseToolAgent


_STATIC_EXTENSIONS = {".css", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf"}


class HakrawlerAgent(BaseToolAgent):
    TOOL_NAME = "hakrawler"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        _ = options or {}
        return [
            "hakrawler",
            "-url",
            target,
            "-depth",
            "3",
            "-plain",
            "-h",
            "User-Agent: Mozilla/5.0 (Kaison-Hakrawler)",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

        for line in raw_output.strip().splitlines():
            value = line.strip()
            if not value:
                continue

            if value.startswith("http://") or value.startswith("https://"):
                lower = value.lower()
                is_api = "/api/" in lower
                is_js = lower.endswith(".js")
                is_form = "form" in lower or "action=" in lower
                severity = "medium" if (is_api or is_form) else ("low" if is_js else "info")
                findings.append(
                    {
                        "type": "url",
                        "value": value,
                        "target": target,
                        "severity": severity,
                        "confidence": 0.75,
                        "source_tool": self.TOOL_NAME,
                        "raw_evidence": value[:1000],
                        "context": {
                            "is_api": is_api,
                            "is_js": is_js,
                            "is_form_action": is_form,
                        },
                        "recommended_next_tools": ["feroxbuster", "katana", "gf"],
                        "recommended_next_actions": ["content_discovery", "vulnerability_scan"],
                    }
                )
                continue

            for email in email_pattern.findall(value):
                findings.append(
                    {
                        "type": "email",
                        "value": email,
                        "target": target,
                        "severity": "info",
                        "confidence": 0.6,
                        "source_tool": self.TOOL_NAME,
                        "raw_evidence": value[:500],
                        "context": {
                            "is_email": True,
                        },
                        "recommended_next_tools": ["sherlock", "social-analyzer"],
                        "recommended_next_actions": ["osint_enrichment"],
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
            value = finding["value"].lower()
            if f"{finding['target'].lower()}|{finding['type']}|{value}" in known:
                noise.append(finding)
                continue

            if finding["type"] == "url":
                parsed = urlparse(finding["value"])
                target_host = str(finding.get("target", "")).strip().lower()
                parsed_host = parsed.netloc.lower()
                if target_host and parsed_host and not (
                    parsed_host == target_host or parsed_host.endswith(f".{target_host}")
                ):
                    noise.append(finding)
                    continue

                if any(value.endswith(ext) for ext in _STATIC_EXTENSIONS):
                    noise.append(finding)
                    continue

                signal.append(finding)
            else:
                signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        new_urls = [f["value"] for f in signal if str(f.get("value", "")).startswith(("http://", "https://"))]
        form_actions = [f["value"] for f in signal if bool(f.get("context", {}).get("is_form_action"))]

        return {
            "next_agents": ["feroxbuster", "katana", "gf"],
            "new_urls": new_urls,
            "form_actions": form_actions,
            "operator_summary": (
                f"Hakrawler identified {len(new_urls)} in-scope URLs for {target} and "
                f"{len(form_actions)} form-action candidates for injection workflows."
            ),
        }
