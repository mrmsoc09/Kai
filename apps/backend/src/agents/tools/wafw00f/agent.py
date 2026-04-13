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
from ..network_fingerprint_schemas import TargetRegistry


_PHASE7_AGENTS = [
    "nuclei_scan",
    "nikto",
    "testssl",
    "dalfox",
    "sqlmap",
    "ssrfmap",
    "corsy",
    "crlfuzz",
    "smuggler",
    "searchsploit",
]
_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}


class Wafw00fAgent(BaseToolAgent):
    TOOL_NAME = "wafw00f"

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
        output_file = opts.get("output_file", f"{opts.get('artifact_dir', '/tmp')}/wafw00f.json")
        return ["wafw00f", target, "-o", str(output_file), "-f", "json"]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        raw_output = raw_output.strip()
        if not raw_output:
            return []

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            data = {}

        payloads = data if isinstance(data, list) else [data]
        findings: list[dict[str, Any]] = []
        for item in payloads:
            if not isinstance(item, dict):
                continue
            waf_name = str(item.get("waf_name") or item.get("firewall") or item.get("manufacturer") or "none")
            detected = bool(item.get("detected") or item.get("waf_detected") or waf_name.lower() != "none")
            confidence = float(item.get("confidence", 0.9 if detected else 0.7))

            try:
                target_registry = TargetRegistry.model_validate(
                    {
                        "target": target,
                        "waf_present": detected,
                        "waf_name": waf_name,
                        "checked_at": datetime.now(UTC),
                    }
                )
            except Exception:
                continue

            findings.append(
                {
                    "type": "waf_fingerprint",
                    "value": waf_name,
                    "target": target,
                    "severity": "medium" if detected else "info",
                    "confidence": max(0.0, min(1.0, confidence)),
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(item, ensure_ascii=True),
                    "context": {
                        "waf_detected": target_registry.waf_present,
                        "waf_name": target_registry.waf_name,
                        "target_registry": target_registry.model_dump(mode="json"),
                        "snl_mode": "fixture_only",
                    },
                    "recommended_next_tools": _PHASE7_AGENTS,
                    "recommended_next_actions": ["apply_waf_adaptive_rate_limit"],
                }
            )
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        known = self.load_memory()
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        for finding in findings:
            value = str(finding.get("value", ""))
            if f"{finding.get('target', '').lower()}|waf_fingerprint|{value}" in known:
                noise.append(finding)
                continue
            signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        detected = any(bool(item.get("context", {}).get("waf_detected")) for item in signal)
        waf_name = "none"
        for item in signal:
            if item.get("context", {}).get("waf_detected"):
                waf_name = str(item.get("context", {}).get("waf_name", "unknown"))
                break

        rate_limit = 2 if detected else 10
        note = (
            f"WAF detected ({waf_name}). Use reduced scan intensity and adaptive pacing."
            if detected
            else "No WAF detected. Baseline pacing profile allowed."
        )
        configuration_hints = {agent: {"rate_limit": rate_limit, "note": note} for agent in _PHASE7_AGENTS}

        return {
            "next_agents": _PHASE7_AGENTS,
            "configuration_hints": configuration_hints,
            "operator_summary": (
                f"WAF pre-check for {target}: {'DETECTED' if detected else 'NOT DETECTED'} ({waf_name})."
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
            command=["fixture://wafw00f"],
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

        self._emit_telemetry("AGENT_STATUS", "WAF_CHECK")
        waf_hits = sum(1 for f in result.findings if bool(f.raw_evidence.get("context", {}).get("waf_detected")))
        self._emit_telemetry("WAF_DETECTIONS", waf_hits)

        context = dict(result.target_context)
        context.update(
            {
                "mode": "stub_fixture",
                "snl_interface": policy["snl_interface"],
                "telemetry": self.get_telemetry_events(),
            }
        )
        return result.model_copy(update={"target_context": context})
