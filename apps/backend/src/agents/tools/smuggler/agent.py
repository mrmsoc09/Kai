from __future__ import annotations

from typing import Any

from ..base_tool_agent import BaseToolAgent


class SmugglerAgent(BaseToolAgent):
    TOOL_NAME = "smuggler"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        return [
            "smuggler",
            "-u",
            target,
            "-q",
            "--timeout",
            "30",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_output = raw_output.strip()
        if not raw_output:
            return findings

        detected_variants = set()
        for line in raw_output.splitlines():
            line = line.lower()
            if "te.cl" in line:
                detected_variants.add("TE.CL")
            elif "cl.te" in line:
                detected_variants.add("CL.TE")

        for variant in detected_variants:
            findings.append(
                {
                    "type": "request_smuggling_candidate",
                    "value": f"HTTP Request Smuggling - {variant} variant",
                    "target": target,
                    "severity": "high",
                    "confidence": 0.7,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": raw_output[:500],
                    "context": {
                        "variant": variant,
                        "requires_manual_verification": True,
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["manual_verification", "exploit_validation"],
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
            key = f"{finding['target'].lower()}|smuggling|{finding['value'].lower()}"
            if key in known:
                noise.append(finding)
                continue

            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "smuggling_variants": len(signal),
            "operator_summary": (
                f"Smuggler detected {len(signal)} potential HTTP request smuggling variants on {target}. "
                "Manual verification required. Do NOT exploit without authorization confirmation."
            ),
        }
