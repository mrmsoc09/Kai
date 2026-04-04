from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class HttpxProbeAgent(BaseToolAgent):
    TOOL_NAME = "httpx_probe"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        input_file = opts.get("input_file", "subdomains.txt")
        # Mandatory tech-detect and cdn checks, along with standard status codes and title
        cmd = ["httpx", "-l", input_file, "-silent", "-td", "-cdn", "-status-code", "-title", "-json"]
        # Filtering for interesting status codes (401/403/200/500)
        if opts.get("filter_status"):
            cmd += ["-fc", opts["filter_status"]]
        else:
            # Default: focus on 200/401/403 for BBP
            cmd += ["-mc", "200,401,403,500"]
        
        if opts.get("threads"):
            cmd += ["-t", str(opts["threads"])]
        
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                findings.append({
                    "url": data.get("url", ""),
                    "value": data.get("url", ""),
                    "status_code": data.get("status_code", 0),
                    "title": data.get("title", ""),
                    "tech": data.get("tech", []),
                    "cdn": data.get("cdn", False),
                    "cdn_name": data.get("cdn_name", ""),
                    "content_length": data.get("content_length", 0),
                    "server": data.get("server", ""),
                    "source": "httpx_probe",
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
            # CDN noise - but still signal if status code is interesting (401/403)
            if item.get("cdn") and item.get("status_code") not in [401, 403]:
                item["noise_reason"] = "cdn_hosted_static"
                noise.append(item)
                continue
            
            # Application 403 vs WAF 403 logic
            if item.get("status_code") == 403:
                server = item.get("server", "").lower()
                if "cloudflare" in server or "akamai" in server or item.get("cdn"):
                    item["signal_reason"] = "waf_403"
                    # Still signal, but lower priority for bypassing
                else:
                    item["signal_reason"] = "app_403"
                signal.append(item)
                continue

            if item.get("status_code") == 401:
                item["signal_reason"] = "auth_required"
                signal.append(item)
                continue

            signal.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        urls = [s["url"] for s in signal]
        tech_map = {}
        for s in signal:
            for t in s.get("tech", []):
                tech_map[t] = tech_map.get(t, 0) + 1
        
        return {
            "next_agent": "nuclei_scan",
            "action": "vulnerability_scan",
            "target": target,
            "input_urls": urls,
            "detected_tech": list(tech_map.keys()),
            "instructions": (
                f"Probed {len(urls)} live hosts. "
                f"Tech stack detected: {', '.join(list(tech_map.keys())[:10])}. "
                "Trigger nuclei scan with tech-specific templates. "
                "Focus on 401/403 endpoints for bypass attempts."
            ),
        }
