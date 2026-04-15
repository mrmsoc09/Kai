from __future__ import annotations

import json
from datetime import UTC, datetime
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
from ..osint_schemas import IdentityRegistry


_HIGH_VALUE_PLATFORMS = {"github", "linkedin", "hackerone"}
_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}


class SherlockAgent(BaseToolAgent):
    """Fixture-driven architectural stub for social-handle discovery."""

    TOOL_NAME = "sherlock"

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
        username = str(opts.get("username", target.split(".")[0]))
        return ["sherlock", username, "--print-found", "--json"]

    @staticmethod
    def _extract_identity_from_url(url: str, fallback_platform: str = "unknown") -> IdentityRegistry | None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None

        handle = parsed.path.strip("/").split("/")[0] if parsed.path.strip("/") else ""
        if not handle:
            return None

        host = parsed.netloc.lower()
        platform = fallback_platform
        if platform == "unknown":
            platform = host.split(".")[0]
            if platform in {"www", "m", "mobile"}:
                platform = host.split(".")[1] if len(host.split(".")) > 1 else "unknown"

        try:
            return IdentityRegistry.model_validate(
                {
                    "social_handle": handle,
                    "platform_detected": platform,
                    "profile_url": url,
                }
            )
        except Exception:
            return None

    def ingest_fixture(
        self,
        fixture: str | dict[str, Any] | list[Any],
        *,
        target: str,
        options: dict[str, Any] | None = None,
    ) -> list[IdentityRegistry]:
        policy = self.check_policy(target, options)
        if not policy["allowed"]:
            raise PermissionError(f"target blocked by scope policy: {policy['reason']}")

        records: list[IdentityRegistry] = []
        for platform, url in self._extract_profiles(fixture):
            registry = self._extract_identity_from_url(url, fallback_platform=platform)
            if registry is not None:
                records.append(registry)

        self._emit_telemetry("AGENT_STATUS", "IDENTIFYING_PROFILES")
        self._emit_telemetry("IDENTITY_PROFILES_FOUND", len(records))
        if records:
            self._emit_telemetry("EventLog", "PROFILE_PULSE")
        return records

    def _extract_profiles(self, fixture: str | dict[str, Any] | list[Any]) -> list[tuple[str, str]]:
        results: list[tuple[str, str]] = []

        def _add(platform: Any, url: Any) -> None:
            platform_value = str(platform or "unknown").strip().lower() or "unknown"
            url_value = str(url or "").strip()
            if url_value:
                results.append((platform_value, url_value))

        if isinstance(fixture, dict):
            profiles = fixture.get("profiles")
            if isinstance(profiles, list):
                for profile in profiles:
                    if isinstance(profile, dict):
                        _add(profile.get("platform"), profile.get("url"))
            else:
                _add(fixture.get("platform"), fixture.get("url"))
            return results

        if isinstance(fixture, list):
            for item in fixture:
                if isinstance(item, dict):
                    _add(item.get("platform"), item.get("url"))
                else:
                    _add("unknown", item)
            return results

        for line in str(fixture).splitlines():
            token = line.strip()
            if not token:
                continue
            if token.startswith("{"):
                try:
                    payload = json.loads(token)
                except json.JSONDecodeError:
                    payload = None
                if isinstance(payload, dict):
                    _add(payload.get("platform"), payload.get("url"))
                    continue
            lower = token.lower()
            platform = "unknown"
            for candidate in ["github", "linkedin", "hackerone", "twitter", "reddit", "gitlab"]:
                if candidate in lower:
                    platform = candidate
                    break
            if "http" in token:
                _add(platform, token.split()[-1])

        return results

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for platform, url in self._extract_profiles(raw_output):
            registry = self._extract_identity_from_url(url, fallback_platform=platform)
            if registry is None:
                continue

            high = registry.platform_detected in _HIGH_VALUE_PLATFORMS
            findings.append(
                {
                    "type": "osint_finding",
                    "value": registry.profile_url,
                    "target": target,
                    "severity": "medium" if high else "info",
                    "confidence": 0.85 if high else 0.7,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": url,
                    "context": {
                        "kind": "social_profile",
                        "platform": registry.platform_detected,
                        "identity_registry": registry.model_dump(mode="json"),
                        "snl_mode": "fixture_only",
                    },
                    "recommended_next_tools": ["social-analyzer", "trufflehog"]
                    if registry.platform_detected == "github"
                    else ["social-analyzer"],
                    "recommended_next_actions": ["profile_enrichment"],
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
            if f"{str(finding.get('target', '')).lower()}|osint|{value}" in known:
                noise.append(finding)
                continue
            if "not found" in str(finding.get("raw_evidence", "")).lower():
                noise.append(finding)
            else:
                signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        github_profiles = [
            f["value"] for f in signal if str(f.get("context", {}).get("platform", "")) == "github"
        ]
        return {
            "next_agents": ["social-analyzer", "trufflehog"],
            "github_profiles": github_profiles,
            "operator_summary": (
                f"Sherlock fixture ingestion discovered {len(signal)} profile records for {target}. "
                f"Profile Pulse telemetry emitted; GitHub profiles: {len(github_profiles)}."
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
        fixture = opts.get("fixture_data")
        if fixture is None and isinstance(opts.get("fixture_path"), str):
            fixture = Path(opts["fixture_path"]).read_text(encoding="utf-8")

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

        records = self.ingest_fixture(fixture, target=target, options=opts)
        stdout = "\n".join(record.profile_url for record in records)
        ended_at = datetime.now(UTC)
        runtime_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))

        result = self.map_output(
            target=target,
            command=["fixture://sherlock"],
            stdout=stdout,
            stderr="",
            exit_code=0,
            started_at=started_at,
            ended_at=ended_at,
            runtime_ms=runtime_ms,
            mission_id=mission_id,
            status="success",
            options=opts,
        )

        context = dict(result.target_context)
        context.update(
            {
                "mode": "stub_fixture",
                "normalized_records": [record.model_dump(mode="json") for record in records],
                "snl_interface": policy["snl_interface"],
                "telemetry": self.get_telemetry_events(),
            }
        )
        return result.model_copy(update={"target_context": context})
