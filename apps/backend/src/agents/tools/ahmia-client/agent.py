from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from apps.backend.src.core.protocol import (
    FindingType,
    KaisonFinding,
    KaisonResult,
    KaisonResultMetadata,
    Severity,
)
from apps.backend.src.core.scope_guardrails import (
    audit_scope_decision,
    evaluate_target_scope,
    load_scope_policy,
)

from ..base_tool_agent import BaseToolAgent
from ..darknet_leak_schemas import DiscoveryRegistry


_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}
_REQUIRED_TOR_PROXY = "127.0.0.1:9050"
_ONION_URL_RE = re.compile(r"https?://[a-z2-7]{16,56}\.onion[^\s<\"]*", re.IGNORECASE)


class AhmiaClientAgent(BaseToolAgent):
    """
    Ahmia specialist agent for searching indexed darknet content.
    Enforces traffic via K1 Sovereign Network Layer Tor proxy.
    """

    TOOL_NAME = "ahmia-client"

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

    def _emit_telemetry(self, metric: str, value: Any, payload: dict[str, Any] | None = None) -> None:
        event = {
            "tool": self.TOOL_NAME,
            "metric": metric,
            "value": value,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if payload:
            event["payload"] = payload
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
        
        # Strict enforcement of K1 proxy
        tor_proxy = str(opts.get("tor_proxy", _REQUIRED_TOR_PROXY)).strip()
        tor_ok = tor_proxy == _REQUIRED_TOR_PROXY

        allowed = decision.allowed and scope_label == _APPROVED_SCOPE_LABEL and snl_ok and tor_ok
        reason = decision.reason
        if scope_label != _APPROVED_SCOPE_LABEL:
            reason = "missing_approved_research_scope"
        elif not snl_ok:
            reason = f"snl_interface_not_allowed:{snl_interface}"
        elif not tor_ok:
            reason = f"tor_proxy_required:{_REQUIRED_TOR_PROXY}"

        return {
            "allowed": allowed,
            "reason": reason,
            "target": decision.normalized_host,
            "matched_rule": decision.matched_rule,
            "snl_interface": snl_interface,
            "tor_proxy": tor_proxy,
        }

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        
        # Mandatory K1 proxy
        tor_proxy = str(opts.get("tor_proxy", _REQUIRED_TOR_PROXY))
        
        # ahmia search <target> --proxy <proxy> --output <dir>
        return [
            "ahmia",
            "search",
            target,
            "--proxy",
            tor_proxy,
            "--output",
            f"{artifact_dir}/ahmia_{int(datetime.now(UTC).timestamp())}.json",
        ]

    @staticmethod
    def _extract_domain(url: str) -> str:
        token = url.split("//", 1)[1] if "//" in url else url
        return token.split("/", 1)[0].strip().lower().rstrip(".")

    def map_output(
        self,
        *,
        target: str,
        command: list[str],
        stdout: str,
        stderr: str,
        exit_code: int,
        started_at: datetime,
        ended_at: datetime,
        runtime_ms: int,
        mission_id: str,
        status: str,
        options: dict[str, Any] | None = None,
    ) -> KaisonResult:
        findings: list[KaisonFinding] = []
        raw_output = stdout.strip()
        if not raw_output:
            return KaisonResult(
                mission_id=mission_id,
                source_agent=self.TOOL_NAME,
                status=status,
                target_context={
                    "target": target,
                    "command": command,
                    "exit_code": exit_code,
                    "stderr": stderr[:2000],
                },
                metadata=KaisonResultMetadata(
                    started_at=started_at,
                    ended_at=ended_at,
                    runtime_ms=runtime_ms,
                ),
                findings=[],
            )

        urls = set(_ONION_URL_RE.findall(raw_output))
        for url in urls:
            domain = self._extract_domain(url)
            try:
                record = DiscoveryRegistry.model_validate(
                    {
                        "discovered_domain": domain,
                        "intel_source": "tor",
                        "timestamp": datetime.now(UTC),
                        "onion_url": url,
                        "source_engine": "ahmia",
                        "crawl_depth": 0,
                    }
                )
            except Exception:
                continue

            findings.append(
                KaisonFinding(
                    finding_type=FindingType.CONFIG,
                    value=record.onion_url or f"http://{record.discovered_domain}",
                    source_agent=self.TOOL_NAME,
                    confidence=0.75,
                    severity=Severity.MEDIUM,
                    raw_evidence={
                        "onion_domain": record.discovered_domain,
                        "source_engine": record.source_engine,
                        "discovery_registry": record.model_dump(mode="json"),
                    },
                )
            )

        # Trigger V-RAD Telemetry for Dark Web Site Discovery
        if findings:
            self._emit_telemetry(
                "V-RAD_EVENT",
                "Deep Web Pulse",
                payload={
                    "v-rad_color": "DARK_PURPLE_BLACK",
                    "discovery_count": len(findings),
                    "summary": f"Ahmia indexed {len(findings)} darknet results for {target}"
                }
            )

        return KaisonResult(
            mission_id=mission_id,
            source_agent=self.TOOL_NAME,
            status=status,
            target_context={
                "target": target,
                "command": command,
                "exit_code": exit_code,
                "options": options,
            },
            metadata=KaisonResultMetadata(
                started_at=started_at,
                ended_at=ended_at,
                runtime_ms=runtime_ms,
            ),
            findings=findings,
        )

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        if not raw_output.strip():
            return result
        for line in raw_output.splitlines():
            url = line.strip()
            if not url:
                continue
            result.append({
                "type": "darknet_finding",
                "value": url[:500],
                "target": target,
                "severity": "medium",
                "confidence": 0.75,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": url[:1200],
                "context": {"ahmia_search": True},
                "recommended_next_tools": ["EvidenceAnalystAgent"],
                "recommended_next_actions": ["investigate"],
            })
        return result

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()
        for finding in findings:
            value = str(finding.get("value", "")).lower()
            ftype = str(finding.get("type", "darknet_finding")).lower()
            tgt = str(finding.get("target", "")).lower()
            if f"{tgt}|{ftype}|{value}" in known:
                noise.append(finding)
                continue
            if str(finding.get("severity", "info")).lower() == "info":
                noise.append(finding)
                continue
            signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "total_findings": len(signal),
            "operator_summary": (
                f"Ahmia search returned {len(signal)} dark web results for {target}."
            ),
        }

    def execute(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        """
        Executes Ahmia search with K1 proxy routing.
        """
        opts = dict(options or {})
        policy = self.check_policy(target, opts)
        
        if not policy["allowed"]:
            now = datetime.now(UTC)
            return KaisonResult(
                mission_id=mission_id,
                source_agent=self.TOOL_NAME,
                status="failure",
                target_context={
                    "target": target, 
                    "error": f"policy_blocked:{policy['reason']}"
                },
                metadata=KaisonResultMetadata(
                    started_at=now,
                    ended_at=now,
                    runtime_ms=0,
                ),
                findings=[],
            )

        # Force K1 Tor proxy
        opts["tor_proxy"] = policy["tor_proxy"]
        
        # Live execution
        result = super().execute(target, opts, mission_id=mission_id)
        
        # Enrich context
        enriched_context = dict(result.target_context)
        enriched_context["snl_interface"] = policy.get("snl_interface")
        enriched_context["tor_proxy"] = policy.get("tor_proxy")
        enriched_context["telemetry"] = self.get_telemetry_events()
        
        return result.model_copy(update={"target_context": enriched_context})


class AhmiaAgent(AhmiaClientAgent):
    """Alias class for architecture briefs."""
