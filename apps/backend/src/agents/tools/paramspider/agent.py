from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

from ..base_tool_agent import BaseToolAgent


_HIGH_VALUE_PARAMS = {
    "id",
    "file",
    "url",
    "path",
    "redirect",
    "next",
    "return",
    "callback",
    "load",
    "fetch",
    "include",
}

_STATIC_SUFFIXES = {".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2"}


class ParamspiderAgent(BaseToolAgent):
    TOOL_NAME = "paramspider"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        output_path = f"{artifact_dir}/paramspider.txt"
        return ["paramspider", "-d", target, "-o", output_path]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.strip().splitlines():
            url = line.strip()
            if not url or "?" not in url:
                continue

            parsed = urlparse(url)
            param_names = sorted(parse_qs(parsed.query, keep_blank_values=True).keys())
            if not param_names:
                continue

            has_high = any(name.lower() in _HIGH_VALUE_PARAMS for name in param_names)
            findings.append(
                {
                    "type": "url",
                    "value": url,
                    "target": target,
                    "severity": "medium" if has_high else "info",
                    "confidence": 0.85 if has_high else 0.7,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": url[:1000],
                    "context": {
                        "parameter_names": param_names,
                        "host": parsed.netloc,
                        "path": parsed.path,
                    },
                    "recommended_next_tools": ["arjun", "dalfox", "sqlmap", "ssrfmap", "gf"],
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
        seen_param_sets: set[tuple[str, ...]] = set()

        for finding in findings:
            value = finding["value"].lower()
            if f"{finding['target'].lower()}|url|{value}" in known:
                noise.append(finding)
                continue

            if any(value.endswith(ext) for ext in _STATIC_SUFFIXES):
                noise.append(finding)
                continue

            params = tuple(sorted(str(p).lower() for p in finding.get("context", {}).get("parameter_names", [])))
            if not params or params in seen_param_sets:
                noise.append(finding)
                continue
            seen_param_sets.add(params)
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        unique_params = sorted(
            {
                str(param).lower()
                for finding in signal
                for param in finding.get("context", {}).get("parameter_names", [])
                if str(param).strip()
            }
        )

        potential_sqli = [p for p in unique_params if p in {"id", "uid", "account", "order", "product", "item"}]
        potential_xss = [p for p in unique_params if p in {"q", "query", "search", "callback", "return", "next"}]
        potential_ssrf = [p for p in unique_params if p in {"url", "uri", "path", "dest", "redirect", "load", "fetch", "include"}]

        return {
            "next_agents": ["arjun", "dalfox", "sqlmap", "ssrfmap", "gf"],
            "param_list": unique_params,
            "potential_sqli": potential_sqli,
            "potential_xss": potential_xss,
            "potential_ssrf": potential_ssrf,
            "operator_summary": (
                f"Paramspider found {len(signal)} parameterized URLs for {target} with "
                f"{len(unique_params)} unique parameter names."
            ),
        }
