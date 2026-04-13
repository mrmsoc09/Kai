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
from ..content_discovery_schemas import CrawlRegistry


_STATIC_EXTENSIONS = {
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".svg",
}
_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}


class KatanaAgent(BaseToolAgent):
    TOOL_NAME = "katana"

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
        output_path = f"{artifact_dir}/katana.json"
        headless = bool(opts.get("headless", True))
        cmd = [
            "katana",
            "-u",
            target,
            "-jc",
            "-kf",
            "all",
            "-d",
            str(opts.get("depth", 5)),
            "-json",
            "-o",
            output_path,
            "-timeout",
            str(opts.get("timeout", 10)),
            "-rate-limit",
            str(opts.get("rate_limit", 10)),
        ]
        if headless:
            cmd.append("-headless")
        return cmd

    def _extract_entries(self, fixture: str | dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []

        def _add(entry: dict[str, Any]) -> None:
            endpoint = entry.get("endpoint") or entry.get("url")
            if endpoint:
                entries.append(entry)

        if isinstance(fixture, dict):
            payload = fixture.get("results")
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        _add(item)
            else:
                _add(fixture)
            return entries

        if isinstance(fixture, list):
            for item in fixture:
                if isinstance(item, dict):
                    _add(item)
            return entries

        for line in str(fixture).strip().splitlines():
            token = line.strip()
            if not token:
                continue
            try:
                payload = json.loads(token)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                _add(payload)

        return entries

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for entry in self._extract_entries(raw_output):
            endpoint = str(entry.get("endpoint") or entry.get("url") or "").strip()
            if not endpoint:
                continue
            is_graphql = "graphql" in endpoint.lower()
            is_js = endpoint.lower().endswith(".js")
            depth = int(entry.get("depth", 0) or 0)

            try:
                crawl_registry = CrawlRegistry.model_validate(
                    {
                        "crawl_url": endpoint,
                        "discovered_from": self.TOOL_NAME,
                        "depth": depth,
                        "asset_type": "js_asset" if is_js else "url",
                        "is_javascript": is_js,
                        "timestamp": datetime.now(UTC),
                    }
                )
            except Exception:
                continue

            findings.append(
                {
                    "type": "url",
                    "value": endpoint,
                    "target": target,
                    "severity": "medium" if is_graphql else "info",
                    "confidence": 0.8,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(entry, ensure_ascii=True)[:1000],
                    "context": {
                        "source": entry.get("source", ""),
                        "is_graphql": is_graphql,
                        "tag": entry.get("tag", ""),
                        "depth": depth,
                        "crawl_registry": crawl_registry.model_dump(mode="json"),
                        "snl_mode": "fixture_only",
                    },
                    "recommended_next_tools": ["paramspider", "dalfox", "sqlmap"],
                    "recommended_next_actions": ["parameter_discovery", "vulnerability_scan"],
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
            if f"{str(finding.get('target', '')).lower()}|url|{value}" in known:
                noise.append(finding)
                continue

            if bool(finding.get("context", {}).get("is_graphql")):
                finding["severity"] = "medium"
                signal.append(finding)
                continue
            if any(value.endswith(ext) for ext in _STATIC_EXTENSIONS):
                noise.append(finding)
                continue
            if value.endswith(".js"):
                finding["severity"] = "low"
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        graphql_endpoints = [f["value"] for f in signal if bool(f.get("context", {}).get("is_graphql"))]
        js_files = [f["value"] for f in signal if str(f.get("value", "")).lower().endswith(".js")]

        return {
            "next_agents": ["paramspider", "dalfox", "sqlmap", "EvidenceAnalystAgent"],
            "graphql_endpoints": graphql_endpoints,
            "js_files": js_files,
            "graphql_detected": len(graphql_endpoints) > 0,
            "operator_summary": (
                f"Katana crawled {target} and produced {len(signal)} endpoints. "
                f"GraphQL endpoints: {len(graphql_endpoints)}. JS assets: {len(js_files)}."
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
            command=["fixture://katana"],
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

        max_depth = 0
        for finding in result.findings:
            depth = int(finding.raw_evidence.get("context", {}).get("depth", 0) or 0)
            max_depth = max(max_depth, depth)

        self._emit_telemetry("AGENT_STATUS", "CRAWLING")
        self._emit_telemetry("CRAWL_DEPTH", max_depth)
        if result.findings:
            self._emit_telemetry("EventLog", "SPIDER_WEB_EXPANSION")

        context = dict(result.target_context)
        context.update(
            {
                "mode": "stub_fixture",
                "snl_interface": policy["snl_interface"],
                "telemetry": self.get_telemetry_events(),
            }
        )
        return result.model_copy(update={"target_context": context})
