from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

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


class OnionsearchAgent(BaseToolAgent):
    """
    OnionSearch specialist agent for aggregating darknet search engine results.
    Enforces routing via K1 Sovereign Network Layer Tor proxy.
    """

    TOOL_NAME = "onionsearch"

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._telemetry_events: list[dict[str, Any]] = []
        self._telemetry_hook: Callable[[dict[str, Any]], None] | None = None

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
        
        # Mandatory K1 proxy
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
        
        # Use K1 mandatory proxy
        tor_proxy = str(opts.get("tor_proxy", _REQUIRED_TOR_PROXY))
        
        # Engines selection (default to wide coverage)
        engines = opts.get("engines")
        if isinstance(engines, list) and engines:
            engine_arg = ",".join(str(e).strip() for e in engines if str(e).strip())
        else:
            engine_arg = "ahmia,darksearch,phobos,haystak,torch,candle"
            
        # onionsearch <target> --proxy <proxy> --engines <engines> --output <dir>
        return [
            "onionsearch",
            target,
            "--proxy",
            tor_proxy,
            "--engines",
            engine_arg,
            "--output",
            f"{artifact_dir}/onionsearch_{int(datetime.now(UTC).timestamp())}.json",
        ]

    @staticmethod
    def _extract_onion_domain(url: str) -> str:
        token = url.strip().lower()
        if token.startswith("http://") or token.startswith("https://"):
            try:
                parsed = urlparse(token)
                return (parsed.netloc or "").lower()
            except Exception:
                return token.split("//", 1)[-1].split("/", 1)[0]
        return token.split("/", 1)[0]

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

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            return KaisonResult(
                mission_id=mission_id,
                source_agent=self.TOOL_NAME,
                status="failure",
                target_context={
                    "target": target,
                    "error": "json_parse_failed",
                },
                metadata=KaisonResultMetadata(
                    started_at=started_at,
                    ended_at=ended_at,
                    runtime_ms=runtime_ms,
                ),
                findings=[],
            )

        results = data.get("results", []) if isinstance(data, dict) else []
        if not isinstance(results, list):
            results = []

        # Aggregate by domain to reduce noise while preserving engine diversity
        aggregated: dict[str, dict[str, Any]] = {}
        for entry in results:
            if not isinstance(entry, dict):
                continue
            url = str(entry.get("url", "")).strip()
            if not url or ".onion" not in url.lower():
                continue
            
            domain = self._extract_onion_domain(url)
            if not domain:
                continue
                
            source_engine = str(entry.get("engine") or entry.get("source") or "onionsearch").strip().lower()
            snippet = str(entry.get("snippet", "")).strip()

            if domain not in aggregated:
                aggregated[domain] = {
                    "url": url,
                    "domain": domain,
                    "engines": {source_engine},
                    "snippet": snippet,
                }
            else:
                aggregated[domain]["engines"].add(source_engine)
                # Keep the longest snippet for better intelligence
                if len(snippet) > len(str(aggregated[domain].get("snippet", ""))):
                    aggregated[domain]["snippet"] = snippet

        for domain, item in aggregated.items():
            try:
                record = DiscoveryRegistry.model_validate(
                    {
                        "discovered_domain": domain,
                        "intel_source": "tor",
                        "timestamp": datetime.now(UTC),
                        "onion_url": item["url"],
                        "source_engine": ",".join(sorted(item["engines"])),
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
                    confidence=0.82,
                    severity=Severity.MEDIUM,
                    raw_evidence={
                        "onion_domain": record.discovered_domain,
                        "source_engines": sorted(item["engines"]),
                        "snippet": item.get("snippet"),
                        "discovery_registry": record.model_dump(mode="json"),
                    },
                )
            )

        # Trigger V-RAD Telemetry for deep web site identification
        if findings:
            self._emit_telemetry(
                "V-RAD_EVENT",
                "Deep Web Pulse",
                payload={
                    "v-rad_color": "DARK_PURPLE_BLACK",
                    "site_count": len(findings),
                    "summary": f"OnionSearch aggregated {len(findings)} darknet nodes for {target}"
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

    def execute(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        """
        Executes OnionSearch with Sovereign Network Layer enforcement.
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

        # Ensure proxy is passed to build_command
        opts["tor_proxy"] = policy["tor_proxy"]
        
        # Live execution
        result = super().execute(target, opts, mission_id=mission_id)
        
        # Enrich context
        enriched_context = dict(result.target_context)
        enriched_context["snl_interface"] = policy.get("snl_interface")
        enriched_context["tor_proxy"] = policy.get("tor_proxy")
        enriched_context["telemetry"] = self.get_telemetry_events()
        
        return result.model_copy(update={"target_context": enriched_context})
