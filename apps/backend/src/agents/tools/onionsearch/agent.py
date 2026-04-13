from __future__ import annotations

from datetime import UTC, datetime
import json
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


_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}
_REQUIRED_TOR_PROXY = "127.0.0.1:9050"


class OnionsearchAgent(BaseToolAgent):
    TOOL_NAME = "onionsearch"

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
        engines = opts.get("engines")
        if isinstance(engines, list) and engines:
            engine_arg = ",".join(str(e).strip() for e in engines if str(e).strip())
        else:
            engine_arg = "ahmia,darksearch,phobos,haystak"
        return [
            "onionsearch",
            target,
            "--proxy",
            str(opts.get("tor_proxy", _REQUIRED_TOR_PROXY)),
            "--engines",
            engine_arg,
            "--output",
            f"{artifact_dir}/onionsearch.json",
        ]

    @staticmethod
    def _extract_onion_domain(url: str) -> str:
        parsed = urlparse(url.strip())
        return (parsed.netloc or "").lower()

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_output = raw_output.strip()
        if not raw_output:
            return findings

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            data = {}

        results = data.get("results", []) if isinstance(data, dict) else []
        if not isinstance(results, list):
            return findings

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

            has_credential = any(
                pattern in str(item.get("snippet", "")).lower()
                for pattern in ["password", "leaked", "credentials", "breach", "dump"]
            )

            findings.append(
                {
                    "type": "dark_web_search_result",
                    "value": record.onion_url or f"http://{record.discovered_domain}",
                    "target": target,
                    "severity": "high" if has_credential else "medium",
                    "confidence": 0.82,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(
                        {
                            "onion_domain": record.discovered_domain,
                            "source_engines": sorted(item["engines"]),
                            "credential_keywords": has_credential,
                        },
                        ensure_ascii=True,
                    ),
                    "context": {
                        "has_credential_keywords": has_credential,
                        "source_engines": sorted(item["engines"]),
                        "discovery_registry": record.model_dump(mode="json"),
                        "intel_source": "TOR",
                        "snl_mode": "fixture_only",
                    },
                    "recommended_next_tools": ["torbot", "ahmia-client", "EvidenceAnalystAgent"],
                    "recommended_next_actions": ["investigate_onion_source"],
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
            if f"{str(finding.get('target', '')).lower()}|dark_web_search_result|{value}" in known:
                noise.append(finding)
                continue
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        engines = sorted(
            {
                engine
                for finding in signal
                for engine in finding.get("context", {}).get("source_engines", [])
            }
        )
        return {
            "next_agents": ["torbot", "ahmia-client", "EvidenceAnalystAgent"],
            "high_value_results": len([f for f in signal if f.get("severity") == "high"]),
            "total_results": len(signal),
            "engines_aggregated": engines,
            "operator_summary": (
                f"Onionsearch aggregated {len(signal)} .onion findings for {target} across {len(engines)} engines."
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
            command=["fixture://onionsearch"],
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

        self._emit_telemetry("AGENT_STATUS", "ONIONSEARCH_AGGREGATION")
        self._emit_telemetry("TOR_ONION_DISCOVERIES", len(result.findings))
        if result.findings:
            self._emit_telemetry("EventLog", "DEEP_WEB_PULSE_DARK_PURPLE_BLACK")

        context = dict(result.target_context)
        context.update(
            {
                "mode": "stub_fixture",
                "snl_interface": policy["snl_interface"],
                "tor_proxy": policy["tor_proxy"],
                "telemetry": self.get_telemetry_events(),
            }
        )
        return result.model_copy(update={"target_context": context})
