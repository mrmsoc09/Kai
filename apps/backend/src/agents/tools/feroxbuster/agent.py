from __future__ import annotations

import asyncio
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


_HIGH_VALUE_PATH_TOKENS = {
    "/admin",
    "/api",
    "/internal",
    "/backup",
    "/config",
    "/.git",
    "/swagger",
    "/actuator",
    "/debug",
    "/dev",
    "/test",
    "/staging",
    "/graphql",
    "/v1",
    "/v2",
    "/v3",
}
_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}
_DEFAULT_WORDLISTS = {
    "php": "wordlists/content/php-directories.txt",
    "js": "wordlists/content/js-endpoints.txt",
    "api": "wordlists/content/api-routes.txt",
    "default": "wordlists/content/common-directories.txt",
}


class FeroxbusterAgent(BaseToolAgent):
    TOOL_NAME = "feroxbuster"

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

    @staticmethod
    def _select_wordlist(options: dict[str, Any]) -> str:
        tech_hint = str(options.get("tech_hint", "default")).strip().lower()
        overrides = options.get("wordlist_overrides")
        if isinstance(overrides, dict):
            for key in (tech_hint, "default"):
                value = overrides.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return _DEFAULT_WORDLISTS.get(tech_hint, _DEFAULT_WORDLISTS["default"])

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        output_path = f"{artifact_dir}/feroxbuster.json"
        wordlist = str(opts.get("wordlist") or self._select_wordlist(opts))
        base_threads = min(int(opts.get("rate_limit", 10)) * 2, 20)
        waf_detected = bool(opts.get("waf_detected", False))
        recursive = bool(opts.get("recursive", True))

        cmd = [
            "feroxbuster",
            "--url",
            target,
            "--wordlist",
            wordlist,
            "--silent",
            "--json",
            "--output",
            output_path,
            "--depth",
            str(opts.get("depth", 3)),
            "--threads",
            str(5 if waf_detected else base_threads),
            "--filter-status",
            "404,429,503",
            "--timeout",
            str(opts.get("timeout", 10)),
        ]
        if not recursive:
            cmd.append("--no-recursion")
        if waf_detected:
            cmd.extend(["--rate-limit", str(opts.get("waf_rate_limit", 2))])
        return cmd

    def _extract_entries(self, fixture: str | dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []

        def _add(entry: dict[str, Any]) -> None:
            if isinstance(entry, dict) and entry.get("url"):
                entries.append(entry)

        if isinstance(fixture, dict):
            results = fixture.get("results")
            if isinstance(results, list):
                for item in results:
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
            url = str(entry.get("url", "")).strip()
            if not url:
                continue
            status = int(entry.get("status", 0) or 0)
            content_length = int(entry.get("content_length", 0) or 0)
            depth = int(entry.get("depth", 0) or 0)
            is_js = url.lower().endswith(".js")

            try:
                crawl_record = CrawlRegistry.model_validate(
                    {
                        "crawl_url": url,
                        "discovered_from": self.TOOL_NAME,
                        "depth": depth,
                        "asset_type": "js_asset" if is_js else "url",
                        "is_javascript": is_js,
                        "timestamp": datetime.now(UTC),
                    }
                )
            except Exception:
                continue

            is_high = any(token in url.lower() for token in _HIGH_VALUE_PATH_TOKENS)
            severity = "medium" if is_high else "info"
            confidence = 0.85 if is_high else 0.6
            if status in {401, 403}:
                severity = "low" if not is_high else severity
                confidence = max(confidence, 0.75)

            findings.append(
                {
                    "type": "url",
                    "value": url,
                    "target": target,
                    "severity": severity,
                    "confidence": confidence,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(entry, ensure_ascii=True)[:1000],
                    "context": {
                        "status_code": status,
                        "content_length": content_length,
                        "depth": depth,
                        "crawl_registry": crawl_record.model_dump(mode="json"),
                        "snl_mode": "fixture_only",
                    },
                    "recommended_next_tools": ["paramspider", "dalfox", "sqlmap"],
                    "recommended_next_actions": ["probe_endpoint", "parameter_discovery"],
                }
            )
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()
        seen_lengths: dict[int, int] = {}

        for finding in findings:
            value = str(finding.get("value", "")).lower()
            if f"{str(finding.get('target', '')).lower()}|url|{value}" in known:
                noise.append(finding)
                continue

            status = int(finding.get("context", {}).get("status_code", 0) or 0)
            content_length = int(finding.get("context", {}).get("content_length", -1) or -1)

            if content_length >= 0:
                seen_lengths[content_length] = seen_lengths.get(content_length, 0) + 1
                if seen_lengths[content_length] > 3:
                    noise.append(finding)
                    continue

            if status == 404:
                noise.append(finding)
            else:
                signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        admin_paths = [
            f["value"]
            for f in signal
            if "/admin" in str(f.get("value", "")).lower() or "/internal" in str(f.get("value", "")).lower()
        ]
        api_paths = [
            f["value"]
            for f in signal
            if any(t in str(f.get("value", "")).lower() for t in ["/api", "/v1", "/v2", "/v3"])
        ]

        return {
            "next_agents": ["paramspider", "dalfox", "sqlmap"],
            "admin_paths": admin_paths,
            "api_paths": api_paths,
            "all_paths_count": len(signal),
            "operator_summary": (
                f"Ferox discovered {len(signal)} paths on {target}. "
                f"Admin/internal: {len(admin_paths)}. API/versioned paths: {len(api_paths)}."
            ),
        }

    async def execute_async(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        opts = dict(options or {})
        shards = opts.get("fixture_shards")
        if not isinstance(shards, list) or not shards:
            return self.execute(target, opts, mission_id=mission_id)

        async def _to_text(fragment: Any) -> str:
            if isinstance(fragment, str):
                return fragment
            return json.dumps(fragment)

        texts = await asyncio.gather(*[_to_text(fragment) for fragment in shards])
        opts["fixture_data"] = "\n".join(texts)
        return self.execute(target, opts, mission_id=mission_id)

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
            command=["fixture://feroxbuster"],
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

        self._emit_telemetry("AGENT_STATUS", "ENUMERATING_CONTENT")
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


class FeroxAgent(FeroxbusterAgent):
    """Alias for architecture briefs."""
