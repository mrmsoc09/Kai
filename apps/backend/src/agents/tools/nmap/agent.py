from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from typing import Any, Callable

from apps.backend.src.core.protocol import KaisonResult, KaisonResultMetadata
from apps.backend.src.core.scope_guardrails import (
    audit_scope_decision,
    evaluate_target_scope,
    load_scope_policy,
)

from ..base_tool_agent import BaseToolAgent
from ..network_fingerprint_schemas import PortServiceRegistry


_HIGH_VALUE_PORTS = {
    "9200": "Elasticsearch",
    "6379": "Redis",
    "5601": "Kibana",
    "27017": "MongoDB",
    "9090": "Prometheus",
}
_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}


class NmapAgent(BaseToolAgent):
    TOOL_NAME = "nmap"

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._telemetry_events: list[dict[str, Any]] = []
        self._telemetry_hook: Callable[[dict[str, Any]], None] | None = None

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def register_telemetry_hook(self, hook: Callable[[dict[str, Any]], None]) -> None:
        self._telemetry_hook = hook

    def get_telemetry_events(self) -> list[dict[str, Any]]:
        return list(self._telemetry_events)

    def _emit_telemetry(self, metric: str, value: Any) -> None:
        event = {
            "tool": self.TOOL_NAME,
            "metric": metric,
            "value": value,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._telemetry_events.append(event)
        if self._telemetry_hook:
            try:
                self._telemetry_hook(event)
            except Exception:
                return

    def check_policy(self, target: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        opts = options or {}
        scope_label = str(opts.get("research_scope", _APPROVED_SCOPE_LABEL)).strip()
        policy = load_scope_policy(opts.get("scope_policy_path"))
        decision = evaluate_target_scope(target, policy, safe_mode=True)
        audit_scope_decision(decision)

        snl_interface = str(opts.get("snl_interface", "tun0")).strip()
        snl_ok = snl_interface in _ALLOWED_SNL_INTERFACES

        allowed = decision.allowed and scope_label == _APPROVED_SCOPE_LABEL and snl_ok
        reason = decision.reason
        if scope_label != _APPROVED_SCOPE_LABEL:
            reason = "missing_approved_research_scope"
        elif not snl_ok:
            reason = f"snl_interface_not_allowed:{snl_interface}"

        return {
            "allowed": allowed,
            "reason": reason,
            "target": decision.normalized_host,
            "matched_rule": decision.matched_rule,
            "snl_interface": snl_interface,
        }

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        output_file = opts.get("output_file", f"{opts.get('artifact_dir', '/tmp')}/nmap_output.xml")
        stealth = bool(opts.get("K1_STEALTH", False))
        timing = "-T2" if stealth else str(opts.get("timing", "-T4"))
        snl_interface = str(opts.get("snl_interface", "tun0")).strip()

        cmd = [
            "nmap",
            "-sV",
            "-sC",
            timing,
            "--open",
            "-oX",
            str(output_file),
            "--host-timeout",
            str(opts.get("host_timeout", "60s")),
            "--script-timeout",
            str(opts.get("script_timeout", "30s")),
            "-e",
            snl_interface,
        ]

        open_ports_file = opts.get("open_ports_file")
        if isinstance(open_ports_file, str) and open_ports_file.strip():
            cmd.extend(["-iL", open_ports_file.strip()])
        else:
            cmd.append(target)
        return cmd

    @staticmethod
    def _extract_host_ip(host: ET.Element, fallback: str) -> str:
        for address in host.findall("address"):
            addr = str(address.attrib.get("addr", "")).strip()
            if addr:
                return addr
        return fallback

    def _parse_xml_records(self, xml_text: str, target: str) -> list[PortServiceRegistry]:
        records: list[PortServiceRegistry] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return records

        for host in root.findall("host"):
            host_ip = self._extract_host_ip(host, fallback=target)
            for port in host.findall("ports/port"):
                state = port.find("state")
                if state is None or state.attrib.get("state") != "open":
                    continue

                port_id = int(port.attrib.get("portid", "0") or 0)
                if port_id <= 0:
                    continue

                service = port.find("service")
                service_name = service.attrib.get("name") if service is not None else None
                product = service.attrib.get("product") if service is not None else None
                version = service.attrib.get("version") if service is not None else None

                try:
                    records.append(
                        PortServiceRegistry.model_validate(
                            {
                                "target_ip": host_ip,
                                "port_number": port_id,
                                "proto_type": port.attrib.get("protocol", "tcp"),
                                "service_name": service_name,
                                "product": product,
                                "version": version,
                                "timestamp": datetime.now(UTC),
                            }
                        )
                    )
                except Exception:
                    continue

        return records

    def _parse_plain_records(self, raw_output: str, target: str) -> list[PortServiceRegistry]:
        records: list[PortServiceRegistry] = []
        pattern = re.compile(r"(\d+)/(tcp|udp)\s+open\s+(\S+)\s*(.*)")
        for line in raw_output.splitlines():
            match = pattern.search(line)
            if not match:
                continue
            try:
                records.append(
                    PortServiceRegistry.model_validate(
                        {
                            "target_ip": target,
                            "port_number": int(match.group(1)),
                            "proto_type": match.group(2),
                            "service_name": match.group(3),
                            "version": match.group(4).strip() or None,
                            "timestamp": datetime.now(UTC),
                        }
                    )
                )
            except Exception:
                continue
        return records

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        records = self._parse_xml_records(raw_output, target=target)
        parser_mode = "xml"
        if not records:
            records = self._parse_plain_records(raw_output, target=target)
            parser_mode = "plain"

        findings: list[dict[str, Any]] = []
        for record in records:
            port = str(record.port_number)
            severity = "info"
            confidence = 0.7
            if port in _HIGH_VALUE_PORTS:
                severity = "high"
                confidence = 0.9
            elif port not in {"80", "443"}:
                severity = "medium"
                confidence = 0.8

            service_descriptor = record.service_name or "unknown"
            if record.product:
                service_descriptor = f"{service_descriptor}:{record.product}"
            if record.version:
                service_descriptor = f"{service_descriptor}:{record.version}"

            findings.append(
                {
                    "type": "open_port",
                    "value": f"{record.target_ip}:{record.port_number}",
                    "target": target,
                    "severity": severity,
                    "confidence": confidence,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": service_descriptor,
                    "context": {
                        "port": str(record.port_number),
                        "service": record.service_name or "unknown",
                        "version": record.version or "",
                        "service_registry": record.model_dump(mode="json"),
                        "parser_mode": parser_mode,
                        "snl_mode": "fixture_only",
                    },
                    "recommended_next_tools": ["wafw00f", "whatweb"],
                    "recommended_next_actions": ["fingerprint_http_stack", "prioritize_exposed_services"],
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
            value = str(finding.get("value", ""))
            if f"{finding.get('target', '').lower()}|open_port|{value}" in known:
                noise.append(finding)
                continue

            port = str(finding.get("context", {}).get("port", ""))
            if port in {"80", "443"}:
                finding["confidence"] = 0.5
                noise.append(finding)
            else:
                signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        high_value = [
            item for item in signal if str(item.get("severity", "")).lower() in {"medium", "high", "critical"}
        ]
        versions = [
            str(item.get("context", {}).get("version", "")).strip()
            for item in high_value
            if str(item.get("context", {}).get("version", "")).strip()
        ]
        return {
            "next_agents": ["wafw00f", "whatweb"],
            "version_strings": versions,
            "high_value_ports": [f["value"] for f in high_value],
            "operator_summary": (
                f"Nmap fixture parsing identified {len(signal)} prioritized services on {target}. "
                f"Forwarding {len(versions)} version strings for stack correlation."
            ),
        }

    def execute(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        opts = dict(options or {})
        policy = self.check_policy(target, opts)

        started_at = datetime.now(UTC)
        if not policy["allowed"]:
            ended_at = datetime.now(UTC)
            return KaisonResult(
                mission_id=mission_id,
                source_agent=self.TOOL_NAME,
                status="failure",
                target_context={
                    "target": target,
                    "mode": "stub_only",
                    "error": f"policy_blocked:{policy['reason']}",
                },
                metadata=KaisonResultMetadata(
                    started_at=started_at,
                    ended_at=ended_at,
                    runtime_ms=max(0, int((ended_at - started_at).total_seconds() * 1000)),
                ),
                findings=[],
            )

        fixture = opts.get("fixture_data")
        if fixture is None and isinstance(opts.get("fixture_path"), str):
            fixture = Path(opts["fixture_path"]).read_text(encoding="utf-8")

        if fixture is None:
            # Prefer Docker live execution when the kai-nmap image is available.
            if self.docker_image_available():
                return super().execute(target, options, mission_id=mission_id)
            ended_at = datetime.now(UTC)
            return KaisonResult(
                mission_id=mission_id,
                source_agent=self.TOOL_NAME,
                status="failure",
                target_context={
                    "target": target,
                    "mode": "stub_only",
                    "error": "fixture_data is required; live execution disabled",
                },
                metadata=KaisonResultMetadata(
                    started_at=started_at,
                    ended_at=ended_at,
                    runtime_ms=max(0, int((ended_at - started_at).total_seconds() * 1000)),
                ),
                findings=[],
            )

        fixture_text = fixture if isinstance(fixture, str) else json.dumps(fixture)
        result = self.map_output(
            target=target,
            command=["fixture://nmap"],
            stdout=fixture_text,
            stderr="",
            exit_code=0,
            started_at=started_at,
            ended_at=datetime.now(UTC),
            runtime_ms=max(0, int((datetime.now(UTC) - started_at).total_seconds() * 1000)),
            mission_id=mission_id,
            status="success",
            options=opts,
        )

        self._emit_telemetry("AGENT_STATUS", "SCAN_REVIEW")
        self._emit_telemetry("OPEN_PORTS_DISCOVERED", len(result.findings))
        if result.findings:
            self._emit_telemetry("EventLog", "PORT_SCAN_ARCS")

        context = dict(result.target_context)
        context.update(
            {
                "mode": "stub_fixture",
                "snl_interface": policy["snl_interface"],
                "telemetry": self.get_telemetry_events(),
            }
        )
        return result.model_copy(update={"target_context": context})
