from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from apps.backend.src.core.protocol import KaisonResult, KaisonResultMetadata
from apps.backend.src.core.scope_guardrails import (
    audit_scope_decision,
    evaluate_target_scope,
    load_scope_policy,
)

from ..base_tool_agent import BaseToolAgent
from ..content_discovery_schemas import ParameterRegistry


_HIGH_VALUE_PARAMS = {
    "id",
    "file",
    "url",
    "path",
    "redirect",
    "next",
    "return",
    "callback",
    "load",
    "fetch",
    "include",
}

_STATIC_SUFFIXES = {
    ".css",
    ".js",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
}
_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}


class ParamspiderAgent(BaseToolAgent):
    TOOL_NAME = "paramspider"

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
        output_path = f"{artifact_dir}/paramspider.txt"
        return ["paramspider", "-d", target, "-o", output_path]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.strip().splitlines():
            url = line.strip()
            if not url or "?" not in url:
                continue

            parsed = urlparse(url)
            param_names = sorted(parse_qs(parsed.query, keep_blank_values=True).keys())
            if not param_names:
                continue

            param_registry_records: list[dict[str, Any]] = []
            for param_name in param_names:
                try:
                    param_record = ParameterRegistry.model_validate(
                        {
                            "endpoint_url": url,
                            "parameter_name": param_name,
                            "source": self.TOOL_NAME,
                            "timestamp": datetime.now(UTC),
                        }
                    )
                except Exception:
                    continue
                param_registry_records.append(param_record.model_dump(mode="json"))

            if not param_registry_records:
                continue

            has_high = any(name.lower() in _HIGH_VALUE_PARAMS for name in param_names)
            findings.append(
                {
                    "type": "url",
                    "value": url,
                    "target": target,
                    "severity": "medium" if has_high else "info",
                    "confidence": 0.85 if has_high else 0.7,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": url[:1000],
                    "context": {
                        "parameter_names": param_names,
                        "parameter_registry": param_registry_records,
                        "host": parsed.netloc,
                        "path": parsed.path,
                        "snl_mode": "fixture_only",
                    },
                    "recommended_next_tools": ["dalfox", "sqlmap", "ssrfmap"],
                    "recommended_next_actions": ["xss_probe", "sqli_probe", "ssrf_probe"],
                }
            )
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()
        seen_param_sets: set[tuple[str, ...]] = set()

        for finding in findings:
            value = str(finding.get("value", "")).lower()
            if f"{str(finding.get('target', '')).lower()}|url|{value}" in known:
                noise.append(finding)
                continue

            if any(value.endswith(ext) for ext in _STATIC_SUFFIXES):
                noise.append(finding)
                continue

            params = tuple(sorted(str(p).lower() for p in finding.get("context", {}).get("parameter_names", [])))
            if not params or params in seen_param_sets:
                noise.append(finding)
                continue
            seen_param_sets.add(params)
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        unique_params = sorted(
            {
                str(param).lower()
                for finding in signal
                for param in finding.get("context", {}).get("parameter_names", [])
                if str(param).strip()
            }
        )

        potential_sqli = [p for p in unique_params if p in {"id", "uid", "account", "order", "product", "item"}]
        potential_xss = [p for p in unique_params if p in {"q", "query", "search", "callback", "return", "next"}]
        potential_ssrf = [p for p in unique_params if p in {"url", "uri", "path", "dest", "redirect", "load", "fetch", "include"}]

        return {
            "next_agents": ["dalfox", "sqlmap", "ssrfmap"],
            "param_list": unique_params,
            "potential_sqli": potential_sqli,
            "potential_xss": potential_xss,
            "potential_ssrf": potential_ssrf,
            "operator_summary": (
                f"Paramspider found {len(signal)} parameterized URLs for {target} with "
                f"{len(unique_params)} unique parameter names."
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

        fixture_text = fixture if isinstance(fixture, str) else "\n".join(str(x) for x in fixture)
        ended_at = datetime.now(UTC)
        runtime_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))
        result = self.map_output(
            target=target,
            command=["fixture://paramspider"],
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

        param_count = 0
        for finding in result.findings:
            params = finding.raw_evidence.get("context", {}).get("parameter_names", [])
            if isinstance(params, list):
                param_count += len(params)

        self._emit_telemetry("AGENT_STATUS", "MINING_PARAMETERS")
        self._emit_telemetry("PARAMS_IDENTIFIED", param_count)
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


class ParamSpiderAgent(ParamspiderAgent):
    """Alias for architecture briefs."""
