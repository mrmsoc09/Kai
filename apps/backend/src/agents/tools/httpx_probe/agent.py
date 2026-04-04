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
                url = data.get("url", "")
                findings.append({
                    "type": "url",
                    "url": url,
                    "value": url,
                    "target": target,
                    "severity": "info",
                    "confidence": 0.9,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": line,
                    "context": {
                        "status_code": data.get("status_code", 0),
                        "title": data.get("title", ""),
                        "tech": data.get("tech", []),
                        "cdn": data.get("cdn", False),
                        "cdn_name": data.get("cdn_name", ""),
                        "content_length": data.get("content_length", 0),
                        "server": data.get("server", ""),
                    },
                    "recommended_next_tools": ["naabu", "nuclei_scan"],
                    "recommended_next_actions": ["port_scan", "vulnerability_scan"],
                })
            except json.JSONDecodeError:
                pass
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()
        for item in findings:
            value = item["value"].lower()
            if f"{item['target'].lower()}|url|{value}" in known:
                noise.append(item)
                continue

            # CDN noise - but still signal if status code is interesting (401/403)
            ctx = item["context"]
            if ctx.get("cdn") and ctx.get("status_code") not in [401, 403]:
                item["noise_reason"] = "cdn_hosted_static"
                noise.append(item)
                continue
            
            # Application 403 vs WAF 403 logic
            if ctx.get("status_code") == 403:
                server = ctx.get("server", "").lower()
                if "cloudflare" in server or "akamai" in server or ctx.get("cdn"):
                    item["signal_reason"] = "waf_403"
                    # Still signal, but lower priority for bypassing
                else:
                    item["signal_reason"] = "app_403"
                    item["severity"] = "medium"
                signal.append(item)
                continue

            if ctx.get("status_code") == 401:
                item["signal_reason"] = "auth_required"
                item["severity"] = "medium"
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
            for t in s["context"].get("tech", []):
                tech_map[t] = tech_map.get(t, 0) + 1
        
        return {
            "next_agent": "naabu",
            "action": "port_scan_live_hosts",
            "target": target,
            "input_urls": urls,
            "detected_tech": list(tech_map.keys()),
            "instructions": (
                f"Probed {len(urls)} live hosts. "
                f"Tech stack detected: {', '.join(list(tech_map.keys())[:10])}. "
                "Next Step: Trigger naabu for non-standard port discovery on these live hosts."
            ),
        }
