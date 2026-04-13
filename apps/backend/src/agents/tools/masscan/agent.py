from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Callable

from apps.backend.src.core.protocol import KaisonResult, KaisonResultMetadata
from apps.backend.src.core.scope_guardrails import (
    audit_scope_decision,
    evaluate_target_scope,
    load_scope_policy,
)

from ..base_tool_agent import BaseToolAgent
from ..network_fingerprint_schemas import PortServiceRegistry


_HIGH_VALUE_PORTS = {9200, 6379, 5601, 9090}
_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}


class MasscanAgent(BaseToolAgent):
    TOOL_NAME = "masscan"

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

    @staticmethod
    def _resolve_targets(target: str, options: dict[str, Any]) -> list[str]:
        discovery_buffer = options.get("discovery_buffer")
        if isinstance(discovery_buffer, list):
            resolved = [str(item).strip() for item in discovery_buffer if str(item).strip()]
            if resolved:
                return resolved
        return [target]

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        output_file = opts.get("output_file", f"{opts.get('artifact_dir', '/tmp')}/masscan_output.json")
        rate = int(opts.get("rate", 1000))
        rate = rate if rate > 0 else 1000
        snl_interface = str(opts.get("snl_interface", "tun0")).strip()

        targets = self._resolve_targets(target, opts)
        cmd = [
            "masscan",
            *targets,
            "-p",
            str(opts.get("ports", "1-1000")),
            "--rate",
            str(rate),
            "--adapter",
            snl_interface,
            "--output-format",
            "json",
            "--output-filename",
            str(output_file),
        ]
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_output = raw_output.strip()
        if not raw_output:
            return findings

        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError:
            payload = []

        if not isinstance(payload, list):
            return findings

        for host_result in payload:
            if not isinstance(host_result, dict):
                continue
            ip = str(host_result.get("ip", target)).strip() or target
            ports = host_result.get("ports", [])
            if not isinstance(ports, list):
                continue
            for item in ports:
                if not isinstance(item, dict):
                    continue
                port_value = item.get("port")
                if not isinstance(port_value, int):
                    continue

                try:
                    record = PortServiceRegistry.model_validate(
                        {
                            "target_ip": ip,
                            "port_number": port_value,
                            "proto_type": item.get("proto", "tcp"),
                            "timestamp": datetime.now(UTC),
                        }
                    )
                except Exception:
                    continue

                severity = "high" if record.port_number in _HIGH_VALUE_PORTS else "medium"
                findings.append(
                    {
                        "type": "open_port",
                        "value": f"{record.target_ip}:{record.port_number}",
                        "target": target,
                        "severity": severity,
                        "confidence": 0.9 if record.port_number in _HIGH_VALUE_PORTS else 0.8,
                        "source_tool": self.TOOL_NAME,
                        "raw_evidence": json.dumps(item, ensure_ascii=True),
                        "context": {
                            "ip": record.target_ip,
                            "port": record.port_number,
                            "protocol": record.proto_type,
                            "service_registry": record.model_dump(mode="json"),
                            "snl_mode": "fixture_only",
                        },
                        "recommended_next_tools": ["nmap", "wafw00f"],
                        "recommended_next_actions": ["run_targeted_service_detection"],
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

            port = int(finding.get("context", {}).get("port", 0) or 0)
            if port in {80, 443}:
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
        ports = sorted(
            {
                int(item.get("context", {}).get("port", 0) or 0)
                for item in signal
                if item.get("context", {}).get("port")
            }
        )
        return {
            "next_agents": ["nmap", "wafw00f"],
            "ports": [p for p in ports if p > 0],
            "operator_summary": (
                f"Masscan fixture parsing identified {len(signal)} prioritized open ports for {target}. "
                "Port Scan Arcs telemetry emitted for topology visibility."
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
        ended_at = datetime.now(UTC)
        runtime_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))
        result = self.map_output(
            target=target,
            command=["fixture://masscan"],
            stdout=fixture_text,
            stderr="",
            exit_code=0,
            started_at=started_at,
            ended_at=ended_at,
            runtime_ms=runtime_ms,
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
