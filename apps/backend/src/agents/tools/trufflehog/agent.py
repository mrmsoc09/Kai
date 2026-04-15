from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from apps.backend.src.core.protocol import (
    FindingType,
    KaisonFinding,
    KaisonResult,
    KaisonResultMetadata,
    Severity,
)
from apps.backend.src.core.scope_guardrails import (
    audit_scope_decision,
    evaluate_target_scope,
    load_scope_policy,
)

from ..base_tool_agent import BaseToolAgent
from ..darknet_leak_schemas import VulnerabilityRegistry


_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}


class TrufflehogAgent(BaseToolAgent):
    """
    TruffleHog specialist agent for secret-leak detection.
    Supports v3 Go-based syntax with automatic masking and V-RAD telemetry.
    """

    TOOL_NAME = "trufflehog"

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._telemetry_events: list[dict[str, Any]] = []
        self._telemetry_hook: Callable[[dict[str, Any]], None] | None = None

    def register_telemetry_hook(self, hook: Callable[[dict[str, Any]], None]) -> None:
        self._telemetry_hook = hook

    def get_telemetry_events(self) -> list[dict[str, Any]]:
        return list(self._telemetry_events)

    def _emit_telemetry(self, metric: str, value: Any, payload: dict[str, Any] | None = None) -> None:
        event = {
            "tool": self.TOOL_NAME,
            "metric": metric,
            "value": value,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if payload:
            event["payload"] = payload
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
        """
        Builds TruffleHog command, handling v2/v3 syntax transition.
        Default is v3 subcommand-based architecture.
        """
        opts = options or {}
        cli_variant = str(opts.get("cli_variant", "v3")).strip().lower()

        if cli_variant == "v2":
            # v2: trufflehog [options] <url>
            cmd = ["trufflehog", "--json"]
            if self._is_repo_url(target):
                cmd.extend(["--regex", "--entropy", target])
            else:
                cmd.extend(["--find-paths", target])
            return cmd

        # v3 default: trufflehog <source> <target> [options]
        mode = "git" if self._is_repo_url(target) else "filesystem"
        cmd = ["trufflehog", mode, target, "--json", "--no-verification"]

        if bool(opts.get("only_verified", False)):
            # v3 verification filter
            cmd.append("--only-verified")
        
        # Add common v3 filters
        if opts.get("since_commit"):
            cmd.extend(["--since-commit", str(opts["since_commit"])])
        if opts.get("branch"):
            cmd.extend(["--branch", str(opts["branch"])])
        if opts.get("include_paths"):
            cmd.extend(["--include-paths", str(opts["include_paths"])])
        if opts.get("exclude_paths"):
            cmd.extend(["--exclude-paths", str(opts["exclude_paths"])])

        return cmd

    @staticmethod
    def _derive_location(record: dict[str, Any]) -> str:
        for key in ("file", "path", "File", "Location"):
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        source = record.get("SourceMetadata")
        if isinstance(source, dict):
            data = source.get("Data")
            if isinstance(data, dict):
                for branch in ("Filesystem", "Git", "Github"):
                    chunk = data.get(branch)
                    if isinstance(chunk, dict):
                        for key in ("file", "path", "line"):
                            value = chunk.get(key)
                            if isinstance(value, str) and value.strip():
                                return value.strip()
        return "unknown-location"

    @staticmethod
    def _derive_vuln_type(record: dict[str, Any]) -> str:
        for key in ("DetectorName", "detector_name", "type", "RuleID", "rule", "Category"):
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower().replace(" ", "_")
        return "secret_exposure"

    def map_output(
        self,
        *,
        target: str,
        command: list[str],
        stdout: str,
        stderr: str,
        exit_code: int,
        started_at: datetime,
        ended_at: datetime,
        runtime_ms: int,
        mission_id: str,
        status: str,
        options: dict[str, Any] | None = None,
    ) -> KaisonResult:
        findings: list[KaisonFinding] = []
        raw_lines = stdout.strip().splitlines()
        
        for line in raw_lines:
            token = line.strip()
            if not token:
                continue
            try:
                data = json.loads(token)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue

            # Handle v3 'Result' wrapper
            record = data.get("Result", data)
            
            vuln_type = self._derive_vuln_type(record)
            location = self._derive_location(record)
            
            # Skip noise/test files
            if any(m in location.lower() for m in ["test", "fixture", "mock", "example"]):
                continue

            try:
                registry = VulnerabilityRegistry.model_validate(
                    {
                        "vuln_type": vuln_type,
                        "location": location,
                        "risk_level": "critical",
                        "source_tool": self.TOOL_NAME,
                        "observed_at": datetime.now(UTC),
                        "masked": True,
                    }
                )
            except Exception:
                continue

            mask_id = hashlib.sha256(
                f"{registry.vuln_type}|{registry.location}".encode("utf-8")
            ).hexdigest()[:12]

            findings.append(
                KaisonFinding(
                    finding_type=FindingType.SECRET,
                    value=f"{registry.vuln_type} masked_at {registry.location} [ID:{mask_id}]",
                    source_agent=self.TOOL_NAME,
                    confidence=0.95,
                    severity=Severity.CRITICAL,
                    raw_evidence={
                        "vuln_type": registry.vuln_type,
                        "location": registry.location,
                        "mask_id": mask_id,
                        "vulnerability_registry": registry.model_dump(mode="json"),
                    },
                )
            )

        # Trigger V-RAD Telemetry for identified secrets
        if findings:
            self._emit_telemetry(
                "V-RAD_EVENT",
                "Secret Exposed",
                payload={
                    "v-rad_color": "NEON_RED",
                    "secret_count": len(findings),
                    "summary": f"Detected {len(findings)} leaked credentials in {target}"
                }
            )

        return KaisonResult(
            mission_id=mission_id,
            source_agent=self.TOOL_NAME,
            status=status,
            target_context={
                "target": target,
                "command": command,
                "exit_code": exit_code,
                "stderr": stderr[:2000],
                "options": options,
            },
            metadata=KaisonResultMetadata(
                started_at=started_at,
                ended_at=ended_at,
                runtime_ms=runtime_ms,
            ),
            findings=findings,
        )

    def execute(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        """
        Executes TruffleHog with policy checks and live scanning.
        """
        opts = dict(options or {})
        policy = self.check_policy(target, opts)
        
        if not policy["allowed"]:
            now = datetime.now(UTC)
            return KaisonResult(
                mission_id=mission_id,
                source_agent=self.TOOL_NAME,
                status="failure",
                target_context={
                    "target": target, 
                    "error": f"policy_blocked:{policy['reason']}"
                },
                metadata=KaisonResultMetadata(
                    started_at=now,
                    ended_at=now,
                    runtime_ms=0,
                ),
                findings=[],
            )

        # Use BaseToolAgent.execute for live subprocess execution
        result = super().execute(target, opts, mission_id=mission_id)
        
        # Enrich context with SNL info
        enriched_context = dict(result.target_context)
        enriched_context["snl_interface"] = policy.get("snl_interface")
        enriched_context["telemetry"] = self.get_telemetry_events()
        
        return result.model_copy(update={"target_context": enriched_context})
