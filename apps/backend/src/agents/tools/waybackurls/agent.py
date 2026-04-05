from __future__ import annotations

from typing import Any

from ..base_tool_agent import BaseToolAgent

_HIGH_SIGNAL_PATHS = {
    "/admin", "/api/", "/internal", "/debug", "/test",
    "/dev", "/.git", "/.env", "/config", "/backup",
    "/graphql", "/swagger", "/openapi", "/console",
    "/v1/", "/v2/", "/v3/",
}
_HIGH_VALUE_EXTENSIONS = {
    ".php", ".asp", ".aspx", ".jsp", ".json", ".xml",
    ".config", ".bak", ".sql", ".log", ".env", ".key",
}
_NOISE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".svg",
                     ".ico", ".woff", ".woff2", ".ttf", ".eot", ".css"}
_INJECTION_PARAMS = {
    "id", "file", "url", "path", "user", "redirect",
    "return", "next", "target", "src", "dest", "page",
    "action", "cmd", "command", "exec", "query", "q",
}

class WaybackurlsAgent(BaseToolAgent):
    TOOL_NAME = "waybackurls"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        # Focus on date-filtered archived URLs by enabling -dates by default
        return ["sh", "-c", f"echo {target} | waybackurls -dates"]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
            # Handle optional date prefix "YYYY-MM-DD URL"
            date = ""
            url = line
            parts = line.split(" ", 1)
            if len(parts) == 2 and len(parts[0]) == 10 and parts[0][4] == "-":
                date = parts[0]
                url = parts[1]
            if not url.startswith(("http://", "https://")):
                continue
            params: list[str] = []
            if "?" in url:
                qs = url.split("?", 1)[1]
                params = [p.split("=")[0] for p in qs.split("&") if "=" in p]
            try:
                path = "/" + url.split("/", 3)[3] if url.count("/") >= 3 else "/"
            except IndexError:
                path = "/"
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
                    "archived_date": date,
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
            if ext in _NOISE_EXTENSIONS:
                item["noise_reason"] = "static_asset"
                noise.append(item)
                continue
            if any(path.startswith(p) for p in _HIGH_SIGNAL_PATHS):
                item["signal_reason"] = "high_signal_path"
                item["severity"] = "medium"
                signal.append(item)
                continue
            injection_params = [p for p in params if p.lower() in _INJECTION_PARAMS]
            if injection_params:
                item["signal_reason"] = "injection_parameter"
                item["severity"] = "medium"
                item["context"]["injection_params"] = injection_params
                signal.append(item)
                continue
            if ext in _HIGH_VALUE_EXTENSIONS:
                item["signal_reason"] = "high_value_extension"
                item["severity"] = "medium"
                signal.append(item)
                continue
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
        legacy_urls = [
            s["url"] for s in signal
            if s.get("archived_date", "") and s["archived_date"] < "2020-01-01"
        ]
        return {
            "next_agent": "paramspider",
            "action": "extract_parameters",
            "target": target,
            "priority_urls": injection_urls[:20],
            "legacy_urls": legacy_urls[:10],
            "total_signal_urls": len(signal),
            "instructions": (
                f"Found {len(signal)} signal URLs from Wayback Machine. "
                f"{len(legacy_urls)} are legacy URLs (pre-2020) which may expose old endpoints. "
                "Combine with gau output, deduplicate, then feed to paramspider."
            ),
        }
