from __future__ import annotations

from datetime import UTC, datetime
import json
import re
from pathlib import Path
from typing import Any, Callable

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
_DEFAULT_TOR_PROXY = "127.0.0.1:9050"
_ONION_URL_RE = re.compile(r"https?://[a-z2-7]{16,56}\.onion[^\s<\"]*", re.IGNORECASE)


class AhmiaClientAgent(BaseToolAgent):
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
        tor_proxy = str(opts.get("tor_proxy", _DEFAULT_TOR_PROXY)).strip()

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
            "tor_proxy": tor_proxy,
        }

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        return [
            "ahmia",
            "search",
            target,
            "--proxy",
            str(opts.get("tor_proxy", _DEFAULT_TOR_PROXY)),
            "--output",
            f"{artifact_dir}/ahmia.json",
        ]

    @staticmethod
    def _extract_domain(url: str) -> str:
        token = url.split("//", 1)[1] if "//" in url else url
        return token.split("/", 1)[0].strip().lower().rstrip(".")

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        if not raw_output.strip():
            return findings

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
                {
                    "type": "indexed_dark_web_result",
                    "value": record.onion_url or f"http://{record.discovered_domain}",
                    "target": target,
                    "severity": "medium",
                    "confidence": 0.75,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(
                        {
                            "onion_domain": record.discovered_domain,
                            "source_engine": record.source_engine,
                        },
                        ensure_ascii=True,
                    ),
                    "context": {
                        "discovery_registry": record.model_dump(mode="json"),
                        "intel_source": "TOR",
                        "snl_mode": "fixture_only",
                    },
                    "recommended_next_tools": ["torbot", "onionsearch", "EvidenceAnalystAgent"],
                    "recommended_next_actions": ["verify_onion_content"],
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
            if f"{str(finding.get('target', '')).lower()}|indexed_dark_web_result|{value}" in known:
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
            "next_agents": ["torbot", "onionsearch", "EvidenceAnalystAgent"],
            "indexed_onion_urls": len(signal),
            "operator_summary": (
                f"Ahmia indexed search returned {len(signal)} .onion URLs for {target}."
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
            command=["fixture://ahmia-client"],
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

        self._emit_telemetry("AGENT_STATUS", "AHMIA_INDEX_LOOKUP")
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


class AhmiaAgent(AhmiaClientAgent):
    """Alias class for architecture briefs."""

