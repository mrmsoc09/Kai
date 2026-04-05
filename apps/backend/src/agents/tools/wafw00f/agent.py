from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


_PHASE7_AGENTS = [
    "nuclei_scan",
    "nikto",
    "testssl",
    "dalfox",
    "sqlmap",
    "ssrfmap",
    "corsy",
    "crlfuzz",
    "smuggler",
    "searchsploit",
]


class Wafw00fAgent(BaseToolAgent):
    TOOL_NAME = "wafw00f"
    def _get_tool_name(self) -> str:
        return self.TOOL_NAME


    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        output_file = opts.get("output_file", f"{opts.get('artifact_dir', '/tmp')}/wafw00f.json")
        # wafw00f doesn't have a direct timeout flag. 
        # BaseToolAgent's subprocess.communicate(timeout=...) handles it.
        return ["wafw00f", target, "-o", str(output_file), "-f", "json"]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        raw_output = raw_output.strip()
        if not raw_output:
            return []

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            data = {}

        payloads = data if isinstance(data, list) else [data]
        findings: list[dict[str, Any]] = []
        for item in payloads:
            if not isinstance(item, dict):
                continue
            waf_name = str(item.get("waf_name") or item.get("firewall") or item.get("manufacturer") or "none")
            detected = bool(item.get("detected") or item.get("waf_detected") or waf_name.lower() != "none")
            confidence = float(item.get("confidence", 0.9 if detected else 0.7))
            findings.append(
                {
                    "type": "waf_fingerprint",
                    "value": waf_name,
                    "target": target,
                    "severity": "medium" if detected else "info",
                    "confidence": max(0.0, min(1.0, confidence)),
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(item, ensure_ascii=True),
                    "context": {
                        "waf_detected": detected,
                        "waf_name": waf_name,
                        "confidence": max(0.0, min(1.0, confidence)),
                    },
                    "recommended_next_tools": _PHASE7_AGENTS,
                    "recommended_next_actions": ["apply_waf_adaptive_rate_limit"],
                }
            )
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        known = self.load_memory()
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        for finding in findings:
            if f"{finding.get('target', '').lower()}|waf_fingerprint|{finding.get('value', '')}" in known:
                noise.append(finding)
                continue
            signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        detected = any(bool(item.get("context", {}).get("waf_detected")) for item in signal)
        waf_name = "none"
        for item in signal:
            if item.get("context", {}).get("waf_detected"):
                waf_name = str(item.get("context", {}).get("waf_name", "unknown"))
                break

        rate_limit = 2 if detected else 10
        note = (
            f"WAF detected ({waf_name}). Reduce aggressiveness, avoid signature payload bursts, and apply evasion."
            if detected
            else "No WAF detected. Full baseline aggressiveness permitted."
        )
        configuration_hints = {agent: {"rate_limit": rate_limit, "note": note} for agent in _PHASE7_AGENTS}

        return {
            "next_agents": _PHASE7_AGENTS,
            "configuration_hints": configuration_hints,
            "operator_summary": (
                f"WAF status for {target}: {'DETECTED' if detected else 'NOT DETECTED'}"
                f" ({waf_name}). All downstream active scanners configured to {rate_limit} req/sec profile."
            ),
        }
