from __future__ import annotations

from datetime import UTC, datetime
import hashlib
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
from ..darknet_leak_schemas import VulnerabilityRegistry


_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}


class GitleaksAgent(BaseToolAgent):
    TOOL_NAME = "gitleaks"

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
    def _is_repo_url(target: str) -> bool:
        token = target.strip().lower()
        return token.startswith("http://") or token.startswith("https://") or token.startswith("git@")

    def check_policy(self, target: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        opts = options or {}
        allow_local_path = bool(opts.get("allow_local_path", True))
        scope_label = str(opts.get("research_scope", _APPROVED_SCOPE_LABEL)).strip()

        if allow_local_path and not self._is_repo_url(target):
            snl_interface = str(opts.get("snl_interface", "tun0")).strip()
            snl_ok = snl_interface in _ALLOWED_SNL_INTERFACES
            return {
                "allowed": snl_ok and scope_label == _APPROVED_SCOPE_LABEL,
                "reason": "local_path_allowed" if snl_ok else f"snl_interface_not_allowed:{snl_interface}",
                "target": target,
                "matched_rule": "local_path",
                "snl_interface": snl_interface,
            }

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
        return [
            "gitleaks",
            "detect",
            "--source",
            target,
            "--report-format",
            "json",
            "--report-path",
            f"{artifact_dir}/gitleaks.json",
            "--redact",
        ]

    @staticmethod
    def _derive_location(record: dict[str, Any]) -> str:
        for key in ("File", "file", "Path", "path", "location"):
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "unknown-location"

    @staticmethod
    def _derive_vuln_type(record: dict[str, Any]) -> str:
        for key in ("RuleID", "Rule", "rule", "Description", "Category"):
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower().replace(" ", "_")
        return "secret_exposure"

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_output = raw_output.strip()
        if not raw_output:
            return findings

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            return findings

        results = data if isinstance(data, list) else data.get("results", [])
        if not isinstance(results, list):
            return findings

        for entry in results:
            if not isinstance(entry, dict):
                continue

            file_path = self._derive_location(entry)
            vuln_type = self._derive_vuln_type(entry)
            is_test_fixture = any(marker in file_path.lower() for marker in ["test", "fixture", "fake", "mock", "example"])
            if is_test_fixture:
                continue

            try:
                registry = VulnerabilityRegistry.model_validate(
                    {
                        "vuln_type": vuln_type,
                        "location": file_path,
                        "risk_level": "critical",
                        "source_tool": self.TOOL_NAME,
                        "observed_at": datetime.now(UTC),
                        "masked": True,
                    }
                )
            except Exception:
                continue

            masked_id = hashlib.sha256(f"{registry.vuln_type}|{registry.location}".encode("utf-8")).hexdigest()[:12]
            findings.append(
                {
                    "type": "exposed_secret",
                    "value": f"{registry.vuln_type} in {registry.location}",
                    "target": target,
                    "severity": "critical",
                    "confidence": 0.92,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(
                        {
                            "vuln_type": registry.vuln_type,
                            "location": registry.location,
                            "masked": True,
                            "mask_id": masked_id,
                        },
                        ensure_ascii=True,
                    ),
                    "context": {
                        "vulnerability_registry": registry.model_dump(mode="json"),
                        "vuln_type": registry.vuln_type,
                        "location": registry.location,
                        "masked": True,
                        "snl_mode": "fixture_only",
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["credential_rotation", "incident_response"],
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
            key = f"{str(finding.get('target', '')).lower()}|exposed_secret|{str(finding.get('value', '')).lower()}"
            if key in known:
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
            "next_agents": ["EvidenceAnalystAgent"],
            "detected_secrets": len(signal),
            "operator_summary": (
                f"Gitleaks normalized {len(signal)} critical secret patterns in {target}; values masked for safety."
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
            command=["fixture://gitleaks"],
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

        self._emit_telemetry("AGENT_STATUS", "SECRET_DETECTION")
        self._emit_telemetry("SECRETS_IDENTIFIED", len(result.findings))
        if result.findings:
            self._emit_telemetry("EventLog", "SECRET_EXPOSED_NEON_RED")

        context = dict(result.target_context)
        context.update(
            {
                "mode": "stub_fixture",
                "snl_interface": policy.get("snl_interface"),
                "telemetry": self.get_telemetry_events(),
            }
        )
        return result.model_copy(update={"target_context": context})
