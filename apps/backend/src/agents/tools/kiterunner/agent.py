from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class KiterunnerAgent(BaseToolAgent):
    TOOL_NAME = "kiterunner"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        # Kiterunner for API endpoint discovery
        # target is the URL to scan
        cmd = ["kr", "scan", target]
        
        # Wordlist: Use .kite files for structured API discovery
        wordlist = opts.get("wordlist", "/usr/share/kiterunner/wordlists/routes-large.kite")
        cmd += ["-w", wordlist]
        
        if opts.get("threads"):
            cmd += ["-c", str(opts["threads"])]
            
        if opts.get("fail_status_codes"):
            cmd += ["--fail-status-codes", opts["fail_status_codes"]]
            
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        # Kiterunner output format: [METHOD] [STATUS] [LENGTH] [URL]
        for line in raw_output.splitlines():
            line = line.strip()
            if not line or not line.startswith("["):
                continue
            
            # Example: [GET] [200] [1234] http://target.com/api/v1/users
            parts = line.split()
            if len(parts) >= 4:
                method = parts[0].strip("[]")
                status = parts[1].strip("[]")
                length = parts[2].strip("[]")
                url = parts[3]
                
                findings.append({
                    "url": url,
                    "value": url,
                    "method": method,
                    "status_code": status,
                    "content_length": length,
                    "source": "kiterunner",
                    "target": target,
                })
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        for item in findings:
            status = item.get("status_code", "0")
            # 200, 401, 403, 405 are all interesting for API endpoints
            if status in ["200", "401", "403", "405"]:
                item["signal_reason"] = "api_endpoint_discovered"
                signal.append(item)
            else:
                noise.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        urls = [s["url"] for s in signal]
        return {
            "next_agent": "vulnerability_scanner",
            "action": "scan_api_endpoints",
            "target": target,
            "input_urls": urls,
            "instructions": (
                f"Kiterunner discovered {len(urls)} API endpoints. "
                "Trigger specialized API scanning (e.g., using postman collections or specialized nuclei templates) "
                "to find IDORs, mass assignment, or authentication bypasses."
            ),
        }
