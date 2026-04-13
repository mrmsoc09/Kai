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


_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}


class SocialAnalyzerAgent(BaseToolAgent):
    """Fixture-driven architectural stub for social profile enrichment."""

    TOOL_NAME = "social-analyzer"

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
        return ["social-analyzer", "--username", username, "--metadata", "--output", "json"]

    def _extract_profiles(self, fixture: str | dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
        profiles: list[dict[str, Any]] = []

        if isinstance(fixture, dict):
            payload = fixture.get("profiles")
            if isinstance(payload, list):
                for profile in payload:
                    if isinstance(profile, dict):
                        profiles.append(profile)
            else:
                profiles.append(fixture)
            return profiles

        if isinstance(fixture, list):
            for item in fixture:
                if isinstance(item, dict):
                    profiles.append(item)
            return profiles

        text = str(fixture).strip()
        if not text:
            return profiles

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = []

        if isinstance(payload, dict):
            data = payload.get("profiles")
            if isinstance(data, list):
                profiles.extend([p for p in data if isinstance(p, dict)])
            else:
                profiles.append(payload)
        elif isinstance(payload, list):
            profiles.extend([p for p in payload if isinstance(p, dict)])

        return profiles

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
        for profile in self._extract_profiles(fixture):
            fallback_handle = ""
            profile_url = str(profile.get("url") or "").strip()
            if profile_url:
                parsed_url = urlparse(profile_url)
                fallback_handle = parsed_url.path.strip("/").split("/")[0] if parsed_url.path else ""
            try:
                registry = IdentityRegistry.model_validate(
                    {
                        "social_handle": profile.get("handle")
                        or profile.get("username")
                        or profile.get("user")
                        or fallback_handle
                        or "",
                        "platform_detected": profile.get("platform") or "unknown",
                        "profile_url": profile_url,
                    }
                )
            except Exception:
                continue
            records.append(registry)

        self._emit_telemetry("AGENT_STATUS", "PROFILE_ENRICHMENT")
        self._emit_telemetry("IDENTITY_PROFILES_FOUND", len(records))
        if records:
            self._emit_telemetry("EventLog", "PROFILE_PULSE")
        return records

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for profile in self._extract_profiles(raw_output):
            fallback_handle = ""
            profile_url = str(profile.get("url") or "").strip()
            if profile_url:
                parsed_url = urlparse(profile_url)
                fallback_handle = parsed_url.path.strip("/").split("/")[0] if parsed_url.path else ""
            try:
                registry = IdentityRegistry.model_validate(
                    {
                        "social_handle": profile.get("handle")
                        or profile.get("username")
                        or profile.get("user")
                        or fallback_handle
                        or "",
                        "platform_detected": profile.get("platform") or "unknown",
                        "profile_url": profile_url,
                    }
                )
            except Exception:
                continue

            follower_count = int(profile.get("followers", 0) or 0)
            bio = str(profile.get("bio", "")).strip()
            links = profile.get("links") if isinstance(profile.get("links"), list) else []
            active = follower_count > 0 or bool(bio) or bool(links)

            findings.append(
                {
                    "type": "osint_finding",
                    "value": registry.profile_url,
                    "target": target,
                    "severity": "medium" if active else "info",
                    "confidence": 0.84 if active else 0.65,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(profile, ensure_ascii=True)[:1000],
                    "context": {
                        "kind": "social_profile_detail",
                        "platform": registry.platform_detected,
                        "identity_registry": registry.model_dump(mode="json"),
                        "follower_count": follower_count,
                        "bio": bio[:300],
                        "links": links,
                        "snl_mode": "fixture_only",
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["profile_intelligence_enrichment"],
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

            followers = int(finding.get("context", {}).get("follower_count", 0) or 0)
            bio = str(finding.get("context", {}).get("bio", "")).strip()
            links = finding.get("context", {}).get("links", [])
            if followers == 0 and not bio and not links:
                noise.append(finding)
            else:
                signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        platforms = sorted({str(f.get("context", {}).get("platform", "unknown")) for f in signal})
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "profiles_found": len(signal),
            "platforms": platforms,
            "operator_summary": (
                f"Social-Analyzer fixture ingestion produced {len(signal)} enriched profile records for {target}. "
                f"Profile Pulse telemetry emitted across {len(platforms)} platforms."
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
        fixture = opts.get("fixture_data")
        if fixture is None and isinstance(opts.get("fixture_path"), str):
            fixture = Path(opts["fixture_path"]).read_text(encoding="utf-8")

        started_at = datetime.now(UTC)
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
        stdout = json.dumps(
            {
                "profiles": [
                    {
                        "username": record.social_handle,
                        "platform": record.platform_detected,
                        "url": record.profile_url,
                    }
                    for record in records
                ]
            }
        )
        ended_at = datetime.now(UTC)
        runtime_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))

        result = self.map_output(
            target=target,
            command=["fixture://social-analyzer"],
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
