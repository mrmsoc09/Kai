from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
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


_STATIC_EXTENSIONS = {".css", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf"}
_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}
_MAX_RPS_CAP = 50


class HakrawlerAgent(BaseToolAgent):
    TOOL_NAME = "hakrawler"

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
        rps = self._normalize_rps(opts)
        delay = round(1.0 / float(rps), 3)
        return [
            "hakrawler",
            "-url",
            target,
            "-depth",
            str(opts.get("depth", 3)),
            "-plain",
            "-delay",
            str(delay),
            "-h",
            "User-Agent: Mozilla/5.0 (Kaison-Hakrawler)",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

        for line in raw_output.strip().splitlines():
            value = line.strip()
            if not value:
                continue

            if value.startswith("http://") or value.startswith("https://"):
                lower = value.lower()
                is_api = "/api/" in lower
                is_js = lower.endswith(".js")
                is_form = "form" in lower or "action=" in lower
                severity = "medium" if (is_api or is_form) else ("low" if is_js else "info")

                try:
                    crawl_registry = CrawlRegistry.model_validate(
                        {
                            "crawl_url": value,
                            "discovered_from": self.TOOL_NAME,
                            "depth": 1,
                            "asset_type": "js_asset" if is_js else "url",
                            "is_javascript": is_js,
                            "timestamp": datetime.now(UTC),
                        }
                    )
                    parsed = urlparse(value)
                    endpoint_path = parsed.path or "/"
                    web_registry = WebDiscoveryRegistry.model_validate(
                        {
                            "endpoint_url": value,
                            "endpoint_path": endpoint_path,
                            "source_tool": self.TOOL_NAME,
                            "discovered_at": datetime.now(UTC),
                        }
                    )
                except Exception:
                    continue

                findings.append(
                    {
                        "type": "url",
                        "value": value,
                        "target": target,
                        "severity": severity,
                        "confidence": 0.78,
                        "source_tool": self.TOOL_NAME,
                        "raw_evidence": value[:1000],
                        "context": {
                            "is_api": is_api,
                            "is_js": is_js,
                            "is_form_action": is_form,
                            "crawl_registry": crawl_registry.model_dump(mode="json"),
                            "web_discovery_registry": web_registry.model_dump(mode="json"),
                            "snl_mode": "fixture_only",
                        },
                        "recommended_next_tools": ["ffuf", "gau", "dalfox"],
                        "recommended_next_actions": ["content_discovery", "historical_url_mining"],
                    }
                )
                continue

            for email in email_pattern.findall(value):
                findings.append(
                    {
                        "type": "email",
                        "value": email,
                        "target": target,
                        "severity": "info",
                        "confidence": 0.6,
                        "source_tool": self.TOOL_NAME,
                        "raw_evidence": value[:500],
                        "context": {"is_email": True, "snl_mode": "fixture_only"},
                        "recommended_next_tools": ["sherlock", "social-analyzer"],
                        "recommended_next_actions": ["osint_enrichment"],
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
            ftype = str(finding.get("type", "url"))
            if f"{str(finding.get('target', '')).lower()}|{ftype}|{value}" in known:
                noise.append(finding)
                continue

            if ftype == "url":
                parsed = urlparse(str(finding.get("value", "")))
                target_host = str(finding.get("target", "")).strip().lower()
                parsed_host = parsed.netloc.lower()
                if target_host and parsed_host and not (
                    parsed_host == target_host or parsed_host.endswith(f".{target_host}")
                ):
                    noise.append(finding)
                    continue

                if any(value.endswith(ext) for ext in _STATIC_EXTENSIONS):
                    noise.append(finding)
                    continue

                signal.append(finding)
            else:
                signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        new_urls = [f["value"] for f in signal if str(f.get("value", "")).startswith(("http://", "https://"))]
        form_actions = [f["value"] for f in signal if bool(f.get("context", {}).get("is_form_action"))]

        return {
            "next_agents": ["ffuf", "gau", "dalfox"],
            "new_urls": new_urls,
            "form_actions": form_actions,
            "operator_summary": (
                f"Hakrawler identified {len(new_urls)} in-scope URLs for {target} and "
                f"{len(form_actions)} form-action candidates."
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
            command=["fixture://hakrawler"],
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

        self._emit_telemetry("AGENT_STATUS", "CRAWLING")
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
