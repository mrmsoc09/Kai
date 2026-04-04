from __future__ import annotations

from typing import Any

from ..base_tool_agent import BaseToolAgent


_HIGH_VALUE_PLATFORMS = {"github", "linkedin", "hackerone"}


class SherlockAgent(BaseToolAgent):
    TOOL_NAME = "sherlock"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        username = str(opts.get("username", target.split(".")[0]))
        output_path = f"{artifact_dir}/sherlock.txt"
        return [
            "sherlock",
            username,
            "--output",
            output_path,
            "--print-found",
            "--timeout",
            "60",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.strip().splitlines():
            text = line.strip()
            if not text or "http" not in text:
                continue
            if "not found" in text.lower():
                continue

            platform = "unknown"
            lowered = text.lower()
            for candidate in ["github", "linkedin", "hackerone", "twitter", "reddit", "gitlab"]:
                if candidate in lowered:
                    platform = candidate
                    break

            url = text.split()[-1]
            high = platform in _HIGH_VALUE_PLATFORMS
            findings.append(
                {
                    "type": "osint_finding",
                    "value": url,
                    "target": target,
                    "severity": "medium" if high else "info",
                    "confidence": 0.85 if high else 0.7,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": text[:1000],
                    "context": {
                        "kind": "social_profile",
                        "platform": platform,
                    },
                    "recommended_next_tools": ["trufflehog", "github-subdomains"] if platform == "github" else ["social-analyzer"],
                    "recommended_next_actions": ["profile_enrichment"],
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

            if "not found" in str(finding.get("raw_evidence", "")).lower():
                noise.append(finding)
            else:
                signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        github_profiles = [f["value"] for f in signal if str(f.get("context", {}).get("platform", "")) == "github"]
        return {
            "next_agents": ["trufflehog", "github-subdomains"],
            "github_profiles": github_profiles,
            "operator_summary": (
                f"Sherlock discovered {len(signal)} social profiles for {target}. "
                f"GitHub profiles for repo intelligence: {len(github_profiles)}."
            ),
        }
