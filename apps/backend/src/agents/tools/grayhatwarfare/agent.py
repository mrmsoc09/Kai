from __future__ import annotations

import json
import os
from typing import Any

from ..base_tool_agent import BaseToolAgent


class GrayHatWarfareAgent(BaseToolAgent):
    """Gray Hat Warfare exposed cloud storage agent."""

    TOOL_NAME = "grayhatwarfare"

    def build_command(
        self, target: str, options: dict[str, Any] | None = None
    ) -> list[str]:
        api_key = os.environ.get("GRAYHATWARFARE_API_KEY", "")
        return [
            "python3",
            "-c",
            f"""
import requests, json
headers = {{'Authorization': f'Bearer {api_key}'}}
try:
    r = requests.get(
        'https://buckets.grayhatwarfare.com/api/v2/buckets',
        params={{'keywords': '{target}', 'limit': 100}},
        headers=headers,
        timeout=30
    )
    print(json.dumps(r.json() if r.ok else {{}}, default=str))
except Exception as e:
    print(json.dumps({{}}, default=str))
""",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        try:
            data = json.loads(raw_output.strip())
        except (json.JSONDecodeError, TypeError):
            return findings

        if not isinstance(data, dict):
            return findings

        buckets = data.get("buckets", [])
        if not isinstance(buckets, list):
            return findings

        for bucket in buckets:
            if not isinstance(bucket, dict):
                continue

            findings.append(
                {
                    "type": "exposed_cloud_storage",
                    "value": bucket.get("bucket", ""),
                    "target": target,
                    "severity": "high",
                    "confidence": 0.85,
                    "source_tool": "grayhatwarfare",
                    "raw_evidence": str(bucket)[:500],
                    "context": {
                        "provider": bucket.get("provider", ""),
                        "file_count": bucket.get("fileCount", 0),
                        "keywords": bucket.get("keywords", []),
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": [
                        "verify_bucket_access",
                        "inventory_exposed_files",
                    ],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]], target: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal = []
        noise = []

        for f in findings:
            if f["context"].get("file_count", 0) > 0:
                signal.append(f)
            else:
                noise.append(f)

        return signal, noise

    def _generate_next_agent_instructions(
        self, result: dict[str, Any], target: str
    ) -> dict[str, Any]:
        finding_count = len(result.get("findings", []))
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "operator_summary": (
                f"GrayHatWarfare found {finding_count} exposed cloud buckets "
                f"related to {target}. Verify access before reporting."
            ),
        }
