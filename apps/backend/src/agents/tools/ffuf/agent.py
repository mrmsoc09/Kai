from __future__ import annotations

import asyncio
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
from ..content_discovery_schemas import CrawlRegistry, WebDiscoveryRegistry


_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}
_MAX_RPS_CAP = 50
def _resolve_wordlist(key: str) -> str:
    """Resolve a wordlist key via WordlistManager (SecLists) with legacy fallback."""
    try:
        from apps.backend.src.core.wordlist_manager import get_wordlist_manager
        wm = get_wordlist_manager()
        seclists_map = {
            "top1k":   "content/quickhits",
            "php":     "content/common",
            "js":      "content/common",
            "api":     "api/endpoints",
            "default": "content/dir-medium",
        }
        p = wm.get(seclists_map.get(key, "content/dir-medium"))
        if p:
            return str(p)
    except Exception:
        pass
    # Bundled relative paths as last resort
    _legacy = {
        "top1k": "wordlists/content/top-1k-discovery.txt",
        "php": "wordlists/content/php-files.txt",
        "js": "wordlists/content/js-files.txt",
        "api": "wordlists/content/api-routes.txt",
        "default": "wordlists/content/top-1k-discovery.txt",
    }
    return _legacy.get(key, _legacy["default"])


class FfufAgent(BaseToolAgent):
    TOOL_NAME = "ffuf"

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
    def _normalize_rps(options: dict[str, Any]) -> int:
        raw = options.get("max_requests_per_second", options.get("rate_limit", 5))
        try:
            rps = int(raw)
        except (TypeError, ValueError):
            rps = 5
        return max(1, min(_MAX_RPS_CAP, rps))

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
            "max_requests_per_second": self._normalize_rps(opts),
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
        output_path = f"{artifact_dir}/ffuf.json"
        waf_detected = bool(opts.get("waf_detected", False))
        threads = 5 if waf_detected else int(opts.get("threads", 20))
        rps = self._normalize_rps(opts)

        if bool(opts.get("vhost", False)):
            domain = str(opts.get("domain", target))
            return [
                "ffuf",
                "-u",
                target,
                "-H",
                f"Host: FUZZ.{domain}",
                "-w",
                str(opts.get("subdomain_wordlist", "wordlists/content/subdomains.txt")),
                "-mc",
                "200",
                "-o",
                output_path,
                "-of",
                "json",
                "-t",
                str(threads),
                "-rate",
                str(min(rps, 10)),
            ]

        recursive = bool(opts.get("recursive", True))
        cmd = [
            "ffuf",
            "-u",
            f"{target.rstrip('/')}/FUZZ",
            "-w",
            str(opts.get("wordlist") or self._select_wordlist(opts)),
            "-mc",
            "200,201,204,301,302,401,403",
            "-o",
            output_path,
            "-of",
            "json",
            "-t",
            str(threads),
            "-rate",
            str(min(rps, 20)),
            "-timeout",
            str(opts.get("timeout", 10)),
        ]
        if recursive:
            cmd.extend(["-recursion", "-recursion-depth", str(opts.get("depth", 2))])
        if waf_detected:
            cmd.extend(["-rate", str(opts.get("waf_rate", 2))])
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_output = raw_output.strip()
        if not raw_output:
            return findings

        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError:
            payload = {}

        results = payload.get("results", []) if isinstance(payload, dict) else []
        if not isinstance(results, list):
            return findings

        for entry in results:
            if not isinstance(entry, dict):
                continue
            url = str(entry.get("url", "")).strip()
            if not url:
                continue
            status = int(entry.get("status", 0) or 0)
            length = int(entry.get("length", 0) or 0)
            words = int(entry.get("words", 0) or 0)
            lines = int(entry.get("lines", 0) or 0)
            mode = "vhost" if "Host:" in str(entry.get("input", {})) else "endpoint"
            depth = int(entry.get("depth", 0) or 0)
            is_js = url.lower().endswith(".js")

            try:
                crawl_record = CrawlRegistry.model_validate(
                    {
                        "crawl_url": url,
                        "discovered_from": self.TOOL_NAME,
                        "depth": depth,
                        "asset_type": "js_asset" if is_js else mode,
                        "is_javascript": is_js,
                        "timestamp": datetime.now(UTC),
                    }
                )
            except Exception:
                continue
            try:
                parsed = urlparse(url)
                web_registry = WebDiscoveryRegistry.model_validate(
                    {
                        "endpoint_url": url,
                        "endpoint_path": parsed.path or "/",
                        "source_tool": self.TOOL_NAME,
                        "http_status": status if 100 <= status <= 599 else None,
                        "content_length": length if length >= 0 else None,
                        "discovered_at": datetime.now(UTC),
                    }
                )
            except Exception:
                continue

            findings.append(
                {
                    "type": mode,
                    "value": url,
                    "target": target,
                    "severity": "medium" if status in {401, 403} else "info",
                    "confidence": 0.8,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(entry, ensure_ascii=True)[:1000],
                    "context": {
                        "status_code": status,
                        "content_length": length,
                        "words": words,
                        "lines": lines,
                        "depth": depth,
                        "crawl_registry": crawl_record.model_dump(mode="json"),
                        "web_discovery_registry": web_registry.model_dump(mode="json"),
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
        clusters: dict[int, int] = {}

        for finding in findings:
            value = str(finding.get("value", "")).lower()
            ftype = str(finding.get("type", "url"))
            if f"{str(finding.get('target', '')).lower()}|{ftype}|{value}" in known:
                noise.append(finding)
                continue

            length = int(finding.get("context", {}).get("content_length", -1) or -1)
            if length >= 0:
                clusters[length] = clusters.get(length, 0) + 1
                if clusters[length] > 4:
                    noise.append(finding)
                    continue
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        discovered_paths = [f["value"] for f in signal]
        return {
            "next_agents": ["paramspider", "dalfox", "sqlmap"],
            "discovered_paths": discovered_paths,
            "operator_summary": (
                f"FFUF identified {len(discovered_paths)} actionable paths/vhosts for {target} "
                "after wildcard-length filtering."
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

        async def _ensure_results_fragment(fragment: Any) -> dict[str, Any]:
            if isinstance(fragment, dict) and isinstance(fragment.get("results"), list):
                return fragment
            if isinstance(fragment, list):
                return {"results": fragment}
            if isinstance(fragment, str):
                try:
                    payload = json.loads(fragment)
                except json.JSONDecodeError:
                    return {"results": []}
                if isinstance(payload, dict) and isinstance(payload.get("results"), list):
                    return payload
                if isinstance(payload, list):
                    return {"results": payload}
            return {"results": []}

        fragments = await asyncio.gather(*[_ensure_results_fragment(fragment) for fragment in shards])
        merged_results: list[dict[str, Any]] = []
        for fragment in fragments:
            merged_results.extend([item for item in fragment.get("results", []) if isinstance(item, dict)])
        opts["fixture_data"] = json.dumps({"results": merged_results})
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
            command=["fixture://ffuf"],
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
        self._emit_telemetry("FUZZ_STREAM", len(result.findings))
        self._emit_telemetry("CRAWL_DEPTH", max_depth)
        if result.findings:
            self._emit_telemetry("EventLog", "SPIDER_WEB_EXPANSION")

        context = dict(result.target_context)
        context.update(
            {
                "mode": "stub_fixture",
                "snl_interface": policy["snl_interface"],
                "max_requests_per_second": policy["max_requests_per_second"],
                "telemetry": self.get_telemetry_events(),
            }
        )
        return result.model_copy(update={"target_context": context})
