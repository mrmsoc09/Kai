from __future__ import annotations

import base64
import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from xml.sax.saxutils import escape as xml_escape

from ..base_tool_agent import BaseToolAgent


class NucleiExportAgent(BaseToolAgent):
    """
    Converts finalized Nuclei KaisonResult payloads into Burp XML history artifacts.
    """

    TOOL_NAME = "nuclei_export"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        # This tool is a transformer, it doesn't run a CLI binary in the traditional sense.
        # But we implement the method to satisfy the base class.
        return ["echo", "nuclei_export_running"]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        # This tool usually takes a full KaisonResult as input via execute().
        # If called via standard parse_output, it assumes raw_output is the JSON result.
        findings: list[dict[str, Any]] = []
        try:
            data = json.loads(raw_output)
            findings.append({
                "type": "artifact",
                "value": target,
                "target": target,
                "severity": "info",
                "confidence": 1.0,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": raw_output[:1000],
                "context": {"kind": "burp_xml_export"},
                "recommended_next_tools": [],
                "recommended_next_actions": ["download_artifact"],
            })
        except json.JSONDecodeError:
            pass
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return findings, []

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        return {"action": "export_complete", "target": target}
