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
from ..content_discovery_schemas import XssRegistry


_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}
_MAX_RPS_CAP = 50


class DalfoxAgent(BaseToolAgent):
    TOOL_NAME = "dalfox"

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

    @staticmethod
    def _normalize_rps(options: dict[str, Any]) -> int:
        raw = options.get("max_requests_per_second", options.get("rate_limit", 5))
        try:
            rps = int(raw)
        except (TypeError, ValueError):
            rps = 5
        return max(1, min(_MAX_RPS_CAP, rps))

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
            "max_requests_per_second": self._normalize_rps(opts),
        }

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        input_file = opts.get("input_file")
        if input_file:
            cmd = ["dalfox", "file", str(input_file), "--silence"]
        else:
            cmd = ["dalfox", "url", target, "--silence"]

        if opts.get("skip_bav", True):
            cmd.append("--skip-bav")

        if opts.get("blind"):
            cmd += ["-b", str(opts["blind"])]

        if opts.get("header"):
            cmd += ["-H", str(opts["header"])]

        worker_count = max(1, min(30, self._normalize_rps(opts)))
        cmd += ["--worker", str(worker_count), "--format", "json"]
        return cmd

    @staticmethod
    def _derive_vuln_type(raw_type: str) -> str:
        token = str(raw_type or "").strip().lower()
        if token == "stored":
            return "stored_xss"
        if token == "dom":
            return "dom_xss"
        if token == "blind":
            return "blind_xss"
        return "reflected_xss"

    @staticmethod
    def _derive_risk(vuln_type: str) -> str:
        if vuln_type in {"stored_xss", "blind_xss"}:
            return "critical"
        if vuln_type == "dom_xss":
            return "high"
        return "high"

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.splitlines():
            token = line.strip()
            if not token or not token.startswith("{"):
                continue
            try:
                data = json.loads(token)
            except json.JSONDecodeError:
                continue

            url = str(data.get("url", "")).strip()
            param = str(data.get("param") or data.get("inurlparam") or "").strip()
            payload = str(data.get("payload") or data.get("evidence") or data.get("poc") or "").strip()
            if not url or not param or not payload:
                continue

            vuln_type = self._derive_vuln_type(str(data.get("type", "")))
            risk = self._derive_risk(vuln_type)
            try:
                xss_registry = XssRegistry.model_validate(
                    {
                        "vulnerable_url": url,
                        "vulnerable_parameter": param,
                        "payload": payload,
                        "vuln_type": vuln_type,
                        "risk_level": risk,
                        "confirmed": True,
                        "detected_at": datetime.now(UTC),
                    }
                )
            except Exception:
                continue

            findings.append(
                {
                    "type": "vulnerability",
                    "value": xss_registry.vulnerable_url,
                    "target": target,
                    "severity": xss_registry.risk_level,
                    "confidence": 0.92,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": token[:1500],
                    "context": {
                        "url": xss_registry.vulnerable_url,
                        "parameter": xss_registry.vulnerable_parameter,
                        "finding_type": str(data.get("type", "")),
                        "evidence": str(data.get("evidence", ""))[:500],
                        "poc": str(data.get("poc", ""))[:500],
                        "xss_registry": xss_registry.model_dump(mode="json"),
                        "snl_mode": "fixture_only",
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["validate_xss"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()

        for item in findings:
            value = str(item.get("value", "")).lower()
            if f"{str(item.get('target', '')).lower()}|vulnerability|{value}" in known:
                noise.append(item)
                continue

            if item.get("context", {}).get("xss_registry", {}).get("confirmed", True):
                item["signal_reason"] = "confirmed_xss"
                signal.append(item)
            else:
                noise.append(item)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        confirmed = [s for s in signal if s.get("signal_reason") == "confirmed_xss"]
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "confirmed_pocs": [s.get("context", {}).get("poc", "") for s in confirmed],
            "instructions": (
                f"Dalfox identified {len(confirmed)} confirmed XSS vulnerabilities for {target}. "
                "Trigger evidence capture and analyst validation."
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
                target_context={"target": target, "mode": "stub_only", "error": f"policy_blocked:{policy['reason']}"},
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
            command=["fixture://dalfox"],
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

        confirmed = 0
        for finding in result.findings:
            if finding.raw_evidence.get("context", {}).get("xss_registry", {}).get("confirmed", False):
                confirmed += 1

        self._emit_telemetry("AGENT_STATUS", "XSS_VALIDATION")
        self._emit_telemetry("XSS_CONFIRMED", confirmed)
        if confirmed > 0:
            self._emit_telemetry("EventLog", "CROSS_SITE_FLASH_CYAN")

        context = dict(result.target_context)
        context.update(
            {
                "mode": "stub_fixture",
                "snl_interface": policy["snl_interface"],
                "max_requests_per_second": policy["max_requests_per_second"],
                "telemetry": self.get_telemetry_events(),
            }
        )
        return result.model_copy(update={"target_context": context})
