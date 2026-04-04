from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class SocialAnalyzerAgent(BaseToolAgent):
    TOOL_NAME = "social-analyzer"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        username = str(opts.get("username", target.split(".")[0]))
        output_path = f"{artifact_dir}/social.json"
        return [
            "social-analyzer",
            "--username",
            username,
            "--metadata",
            "--output",
            output_path,
            "--timeout",
            "60",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_output = raw_output.strip()
        if not raw_output:
            return findings

        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError:
            payload = []

        profiles: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            data = payload.get("profiles")
            if isinstance(data, list):
                profiles = [p for p in data if isinstance(p, dict)]
        elif isinstance(payload, list):
            profiles = [p for p in payload if isinstance(p, dict)]

        for profile in profiles:
            platform = str(profile.get("platform", "unknown"))
            url = str(profile.get("url", "")).strip()
            if not url:
                continue
            follower_count = int(profile.get("followers", 0) or 0)
            bio = str(profile.get("bio", ""))
            links = profile.get("links", [])
            if not isinstance(links, list):
                links = []

            active = follower_count > 0 or bool(bio.strip()) or len(links) > 0
            findings.append(
                {
                    "type": "osint_finding",
                    "value": url,
                    "target": target,
                    "severity": "medium" if active else "info",
                    "confidence": 0.84 if active else 0.65,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(profile, ensure_ascii=True)[:1000],
                    "context": {
                        "kind": "social_profile_detail",
                        "platform": platform,
                        "follower_count": follower_count,
                        "bio": bio[:300],
                        "links": links,
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["profile_intelligence_enrichment"],
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

            followers = int(finding.get("context", {}).get("follower_count", 0) or 0)
            bio = str(finding.get("context", {}).get("bio", "")).strip()
            links = finding.get("context", {}).get("links", [])
            if followers == 0 and not bio and not links:
                noise.append(finding)
            else:
                signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        platforms = sorted({str(f.get("context", {}).get("platform", "unknown")) for f in signal})
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "profiles_found": len(signal),
            "platforms": platforms,
            "operator_summary": (
                f"Social-Analyzer produced {len(signal)} enriched profile records for {target} "
                f"across {len(platforms)} platforms."
            ),
        }
