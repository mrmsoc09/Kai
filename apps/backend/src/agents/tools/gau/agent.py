from __future__ import annotations

import re
from typing import Any

from ..base_tool_agent import BaseToolAgent

# Extensions indicating high-value files
_HIGH_VALUE_EXTENSIONS = {
    ".php", ".asp", ".aspx", ".jsp", ".json", ".xml",
    ".config", ".bak", ".sql", ".log", ".env", ".key",
    ".pem", ".yaml", ".yml",
}

# High-signal path prefixes
_HIGH_SIGNAL_PATHS = {
    "/admin", "/api/", "/internal", "/debug", "/test",
    "/dev", "/.git", "/.env", "/config", "/backup",
    "/graphql", "/swagger", "/openapi", "/console",
    "/mgmt", "/management", "/v1/", "/v2/", "/v3/",
}

# High-value parameter names for injection testing
_INJECTION_PARAMS = {
    "id", "file", "url", "path", "user", "redirect",
    "return", "next", "target", "src", "dest", "destination",
    "page", "action", "cmd", "command", "exec", "query",
    "search", "q", "input", "data", "load", "include",
}

_NOISE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".svg",
                     ".ico", ".woff", ".woff2", ".ttf", ".eot"}


class GauAgent(BaseToolAgent):
    TOOL_NAME = "gau"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        cmd = ["gau", target, "--subs"]
        if opts.get("providers"):
            cmd += ["--providers", ",".join(opts["providers"])]
        # Implement 900s timeout for deep archive retrieval by default
        timeout = opts.get("timeout", 900)
        cmd += ["--timeout", str(timeout)]
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.splitlines():
            url = line.strip()
            if not url:
                continue
            if not url.startswith(("http://", "https://")):
                continue
            # Extract parameters
            params: list[str] = []
            if "?" in url:
                qs = url.split("?", 1)[1]
                params = [p.split("=")[0] for p in qs.split("&") if "=" in p]
            # Extract path
            try:
                path = "/" + url.split("/", 3)[3] if url.count("/") >= 3 else "/"
            except IndexError:
                path = "/"
            # Extension
            path_no_qs = path.split("?")[0]
            ext = ""
            if "." in path_no_qs.split("/")[-1]:
                ext = "." + path_no_qs.rsplit(".", 1)[-1].lower()
            findings.append({
                "type": "url",
                "url": url,
                "value": url,
                "target": target,
                "severity": "info",
                "confidence": 0.8,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": line,
                "context": {
                    "path": path,
                    "extension": ext,
                    "parameters": params,
                },
                "recommended_next_tools": ["paramspider", "httpx_probe"],
                "recommended_next_actions": ["extract_parameters", "probe_http"],
            })
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()
        seen_urls: set[str] = set()
        for item in findings:
            url = item["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            value = item["value"].lower()
            if f"{item['target'].lower()}|url|{value}" in known:
                noise.append(item)
                continue

            path = item["context"]["path"].lower()
            ext = item["context"]["extension"]
            params = item["context"]["parameters"]
            # Static asset noise
            if ext in _NOISE_EXTENSIONS:
                item["noise_reason"] = "static_asset"
                noise.append(item)
                continue
            # High-signal path
            if any(path.startswith(p) for p in _HIGH_SIGNAL_PATHS):
                item["signal_reason"] = "high_signal_path"
                item["severity"] = "medium"
                signal.append(item)
                continue
            # Injection parameter
            injection_params = [p for p in params if p.lower() in _INJECTION_PARAMS]
            if injection_params:
                item["signal_reason"] = "injection_parameter"
                item["severity"] = "medium"
                item["context"]["injection_params"] = injection_params
                signal.append(item)
                continue
            # High-value extension
            if ext in _HIGH_VALUE_EXTENSIONS:
                item["signal_reason"] = "high_value_extension"
                item["severity"] = "medium"
                signal.append(item)
                continue
            # Default noise for plain paths without parameters
            if not params:
                item["noise_reason"] = "no_parameters_plain_path"
                noise.append(item)
                continue
            signal.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        injection_urls = [s["url"] for s in signal if s.get("signal_reason") == "injection_parameter"]
        high_signal_paths = [s["url"] for s in signal if s.get("signal_reason") == "high_signal_path"]
        all_params = list({p for s in signal for p in s.get("parameters", [])})
        return {
            "next_agent": "paramspider",
            "action": "extract_parameters",
            "target": target,
            "priority_urls": injection_urls[:20],
            "high_signal_paths": high_signal_paths[:20],
            "discovered_parameter_names": all_params[:50],
            "total_signal_urls": len(signal),
            "instructions": (
                f"Found {len(signal)} signal URLs. "
                f"{len(injection_urls)} have injection-candidate parameters. "
                "Feed to paramspider and arjun for parameter discovery. "
                "Use httpx to verify which URLs are still live before testing."
            ),
        }
