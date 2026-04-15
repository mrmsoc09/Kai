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
from ..httpx_probe.schemas import HttpxRawRecord, ServiceRegistry


_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}


class NiktoAgent(BaseToolAgent):
    TOOL_NAME = "nikto"

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
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        waf_detected = bool(opts.get("waf_detected", False))

        cmd = [
            "nikto",
            "-h",
            target,
            "-o",
            f"{artifact_dir}/nikto.json",
            "-Format",
            "json",
            "-Tuning",
            "1234569",
            "-maxtime",
            "300",
            "-timeout",
            "10",
        ]
        if waf_detected:
            cmd.extend(["-evasion", "1"])
        return cmd

    @staticmethod
    def _ensure_url(target: str, uri: str | None = None) -> str:
        base = target.strip()
        if not base.startswith("http://") and not base.startswith("https://"):
            base = f"http://{base}"
        if uri and uri.strip().startswith("/"):
            return f"{base.rstrip('/')}{uri.strip()}"
        return base

    @staticmethod
    def _severity_from_value(value: Any) -> str:
        token = str(value or "").strip().lower()
        if token in {"1", "critical"}:
            return "critical"
        if token in {"2", "high"}:
            return "high"
        if token in {"3", "medium"}:
            return "medium"
        return "low"

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        token = raw_output.strip()
        if not token:
            return findings

        try:
            data = json.loads(token)
        except json.JSONDecodeError:
            return findings

        vulnerabilities = data.get("vulnerabilities", []) if isinstance(data, dict) else []
        if not isinstance(vulnerabilities, list):
            return findings

        for vuln in vulnerabilities:
            if not isinstance(vuln, dict):
                continue

            title = str(vuln.get("title", "")).strip() or "nikto_finding"
            uri = str(vuln.get("uri", "")).strip()
            severity = self._severity_from_value(vuln.get("severity", "4"))

            try:
                raw_record = HttpxRawRecord.model_validate(
                    {
                        "url": self._ensure_url(target, uri),
                        "title": title,
                        "status_code": int(vuln.get("status", 200) or 200),
                        "server": str(vuln.get("server", "")).strip() or "unknown",
                        "content_length": int(vuln.get("content_length", 0) or 0),
                    }
                )
                service_registry = ServiceRegistry.from_raw(raw_record, target_domain=target)
            except Exception:
                continue

            findings.append(
                {
                    "type": "service_vulnerability",
                    "value": title,
                    "target": target,
                    "severity": severity,
                    "confidence": 0.86 if severity in {"critical", "high"} else 0.74,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(vuln, ensure_ascii=True)[:2000],
                    "context": {
                        "osvdb_id": str(vuln.get("id", "")),
                        "uri": uri,
                        "method": str(vuln.get("method", "")),
                        "service_registry": service_registry.model_dump(mode="json"),
                        "snl_mode": "fixture_only",
                    },
                    "recommended_next_tools": ["nuclei_scan", "EvidenceAnalystAgent"],
                    "recommended_next_actions": ["validate_web_vulnerability"],
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
            key = f"{str(finding.get('target', '')).lower()}|service_vulnerability|{str(finding.get('value', '')).lower()}"
            if key in known:
                noise.append(finding)
                continue

            severity = str(finding.get("severity", "low")).lower()
            if severity in {"critical", "high", "medium"}:
                signal.append(finding)
            else:
                noise.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        crit = len([f for f in signal if str(f.get("severity", "")).lower() == "critical"])
        high = len([f for f in signal if str(f.get("severity", "")).lower() == "high"])
        return {
            "next_agents": ["nuclei_scan", "EvidenceAnalystAgent"],
            "critical_findings": crit,
            "high_findings": high,
            "operator_summary": (
                f"Nikto normalized {len(signal)} service-linked findings for {target}. "
                f"Critical: {crit}, High: {high}."
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
            command=["fixture://nikto"],
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

        self._emit_telemetry("AGENT_STATUS", "WEB_SERVER_AUDIT")
        self._emit_telemetry("NIKTO_FINDINGS", len(result.findings))

        context = dict(result.target_context)
        context.update(
            {
                "mode": "stub_fixture",
                "snl_interface": policy.get("snl_interface"),
                "telemetry": self.get_telemetry_events(),
            }
        )
        return result.model_copy(update={"target_context": context})
