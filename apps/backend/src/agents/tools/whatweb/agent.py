from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from apps.backend.src.core.protocol import KaisonResult, KaisonResultMetadata
from apps.backend.src.core.scope_guardrails import (
    audit_scope_decision,
    evaluate_target_scope,
    load_scope_policy,
)

from ..base_tool_agent import BaseToolAgent
from ..network_fingerprint_schemas import TechStackRegistry


_NOISE_TECH = {"html5", "utf-8", "jquery", "javascript"}

_TEMPLATE_MAP = {
    "spring": ["spring-actuator", "spring-core-cves"],
    "wordpress": ["wordpress-cves", "wp-plugin-audit"],
    "apache": ["apache-httpd-cves", "apache-path-traversal"],
    "nginx": ["nginx-misconfig", "nginx-cves"],
    "iis": ["microsoft-iis", "aspnet-cves"],
}
_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}


class WhatwebAgent(BaseToolAgent):
    TOOL_NAME = "whatweb"

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
        output_file = opts.get("output_file", f"{opts.get('artifact_dir', '/tmp')}/whatweb.json")
        return [
            "whatweb",
            f"--log-json={output_file}",
            "--aggression",
            str(opts.get("aggression", 1)),
            "--open-timeout=30",
            "--read-timeout=60",
            target,
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            plugins = payload.get("plugins", {})
            if not isinstance(plugins, dict):
                continue

            for tech_name, details in plugins.items():
                if not isinstance(tech_name, str):
                    continue
                detail_text = ""
                version = ""
                if isinstance(details, dict):
                    strings = details.get("string")
                    versions = details.get("version")
                    if isinstance(strings, list):
                        detail_text = ", ".join(str(v) for v in strings[:5])
                    if isinstance(versions, list) and versions:
                        version = str(versions[0])

                category = self._categorize_technology(tech_name)
                try:
                    tech_registry = TechStackRegistry.model_validate(
                        {
                            "target": target,
                            "technology_name": tech_name,
                            "category": category,
                            "version": version or None,
                            "source": "whatweb",
                            "timestamp": datetime.now(UTC),
                        }
                    )
                except Exception:
                    continue

                value = tech_registry.technology_name if not tech_registry.version else f"{tech_registry.technology_name} {tech_registry.version}"
                findings.append(
                    {
                        "type": "technology_fingerprint",
                        "value": value,
                        "target": target,
                        "severity": "info",
                        "confidence": 0.85 if tech_registry.version else 0.7,
                        "source_tool": self.TOOL_NAME,
                        "raw_evidence": line,
                        "context": {
                            "technology_category": tech_registry.category,
                            "version": tech_registry.version or "",
                            "detail": detail_text,
                            "techstack_registry": tech_registry.model_dump(mode="json"),
                            "snl_mode": "fixture_only",
                        },
                        "recommended_next_tools": ["nuclei_scan"],
                        "recommended_next_actions": ["select_templates_by_stack", "correlate_versions_with_cves"],
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
            if f"{finding.get('target', '').lower()}|technology_fingerprint|{value}" in known:
                noise.append(finding)
                continue

            if any(token in value for token in _NOISE_TECH):
                finding["confidence"] = 0.4
                noise.append(finding)
                continue
            if str(finding.get("context", {}).get("version", "")).strip():
                finding["severity"] = "medium"
                finding["confidence"] = 0.92
            signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        detected = [str(item.get("value", "")).strip() for item in signal if str(item.get("value", "")).strip()]
        recommendations: list[str] = []
        for tech in detected:
            lowered = tech.lower()
            for token, templates in _TEMPLATE_MAP.items():
                if token in lowered:
                    recommendations.extend(templates)

        deduped_templates = sorted(set(recommendations))
        return {
            "next_agents": ["nuclei_scan"],
            "detected_technologies": detected,
            "template_recommendations": deduped_templates,
            "operator_summary": (
                f"WhatWeb fixture parsing fingerprinted {len(detected)} technologies for {target}. "
                f"Generated {len(deduped_templates)} template recommendations."
            ),
        }

    @staticmethod
    def _categorize_technology(name: str) -> str:
        token = name.lower()
        if "wordpress" in token or "drupal" in token or "joomla" in token:
            return "cms"
        if "apache" in token or "nginx" in token or "iis" in token or "server" in token:
            return "server"
        if "spring" in token or "rails" in token or "django" in token or "asp.net" in token:
            return "framework"
        if "jquery" in token or "react" in token or "vue" in token:
            return "javascript_library"
        if "waf" in token or "cloudflare" in token or "akamai" in token:
            return "waf_indicator"
        return "other"

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
            command=["fixture://whatweb"],
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

        self._emit_telemetry("AGENT_STATUS", "STACK_FINGERPRINTING")
        self._emit_telemetry("TECH_STACK_ITEMS", len(result.findings))

        context = dict(result.target_context)
        context.update(
            {
                "mode": "stub_fixture",
                "snl_interface": policy["snl_interface"],
                "telemetry": self.get_telemetry_events(),
            }
        )
        return result.model_copy(update={"target_context": context})
