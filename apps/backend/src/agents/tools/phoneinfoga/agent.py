from __future__ import annotations

import json
import re
from typing import Any

from ..base_tool_agent import BaseToolAgent


class PhoneinfogaAgent(BaseToolAgent):
    TOOL_NAME = "phoneinfoga"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        phone_number = str(opts.get("phone_number", target))
        # phoneinfoga has no --timeout flag
        # timeout enforced by subprocess wrapper via ctx.timeout in execute() method
        return ["phoneinfoga", "scan", "-n", phone_number]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_output = raw_output.strip()
        if not raw_output:
            return findings

        payload: dict[str, Any] = {}
        try:
            parsed = json.loads(raw_output)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            # Fallback: parse simple "key: value" style output.
            payload = {}
            linked_accounts: list[str] = []
            for line in raw_output.splitlines():
                text = line.strip()
                if not text:
                    continue
                lowered = text.lower()
                if ":" in text:
                    key, value = text.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    if key in {"carrier", "operator"} and value:
                        payload["carrier"] = value
                    elif key in {"country", "location"} and value:
                        payload["country"] = value
                linked_accounts.extend(re.findall(r"@([A-Za-z0-9_.-]{2,50})", text))
            if linked_accounts:
                payload["linked_accounts"] = sorted(set(linked_accounts))

        country = str(payload.get("country") or payload.get("location") or "")
        carrier = str(payload.get("carrier") or payload.get("operator") or "")
        linked = payload.get("linked_accounts") or payload.get("accounts") or []
        if not isinstance(linked, list):
            linked = []

        value = str(payload.get("number") or target)
        findings.append(
            {
                "type": "osint_finding",
                "value": value,
                "target": target,
                "severity": "medium" if linked else "info",
                "confidence": 0.8 if linked else 0.65,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": raw_output[:1000],
                "context": {
                    "kind": "phone_intel",
                    "carrier": carrier,
                    "country": country,
                    "linked_accounts": linked,
                },
                "recommended_next_tools": ["sherlock"],
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
            if f"{finding['target'].lower()}|osint|{value}" in known:
                noise.append(finding)
                continue

            if not value or "invalid" in value.lower():
                noise.append(finding)
            else:
                signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        linked_usernames: list[str] = []
        for finding in signal:
            for acct in finding.get("context", {}).get("linked_accounts", []):
                if isinstance(acct, str) and acct.strip():
                    linked_usernames.append(acct.strip())
                elif isinstance(acct, dict):
                    username = str(acct.get("username", "")).strip()
                    if username:
                        linked_usernames.append(username)

        return {
            "next_agents": ["sherlock"],
            "linked_usernames": sorted(set(linked_usernames)),
            "operator_summary": (
                f"Phoneinfoga processed {len(signal)} phone intelligence records for {target}. "
                f"Linked usernames extracted: {len(set(linked_usernames))}."
            ),
        }
