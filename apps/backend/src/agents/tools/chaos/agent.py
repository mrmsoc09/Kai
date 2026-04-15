from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from apps.backend.src.core.protocol import KaisonResult, KaisonResultMetadata
from apps.backend.src.core.scope_guardrails import (
    audit_scope_decision,
    evaluate_target_scope,
    load_scope_policy,
)

from ..base_tool_agent import BaseToolAgent
from ..osint_schemas import DiscoveryRegistry


_HIGH_VALUE_KEYWORDS = {"admin", "api", "dev", "staging", "internal", "backend"}
_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}


class ChaosAgent(BaseToolAgent):
    """Fixture-driven architectural stub for passive Chaos ingestion."""

    TOOL_NAME = "chaos"

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._lifecycle_status = "IDLE"
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
        _ = options or {}
        return ["chaos", "-d", target, "-silent", "-json"]

    def ingest_fixture(
        self,
        fixture: str | dict[str, Any] | list[Any],
        *,
        target: str,
        options: dict[str, Any] | None = None,
    ) -> list[DiscoveryRegistry]:
        policy = self.check_policy(target, options)
        if not policy["allowed"]:
            raise PermissionError(f"target blocked by scope policy: {policy['reason']}")

        records: list[DiscoveryRegistry] = []
        for domain in self._extract_domains(fixture):
            try:
                records.append(
                    DiscoveryRegistry.model_validate(
                        {
                            "discovered_domain": domain,
                            "intel_source": "chaos_dataset",
                            "timestamp": datetime.now(UTC),
                        }
                    )
                )
            except Exception:
                continue

        self._emit_telemetry("AGENT_STATUS", "PASSIVE_ENUMERATION")
        self._emit_telemetry("PASSIVE_ASSETS_FOUND", len(records))
        if records:
            self._emit_telemetry("EventLog", "CLOUD_BURST")
        return records

    def _extract_domains(self, fixture: str | dict[str, Any] | list[Any]) -> list[str]:
        values: list[str] = []

        def _add_candidate(candidate: Any) -> None:
            token = str(candidate or "").strip().lower()
            if token:
                values.append(token)

        if isinstance(fixture, dict):
            if isinstance(fixture.get("domain"), str):
                _add_candidate(fixture["domain"])
            if isinstance(fixture.get("subdomain"), str):
                _add_candidate(fixture["subdomain"])
            domains = fixture.get("domains")
            if isinstance(domains, list):
                for item in domains:
                    _add_candidate(item)
            return values

        if isinstance(fixture, list):
            for item in fixture:
                if isinstance(item, dict):
                    _add_candidate(item.get("domain") or item.get("subdomain"))
                else:
                    _add_candidate(item)
            return values

        for line in str(fixture).splitlines():
            token = line.strip()
            if not token:
                continue
            if token.startswith("{"):
                try:
                    payload = json.loads(token)
                except json.JSONDecodeError:
                    payload = None
                if isinstance(payload, dict):
                    _add_candidate(payload.get("domain") or payload.get("subdomain") or payload.get("name"))
                    continue
            _add_candidate(token)

        return values

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for domain in self._extract_domains(raw_output):
            try:
                registry = DiscoveryRegistry.model_validate(
                    {
                        "discovered_domain": domain,
                        "intel_source": "chaos_dataset",
                        "timestamp": datetime.now(UTC),
                    }
                )
            except Exception:
                continue

            findings.append(
                {
                    "type": "subdomain",
                    "value": registry.discovered_domain,
                    "target": target,
                    "severity": "info",
                    "confidence": 0.95,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": domain,
                    "context": {
                        "source": registry.intel_source,
                        "discovery_registry": registry.model_dump(mode="json"),
                        "snl_mode": "fixture_only",
                    },
                    "recommended_next_tools": ["dnsx", "httpx_probe"],
                    "recommended_next_actions": ["resolve_dns"],
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
            value = str(finding.get("value", "")).lower()
            if f"{finding.get('target', '').lower()}|subdomain|{value}" in known:
                noise.append(finding)
                continue

            if value.startswith("*."):
                noise.append(finding)
                continue
            if any(token in value for token in _HIGH_VALUE_KEYWORDS):
                finding["severity"] = "medium"
                finding["confidence"] = 0.97
            signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        high_value = [
            item
            for item in signal
            if str(item.get("severity", "")).lower() in {"medium", "high", "critical"}
        ]
        return {
            "next_agents": ["dnsx", "httpx_probe"],
            "priority_targets": [f["value"] for f in high_value[:15]],
            "operator_summary": (
                f"Chaos fixture ingestion accepted {len(signal)} passive assets for {target}. "
                "Cloud Burst telemetry emitted for dashboard visibility."
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
        fixture = opts.get("fixture_data")
        if fixture is None and isinstance(opts.get("fixture_path"), str):
            fixture = Path(opts["fixture_path"]).read_text(encoding="utf-8")

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

        records = self.ingest_fixture(fixture, target=target, options=opts)
        stdout = "\n".join(record.discovered_domain for record in records)
        ended_at = datetime.now(UTC)
        runtime_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))

        result = self.map_output(
            target=target,
            command=["fixture://chaos"],
            stdout=stdout,
            stderr="",
            exit_code=0,
            started_at=started_at,
            ended_at=ended_at,
            runtime_ms=runtime_ms,
            mission_id=mission_id,
            status="success",
            options=opts,
        )

        context = dict(result.target_context)
        context.update(
            {
                "mode": "stub_fixture",
                "normalized_records": [record.model_dump(mode="json") for record in records],
                "snl_interface": policy["snl_interface"],
                "telemetry": self.get_telemetry_events(),
            }
        )
        return result.model_copy(update={"target_context": context})
