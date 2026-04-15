from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any, Callable

from apps.backend.src.core.protocol import KaisonResult, KaisonResultMetadata
from apps.backend.src.core.scope_guardrails import (
    audit_scope_decision,
    evaluate_target_scope,
    load_scope_policy,
)

from ..base_tool_agent import BaseToolAgent


_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}
_ALLOWED_MODULE_RE = re.compile(r"^(auxiliary|exploit)/[a-zA-Z0-9_./-]+$")
_ALLOWED_TARGET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,252}$")
_PORT_MODULE_HINTS = {
    21: "auxiliary/scanner/ftp/ftp_version",
    22: "auxiliary/scanner/ssh/ssh_version",
    25: "auxiliary/scanner/smtp/smtp_version",
    80: "auxiliary/scanner/http/http_version",
    443: "auxiliary/scanner/http/http_version",
    445: "auxiliary/scanner/smb/smb_version",
    3306: "auxiliary/scanner/mysql/mysql_version",
    5432: "auxiliary/scanner/postgres/postgres_version",
    6379: "auxiliary/scanner/redis/redis_server",
}


class MetasploitFrameworkAgent(BaseToolAgent):
    TOOL_NAME = "metasploit-framework"

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
    def _normalize_target(target: str) -> str:
        token = (target or "").strip()
        if "://" in token:
            token = token.split("://", 1)[1]
        token = token.split("/", 1)[0].strip()
        return token

    @staticmethod
    def _recommended_module_from_ports(ports: list[int]) -> str:
        for port in ports:
            if port in _PORT_MODULE_HINTS:
                return _PORT_MODULE_HINTS[port]
        return "auxiliary/scanner/http/http_version"

    def check_policy(self, target: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        opts = options or {}
        scope_label = str(opts.get("research_scope", _APPROVED_SCOPE_LABEL)).strip()
        snl_interface = str(opts.get("snl_interface", "tun0")).strip()
        snl_ok = snl_interface in _ALLOWED_SNL_INTERFACES

        normalized_target = self._normalize_target(target)
        target_ok = bool(_ALLOWED_TARGET_RE.fullmatch(normalized_target))

        mode = str(opts.get("mode", "listener")).strip().lower()
        check_only = bool(opts.get("check_only", True))

        policy = load_scope_policy(opts.get("scope_policy_path"))
        decision = evaluate_target_scope(normalized_target or target, policy, safe_mode=True)
        audit_scope_decision(decision)

        allowed = (
            decision.allowed
            and scope_label == _APPROVED_SCOPE_LABEL
            and snl_ok
            and target_ok
            and check_only
            and mode in {"listener", "module_check"}
        )

        reason = decision.reason
        if scope_label != _APPROVED_SCOPE_LABEL:
            reason = "missing_approved_research_scope"
        elif not snl_ok:
            reason = f"snl_interface_not_allowed:{snl_interface}"
        elif not target_ok:
            reason = "invalid_target"
        elif not check_only:
            reason = "check_only_required"
        elif mode not in {"listener", "module_check"}:
            reason = "unsupported_mode"

        return {
            "allowed": allowed,
            "reason": reason,
            "target": decision.normalized_host,
            "matched_rule": decision.matched_rule,
            "snl_interface": snl_interface,
            "mode": mode,
            "check_only": check_only,
        }

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        mode = str(opts.get("mode", "listener")).strip().lower()
        check_only = bool(opts.get("check_only", True))
        if not check_only:
            raise ValueError("Metasploit wrapper enforces CHECK-only mode")

        safe_target = self._normalize_target(target)
        if not _ALLOWED_TARGET_RE.fullmatch(safe_target):
            raise ValueError("metasploit-framework target must be host/domain/IP without metacharacters")

        port_hints = opts.get("ports", [])
        if isinstance(port_hints, list):
            parsed_ports = [int(p) for p in port_hints if str(p).isdigit()]
        else:
            parsed_ports = []

        module = str(opts.get("module") or self._recommended_module_from_ports(parsed_ports)).strip()
        if not _ALLOWED_MODULE_RE.fullmatch(module):
            raise ValueError("metasploit module must match exploit/* or auxiliary/*")

        if mode == "listener":
            rpc_host = str(opts.get("msfrpc_host", "127.0.0.1")).strip()
            rpc_port = str(opts.get("msfrpc_port", "55553")).strip()
            return ["msf_rpc_healthcheck", "--host", rpc_host, "--port", rpc_port, "--mode", "listener"]

        script = f"use {module}; setg RHOSTS {safe_target}; check; exit -y"
        return ["msfconsole", "-q", "-x", script]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        token = raw_output.strip()
        if not token:
            return findings

        lines: list[str] = []
        try:
            payload = json.loads(token)
            if isinstance(payload, dict):
                lines.append(str(payload.get("status", "")))
                lines.append(str(payload.get("message", "")))
                findings.append(
                    {
                        "type": "metasploit_status",
                        "value": str(payload.get("message") or payload.get("status") or "msf_event"),
                        "target": target,
                        "severity": "medium" if str(payload.get("status", "")).lower() == "cooldown" else "info",
                        "confidence": 0.85,
                        "source_tool": self.TOOL_NAME,
                        "raw_evidence": json.dumps(payload, ensure_ascii=True)[:2000],
                        "context": {
                            "agent_status": str(payload.get("status", "ACTIVE")).upper() or "ACTIVE",
                            "current_phase": str(payload.get("phase", "LISTENER")).upper(),
                            "module": str(payload.get("module", "")),
                            "check_only": True,
                            "snl_mode": "fixture_only",
                        },
                        "recommended_next_tools": ["EvidenceAnalystAgent"],
                        "recommended_next_actions": ["review_listener_health", "review_check_output"],
                    }
                )
            elif isinstance(payload, list):
                for entry in payload:
                    if isinstance(entry, dict):
                        findings.extend(self.parse_output(json.dumps(entry), target))
                return findings
        except json.JSONDecodeError:
            lines.extend(token.splitlines())

        if not findings:
            for line in lines:
                text = line.strip()
                if not text:
                    continue
                lowered = text.lower()
                is_cooldown = "rate limit" in lowered or "429" in lowered
                findings.append(
                    {
                        "type": "metasploit_status",
                        "value": text[:300],
                        "target": target,
                        "severity": "medium" if is_cooldown else "info",
                        "confidence": 0.75,
                        "source_tool": self.TOOL_NAME,
                        "raw_evidence": text[:1000],
                        "context": {
                            "agent_status": "COOLDOWN" if is_cooldown else "ACTIVE",
                            "current_phase": "LISTENER",
                            "check_only": True,
                            "snl_mode": "fixture_only",
                        },
                        "recommended_next_tools": ["EvidenceAnalystAgent"],
                        "recommended_next_actions": ["review_listener_health"],
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
            key = f"{str(finding.get('target', '')).lower()}|metasploit_status|{str(finding.get('value', '')).lower()}"
            if key in known:
                noise.append(finding)
                continue
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        cooldown = len(
            [
                f
                for f in signal
                if str(f.get("context", {}).get("agent_status", "")).upper() == "COOLDOWN"
            ]
        )
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "cooldown_events": cooldown,
            "operator_summary": (
                f"Metasploit CHECK-only listener/module telemetry captured {len(signal)} records for {target}. "
                f"Cooldown events: {cooldown}."
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
            command=["fixture://metasploit-framework"],
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

        cooldown = 0
        for finding in result.findings:
            status = str(finding.raw_evidence.get("context", {}).get("agent_status", "")).upper()
            if status == "COOLDOWN":
                cooldown += 1

        self._emit_telemetry("AGENT_STATUS", "COOLDOWN" if cooldown else "ACTIVE")
        self._emit_telemetry("DISCOVERY_COUNT", len(result.findings))
        self._emit_telemetry("CURRENT_PHASE", "DNS_BRUTE" if policy.get("mode") == "module_check" else "LISTENER")

        context = dict(result.target_context)
        context.update(
            {
                "mode": "stub_fixture",
                "check_only": True,
                "snl_interface": policy.get("snl_interface"),
                "telemetry": self.get_telemetry_events(),
            }
        )
        return result.model_copy(update={"target_context": context})


class MetasploitAgent(MetasploitFrameworkAgent):
    """Alias for architecture briefs that reference MetasploitAgent."""
