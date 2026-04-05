from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class FfufAgent(BaseToolAgent):
    TOOL_NAME = "ffuf"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        output_path = f"{artifact_dir}/ffuf.json"
        waf_detected = bool(opts.get("waf_detected", False))
        threads = 5 if waf_detected else int(opts.get("threads", 20))

        if bool(opts.get("vhost", False)):
            domain = str(opts.get("domain", target))
            return [
                "ffuf",
                "-u",
                target,
                "-H",
                f"Host: FUZZ.{domain}",
                "-w",
                str(opts.get("subdomain_wordlist", "/usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt")),
                "-mc",
                "200",
                "-o",
                output_path,
                "-of",
                "json",
                "-t",
                str(threads),
            ]

        cmd = [
            "ffuf",
            "-u",
            f"{target.rstrip('/')}/FUZZ",
            "-w",
            str(opts.get("wordlist", "/usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt")),
            "-mc",
            "200,201,204,301,302,401,403",
            "-o",
            output_path,
            "-of",
            "json",
            "-t",
            str(threads),
            "-timeout",
            str(opts.get("timeout", 10)),
        ]
        if waf_detected:
            cmd.extend(["-rate", str(opts.get("waf_rate", 2))])
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_output = raw_output.strip()
        if not raw_output:
            return findings

        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError:
            payload = {}

        results = payload.get("results", []) if isinstance(payload, dict) else []
        if not isinstance(results, list):
            return findings

        for entry in results:
            if not isinstance(entry, dict):
                continue
            url = str(entry.get("url", "")).strip()
            if not url:
                continue
            status = int(entry.get("status", 0) or 0)
            length = int(entry.get("length", 0) or 0)
            mode = "vhost" if "Host:" in str(entry.get("input", {})) else "url"
            findings.append(
                {
                    "type": mode,
                    "value": url,
                    "target": target,
                    "severity": "medium" if status in {401, 403} else "info",
                    "confidence": 0.8,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(entry, ensure_ascii=True)[:1000],
                    "context": {
                        "status_code": status,
                        "content_length": length,
                        "words": int(entry.get("words", 0) or 0),
                        "lines": int(entry.get("lines", 0) or 0),
                    },
                    "recommended_next_tools": ["arjun", "nuclei_scan"],
                    "recommended_next_actions": ["parameter_discovery", "vulnerability_scan"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()
        clusters: dict[int, int] = {}

        for finding in findings:
            value = finding["value"].lower()
            if f"{finding['target'].lower()}|{finding['type']}|{value}" in known:
                noise.append(finding)
                continue

            length = int(finding.get("context", {}).get("content_length", -1) or -1)
            if length >= 0:
                clusters[length] = clusters.get(length, 0) + 1
                if clusters[length] > 4:
                    noise.append(finding)
                    continue
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        discovered_paths = [f["value"] for f in signal]
        return {
            "next_agents": ["arjun", "nuclei_scan"],
            "discovered_paths": discovered_paths,
            "operator_summary": (
                f"FFUF identified {len(discovered_paths)} actionable paths/vhosts for {target} "
                "after wildcard length filtering."
            ),
        }
