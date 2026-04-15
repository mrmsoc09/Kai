from __future__ import annotations

from datetime import UTC, datetime
import json
import re
import shutil
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from apps.backend.src.core.protocol import KaisonResult, KaisonResultMetadata
from apps.backend.src.core.scope_guardrails import (
    audit_scope_decision,
    evaluate_target_scope,
    load_scope_policy,
)

from ..base_tool_agent import BaseToolAgent
from ..darknet_leak_schemas import DiscoveryRegistry
from ..osint_schemas import IdentityRegistry


_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}
_HIGH_VALUE_TYPES = {
    "CREDENTIAL_COMPROMISED",
    "EMAILADDR_COMPROMISED",
    "LEAKED_INFO",
    "PASSWORD_COMPROMISED",
    "VULNERABILITY_CVE_CRITICAL",
    "VULNERABILITY_CVE_HIGH",
    "DARKWEB_MENTION",
    "SOCIAL_MEDIA",
}
_IDENTITY_HINT_TYPES = {"SOCIAL_MEDIA", "USERNAME", "HUMAN_NAME", "EMAILADDR"}
_SOCIAL_DOMAINS = {
    "twitter.com": "twitter",
    "x.com": "x",
    "github.com": "github",
    "gitlab.com": "gitlab",
    "linkedin.com": "linkedin",
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "reddit.com": "reddit",
    "youtube.com": "youtube",
    "t.me": "telegram",
}
_HANDLE_RE = re.compile(r"@?([A-Za-z0-9._-]{2,64})")
_ONION_RE = re.compile(r"([a-z2-7]{16,56}\.onion)", re.IGNORECASE)


class SpiderfootAgent(BaseToolAgent):
    TOOL_NAME = "spiderfoot"

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
        output_path = f"{artifact_dir}/spiderfoot.json"
        timeout_seconds = min(max(int(opts.get("timeout_seconds", 1200)), 30), 1800)
        modules = str(
            opts.get(
                "modules",
                "sfp_dns,sfp_ssl,sfp_whois,sfp_crt,sfp_netcraft,sfp_socialprofiles",
            )
        )
        binary = "sf" if shutil.which("sf") else "spiderfoot"
        return [
            binary,
            "-s",
            target,
            "-m",
            modules,
            "-o",
            "json",
            "-q",
            "-l",
            output_path,
            "-t",
            str(timeout_seconds),
        ]

    @staticmethod
    def _extract_entries(raw_output: str) -> list[dict[str, Any]]:
        payload: Any
        try:
            payload = json.loads(raw_output.strip())
        except (json.JSONDecodeError, TypeError):
            payload = []
            for line in raw_output.splitlines():
                token = line.strip()
                if not token:
                    continue
                try:
                    item = json.loads(token)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    payload.append(item)

        if isinstance(payload, dict):
            rows = payload.get("results", [])
        else:
            rows = payload
        return rows if isinstance(rows, list) else []

    @staticmethod
    def _extract_social_identity(value: str) -> tuple[str, str, str] | None:
        token = value.strip()
        if not token:
            return None

        parsed = urlparse(token)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            host = parsed.netloc.lower()
            platform = _SOCIAL_DOMAINS.get(host)
            if platform:
                parts = [p for p in parsed.path.split("/") if p]
                if not parts:
                    return None
                handle = parts[0].lstrip("@")
                return handle, platform, token
            return None

        match = _HANDLE_RE.search(token)
        if not match:
            return None
        handle = match.group(1).lstrip("@")
        platform = "unknown"
        return handle, platform, f"https://social.local/{handle}"

    @staticmethod
    def _extract_onion_domain(value: str) -> str | None:
        match = _ONION_RE.search(value or "")
        if not match:
            return None
        return match.group(1).lower()

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        rows = self._extract_entries(raw_output)
        if not rows:
            return findings

        for entry in rows:
            if not isinstance(entry, dict):
                continue

            data_type = str(entry.get("type", "UNKNOWN")).strip().upper()
            value = str(entry.get("data", "")).strip()
            if not value:
                continue

            context = {
                "data_type": data_type,
                "module": str(entry.get("module", "")).strip(),
                "snl_mode": "fixture_only",
            }
            severity = "high" if data_type in _HIGH_VALUE_TYPES else "info"

            onion_domain = self._extract_onion_domain(value)
            if onion_domain:
                try:
                    discovery = DiscoveryRegistry.model_validate(
                        {
                            "discovered_domain": onion_domain,
                            "intel_source": "INTEL:DARKNET",
                            "timestamp": datetime.now(UTC),
                            "onion_url": value if value.startswith("http") else f"http://{onion_domain}",
                            "source_engine": "spiderfoot",
                            "crawl_depth": 1,
                        }
                    )
                    context["discovery_registry"] = discovery.model_dump(mode="json")
                    context["intel_source"] = "INTEL:DARKNET"
                    severity = "high"
                except Exception:
                    pass

            if data_type in _IDENTITY_HINT_TYPES or any(domain in value.lower() for domain in _SOCIAL_DOMAINS):
                social = self._extract_social_identity(value)
                if social:
                    handle, platform, profile_url = social
                    try:
                        identity = IdentityRegistry.model_validate(
                            {
                                "social_handle": handle,
                                "platform_detected": platform,
                                "profile_url": profile_url,
                            }
                        )
                        context["identity_registry"] = identity.model_dump(mode="json")
                        severity = "medium" if severity == "info" else severity
                    except Exception:
                        pass

            findings.append(
                {
                    "type": "osint_finding",
                    "value": value[:500],
                    "target": target,
                    "severity": severity,
                    "confidence": 0.9 if severity in {"high", "critical"} else 0.75,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(entry, ensure_ascii=True)[:1200],
                    "context": context,
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["investigate"],
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
            ftype = str(finding.get("type", "osint_finding")).lower()
            target_value = str(finding.get("target", "")).lower()
            if f"{target_value}|{ftype}|{value}" in known:
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
        identity_hits = sum(1 for f in signal if "identity_registry" in f.get("context", {}))
        darknet_hits = sum(1 for f in signal if "discovery_registry" in f.get("context", {}))
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "identity_hits": identity_hits,
            "darknet_hits": darknet_hits,
            "operator_summary": (
                f"Spiderfoot fixture ingestion returned {len(signal)} high-signal nodes for {target}. "
                f"Identity nodes: {identity_hits}; darknet nodes: {darknet_hits}."
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
        fixture = opts.get("fixture_data")
        if fixture is None and isinstance(opts.get("fixture_path"), str):
            fixture = Path(opts["fixture_path"]).read_text(encoding="utf-8")

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

        fixture_text = fixture if isinstance(fixture, str) else json.dumps(fixture)
        ended_at = datetime.now(UTC)
        runtime_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))
        result = self.map_output(
            target=target,
            command=["fixture://spiderfoot"],
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

        self._emit_telemetry("AGENT_STATUS", "ACTIVE")
        self._emit_telemetry("INTEL_NODES_ACTIVE", len(result.findings))
        if any("onion" in str(f.raw_evidence).lower() for f in result.findings):
            self._emit_telemetry("EventLog", "DEEP_WEB_PULSE_DEEP_PURPLE_GRADIENT")

        context = dict(result.target_context)
        context.update(
            {
                "mode": "stub_fixture",
                "snl_interface": policy["snl_interface"],
                "telemetry": self.get_telemetry_events(),
            }
        )
        return result.model_copy(update={"target_context": context})
