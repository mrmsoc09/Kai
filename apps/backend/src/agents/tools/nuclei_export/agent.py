from __future__ import annotations

import base64
import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from xml.sax.saxutils import escape as xml_escape

from apps.backend.src.core.protocol import (
    FindingType,
    KaisonFinding,
    KaisonResult,
    KaisonResultMetadata,
    Severity,
)


class NucleiExportAgent:
    """
    Converts finalized Nuclei KaisonResult payloads into Burp XML history artifacts.
    """

    TOOL_NAME = "nuclei_export"

    def run(
        self,
        target: str,
        raw_output: str,
        options: dict[str, Any] | None = None,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        started_at = datetime.now(UTC)
        opts = options or {}

        output_dir = Path(str(opts.get("output_dir", "output/burp_exports")))
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        output_name = str(opts.get("output_name", f"{mission_id}_{timestamp}.burp"))
        output_path = output_dir / output_name

        findings: list[KaisonFinding]
        status = "failure"
        export_count = 0
        telemetry: dict[str, Any] = {}

        try:
            parsed_result = self._parse_input_result(raw_output)
            confirmed = self._extract_confirmed_vulns(parsed_result)
            export_count = len(confirmed)

            xml_text = self._build_burp_xml(confirmed)
            output_path.write_text(xml_text, encoding="utf-8")

            status = "success" if confirmed else "partial"
            findings = [
                KaisonFinding(
                    finding_type=FindingType.CONFIG,
                    value=str(output_path),
                    source_agent=self.TOOL_NAME,
                    confidence=1.0,
                    severity=Severity.INFO,
                    raw_evidence={
                        "kind": "artifact",
                        "artifact_type": "burp_xml",
                        "path": str(output_path),
                        "confirmed_findings": len(confirmed),
                        "input_source_agent": parsed_result.source_agent,
                    },
                )
            ]
        except Exception as exc:
            telemetry = {
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "output_path": str(output_path),
            }
            findings = [
                KaisonFinding(
                    finding_type=FindingType.CONFIG,
                    value="nuclei_export:telemetry:failure",
                    source_agent=self.TOOL_NAME,
                    confidence=1.0,
                    severity=Severity.INFO,
                    raw_evidence={"kind": "telemetry", **telemetry},
                )
            ]

        ended_at = datetime.now(UTC)
        runtime_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))

        return KaisonResult(
            mission_id=mission_id,
            source_agent=self.TOOL_NAME,
            status=status,
            target_context={
                "target": target,
                "output_path": str(output_path),
                "exported_items": export_count,
                "telemetry": telemetry,
            },
            metadata=KaisonResultMetadata(
                started_at=started_at,
                ended_at=ended_at,
                runtime_ms=runtime_ms,
            ),
            findings=findings,
        )

    def _parse_input_result(self, raw_output: str) -> KaisonResult:
        text = raw_output.strip()
        if not text:
            raise ValueError("raw_output is empty")

        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("raw_output must contain a JSON object")
        return KaisonResult.model_validate(payload)

    def _extract_confirmed_vulns(self, result_obj: KaisonResult) -> list[dict[str, Any]]:
        confirmed: list[dict[str, Any]] = []

        for finding in result_obj.findings:
            if finding.finding_type != FindingType.VULN:
                continue

            evidence = dict(finding.raw_evidence)
            if not self._is_confirmed(finding, evidence):
                continue

            request_text = self._coalesce_http(evidence, "request", "raw_request", "http_request")
            response_text = self._coalesce_http(evidence, "response", "raw_response", "http_response")
            matched_at = self._coalesce_text(
                finding.value,
                evidence.get("matched_at"),
                evidence.get("url"),
            )

            confirmed.append(
                {
                    "name": str(evidence.get("vuln_name") or evidence.get("template_id") or "Nuclei Finding"),
                    "severity": finding.severity.value,
                    "url": matched_at,
                    "request": request_text,
                    "response": response_text,
                    "metadata": evidence,
                }
            )

        return confirmed

    def _build_burp_xml(self, confirmed_findings: list[dict[str, Any]]) -> str:
        root = ET.Element(
            "items",
            {
                "burpVersion": "2026.1",
                "exportTime": datetime.now(UTC).isoformat(),
            },
        )

        for entry in confirmed_findings:
            item = ET.SubElement(root, "item")
            parsed = urlsplit(str(entry.get("url") or ""))
            host = parsed.hostname or ""
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"

            ET.SubElement(item, "time").text = datetime.now(UTC).strftime("%a %b %d %H:%M:%S UTC %Y")
            ET.SubElement(item, "url").text = self._xml_safe_text(str(entry.get("url") or ""))
            ET.SubElement(item, "host", {"ip": ""}).text = self._xml_safe_text(host)
            ET.SubElement(item, "port").text = str(port)
            ET.SubElement(item, "protocol").text = self._xml_safe_text(parsed.scheme or "https")
            ET.SubElement(item, "method").text = self._xml_safe_text(
                self._extract_method(str(entry.get("request") or ""))
            )
            ET.SubElement(item, "path").text = self._xml_safe_text(path)
            ET.SubElement(item, "extension").text = self._xml_safe_text(self._extract_extension(parsed.path or ""))

            request_raw = str(entry.get("request") or "GET / HTTP/1.1\r\nHost: example.com\r\n\r\n")
            response_raw = str(entry.get("response") or "HTTP/1.1 200 OK\r\n\r\n")

            ET.SubElement(item, "request", {"base64": "true"}).text = base64.b64encode(
                request_raw.encode("utf-8", errors="replace")
            ).decode("ascii")
            ET.SubElement(item, "response", {"base64": "true"}).text = base64.b64encode(
                response_raw.encode("utf-8", errors="replace")
            ).decode("ascii")

            ET.SubElement(item, "status").text = self._extract_status_code(response_raw)
            ET.SubElement(item, "responselength").text = str(len(response_raw.encode("utf-8", errors="replace")))
            ET.SubElement(item, "mimetype").text = ""
            ET.SubElement(item, "comment").text = self._xml_safe_text(
                f"nuclei_export|severity={entry.get('severity')}|name={entry.get('name')}"
            )

        xml_bytes = ET.tostring(root, encoding="utf-8")
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes.decode("utf-8")

    @staticmethod
    def _is_confirmed(finding: KaisonFinding, evidence: dict[str, Any]) -> bool:
        if bool(evidence.get("confirmed")):
            return True

        status = str(evidence.get("validation_status", evidence.get("status", ""))).lower()
        if status in {"confirmed", "verified", "valid", "true_positive"}:
            return True

        confidence = evidence.get("confidence", finding.confidence)
        try:
            return float(confidence) >= 0.9
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _coalesce_http(metadata: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, dict):
                nested = value.get("raw") or value.get("text")
                if isinstance(nested, str) and nested.strip():
                    return nested
        return ""

    @staticmethod
    def _coalesce_text(*values: Any) -> str:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value
        return ""

    @staticmethod
    def _extract_method(request_text: str) -> str:
        first_line = request_text.splitlines()[0].strip() if request_text else ""
        token = first_line.split(" ", 1)[0].upper() if first_line else "GET"
        if not token.isalpha():
            return "GET"
        return token[:16]

    @staticmethod
    def _extract_status_code(response_text: str) -> str:
        if not response_text:
            return "0"
        first_line = response_text.splitlines()[0]
        parts = first_line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            return parts[1]
        return "0"

    @staticmethod
    def _extract_extension(path: str) -> str:
        filename = (path or "").rsplit("/", 1)[-1]
        if "." not in filename:
            return ""
        return filename.rsplit(".", 1)[-1][:32]

    @staticmethod
    def _xml_safe_text(value: str) -> str:
        filtered = []
        for ch in value:
            code = ord(ch)
            if code in {0x9, 0xA, 0xD} or 0x20 <= code <= 0xD7FF or 0xE000 <= code <= 0xFFFD:
                filtered.append(ch)
        return xml_escape("".join(filtered), {'"': "&quot;", "'": "&apos;"})
