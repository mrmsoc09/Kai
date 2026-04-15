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
from ..content_discovery_schemas import CrawlRegistry, WebDiscoveryRegistry


_HIGH_VALUE_EXTENSIONS = {
    ".php", ".asp", ".aspx", ".jsp", ".json", ".xml",
    ".config", ".bak", ".sql", ".log", ".env", ".key",
    ".pem", ".yaml", ".yml",
}
_HIGH_SIGNAL_PATHS = {
    "/admin", "/api/", "/internal", "/debug", "/test",
    "/dev", "/.git", "/.env", "/config", "/backup",
    "/graphql", "/swagger", "/openapi", "/console",
    "/mgmt", "/management", "/v1/", "/v2/", "/v3/",
}
_INJECTION_PARAMS = {
    "id", "file", "url", "path", "user", "redirect",
    "return", "next", "target", "src", "dest", "destination",
    "page", "action", "cmd", "command", "exec", "query",
    "search", "q", "input", "data", "load", "include",
}
_NOISE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".eot"}
_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}
_MAX_RPS_CAP = 50


class GauAgent(BaseToolAgent):
    TOOL_NAME = "gau"

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

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        cmd = ["gau", target, "--subs"]
        if opts.get("providers"):
            cmd += ["--providers", ",".join(opts["providers"])]
        timeout = int(opts.get("timeout", opts.get("timeout_seconds", 900)))
        cmd += ["--timeout", str(timeout)]
        return cmd

    @staticmethod
    def _iter_lines(raw_output: str) -> list[str]:
        lines: list[str] = []
        for line in raw_output.splitlines():
            token = line.strip()
            if not token:
                continue
            if token.startswith("{"):
                try:
                    payload = json.loads(token)
                except json.JSONDecodeError:
                    payload = None
                if isinstance(payload, dict) and isinstance(payload.get("url"), str):
                    lines.append(payload["url"])
                    continue
            lines.append(token)
        return lines

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for url in self._iter_lines(raw_output):
            if not url.startswith(("http://", "https://")):
                continue

            parsed = urlparse(url)
            host = parsed.netloc.lower()
            target_host = str(target).strip().lower()
            if target_host and not (host == target_host or host.endswith(f".{target_host}")):
                continue

            path = parsed.path or "/"
            params: list[str] = []
            if parsed.query:
                for chunk in parsed.query.split("&"):
                    if "=" in chunk:
                        key = chunk.split("=", 1)[0].strip()
                        if key:
                            params.append(key)

            ext = ""
            if "." in path.split("/")[-1]:
                ext = "." + path.rsplit(".", 1)[-1].lower()

            try:
                crawl_registry = CrawlRegistry.model_validate(
                    {
                        "crawl_url": url,
                        "discovered_from": self.TOOL_NAME,
                        "depth": 0,
                        "asset_type": "archive_url",
                        "is_javascript": ext == ".js",
                        "timestamp": datetime.now(UTC),
                    }
                )
                web_registry = WebDiscoveryRegistry.model_validate(
                    {
                        "endpoint_url": url,
                        "endpoint_path": path,
                        "source_tool": self.TOOL_NAME,
                        "discovered_at": datetime.now(UTC),
                    }
                )
            except Exception:
                continue

            finding = {
                "type": "url",
                "url": url,
                "value": url,
                "target": target,
                "severity": "info",
                "confidence": 0.82,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": url[:1000],
                "context": {
                    "path": path,
                    "extension": ext,
                    "parameters": params,
                    "crawl_registry": crawl_registry.model_dump(mode="json"),
                    "web_discovery_registry": web_registry.model_dump(mode="json"),
                    "snl_mode": "fixture_only",
                },
                "recommended_next_tools": ["arjun", "dalfox", "ffuf"],
                "recommended_next_actions": ["extract_parameters", "probe_live_candidates"],
            }
            findings.append(finding)

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()
        seen_urls: set[str] = set()

        for item in findings:
            url = str(item.get("url", "")).strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            value = str(item.get("value", "")).lower()
            if f"{str(item.get('target', '')).lower()}|url|{value}" in known:
                noise.append(item)
                continue

            path = str(item.get("context", {}).get("path", "")).lower()
            ext = str(item.get("context", {}).get("extension", "")).lower()
            params = item.get("context", {}).get("parameters", [])
            if not isinstance(params, list):
                params = []

            if ext in _NOISE_EXTENSIONS:
                item["noise_reason"] = "static_asset"
                noise.append(item)
                continue

            if any(path.startswith(p) for p in _HIGH_SIGNAL_PATHS):
                item["signal_reason"] = "high_signal_path"
                item["severity"] = "medium"
                signal.append(item)
                continue

            injection_params = [p for p in params if str(p).lower() in _INJECTION_PARAMS]
            if injection_params:
                item["signal_reason"] = "injection_parameter"
                item["severity"] = "medium"
                item["context"]["injection_params"] = injection_params
                signal.append(item)
                continue

            if ext in _HIGH_VALUE_EXTENSIONS:
                item["signal_reason"] = "high_value_extension"
                item["severity"] = "medium"
                signal.append(item)
                continue

            if not params:
                item["noise_reason"] = "no_parameters_plain_path"
                noise.append(item)
                continue

            signal.append(item)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        injection_urls = [s["url"] for s in signal if s.get("signal_reason") == "injection_parameter"]
        high_signal_paths = [s["url"] for s in signal if s.get("signal_reason") == "high_signal_path"]
        all_params = sorted({p for s in signal for p in s.get("context", {}).get("parameters", []) if isinstance(p, str)})

        return {
            "next_agents": ["arjun", "dalfox", "ffuf"],
            "priority_urls": injection_urls[:20],
            "high_signal_paths": high_signal_paths[:20],
            "discovered_parameter_names": all_params[:50],
            "total_signal_urls": len(signal),
            "instructions": (
                f"Found {len(signal)} signal URLs. {len(injection_urls)} include injection-candidate parameters."
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
            command=["fixture://gau"],
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

        self._emit_telemetry("AGENT_STATUS", "ARCHIVE_MINING")
        self._emit_telemetry("FUZZ_STREAM", len(result.findings))

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
