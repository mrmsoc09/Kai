from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


_HIGH_VALUE_PATH_TOKENS = {
    "/admin",
    "/api",
    "/internal",
    "/backup",
    "/config",
    "/.git",
    "/swagger",
    "/actuator",
    "/debug",
    "/dev",
    "/test",
    "/staging",
    "/graphql",
    "/v1",
    "/v2",
    "/v3",
}


class FeroxbusterAgent(BaseToolAgent):
    TOOL_NAME = "feroxbuster"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        output_path = f"{artifact_dir}/feroxbuster.json"
        wordlist = opts.get(
            "wordlist",
            "/usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt",
        )
        base_threads = min(int(opts.get("rate_limit", 10)) * 2, 20)
        waf_detected = bool(opts.get("waf_detected", False))

        cmd = [
            "feroxbuster",
            "--url",
            target,
            "--wordlist",
            str(wordlist),
            "--silent",
            "--json",
            "--output",
            output_path,
            "--depth",
            str(opts.get("depth", 3)),
            "--threads",
            str(5 if waf_detected else base_threads),
            "--filter-status",
            "404,429,503",
            "--timeout",
            str(opts.get("timeout", 10)),
            "--no-recursion",
        ]
        if waf_detected:
            cmd.extend(["--rate-limit", str(opts.get("waf_rate_limit", 2))])
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            url = str(entry.get("url", "")).strip()
            if not url:
                continue
            status = int(entry.get("status", 0) or 0)
            content_length = int(entry.get("content_length", 0) or 0)

            is_high = any(token in url.lower() for token in _HIGH_VALUE_PATH_TOKENS)
            severity = "medium" if is_high else "info"
            confidence = 0.85 if is_high else 0.6
            if status in {401, 403}:
                severity = "low" if not is_high else severity
                confidence = max(confidence, 0.75)

            findings.append(
                {
                    "type": "url",
                    "value": url,
                    "target": target,
                    "severity": severity,
                    "confidence": confidence,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": line[:1000],
                    "context": {
                        "status_code": status,
                        "content_length": content_length,
                    },
                    "recommended_next_tools": ["nuclei_scan", "arjun"],
                    "recommended_next_actions": ["probe_endpoint", "parameter_discovery"],
                }
            )
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()
        seen_lengths: dict[int, int] = {}

        for finding in findings:
            value = finding["value"].lower()
            if f"{finding['target'].lower()}|url|{value}" in known:
                noise.append(finding)
                continue

            status = int(finding.get("context", {}).get("status_code", 0) or 0)
            content_length = int(finding.get("context", {}).get("content_length", -1) or -1)

            if content_length >= 0:
                seen_lengths[content_length] = seen_lengths.get(content_length, 0) + 1
                if seen_lengths[content_length] > 3:
                    noise.append(finding)
                    continue

            if status == 404:
                noise.append(finding)
            else:
                signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        admin_paths = [
            f["value"]
            for f in signal
            if "/admin" in str(f.get("value", "")).lower() or "/internal" in str(f.get("value", "")).lower()
        ]
        api_paths = [
            f["value"]
            for f in signal
            if any(t in str(f.get("value", "")).lower() for t in ["/api", "/v1", "/v2", "/v3"])
        ]

        return {
            "next_agents": ["arjun", "nuclei_scan", "gf", "dalfox"],
            "admin_paths": admin_paths,
            "api_paths": api_paths,
            "all_paths_count": len(signal),
            "operator_summary": (
                f"Feroxbuster discovered {len(signal)} paths on {target}. "
                f"Admin/internal: {len(admin_paths)}. API/versioned paths: {len(api_paths)}."
            ),
        }
