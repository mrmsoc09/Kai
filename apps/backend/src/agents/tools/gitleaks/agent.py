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


class GitleaksAgent(BaseToolAgent):
    """
    Gitleaks specialist agent for credential scanning in git history and filesystems.
    Implements automatic masking and Neon Red V-RAD telemetry.
    """

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
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        
        # Gitleaks detect command
        cmd = [
            "gitleaks",
            "detect",
            "--source",
            target,
            "--report-format",
            "json",
            "--report-path",
            f"{artifact_dir}/gitleaks_{int(datetime.now(UTC).timestamp())}.json",
            "--redact", # Built-in redaction for stdout
        ]
        
        if opts.get("config_path"):
            cmd.extend(["--config", str(opts["config_path"])])
        
        if bool(opts.get("no_git", False)):
            cmd.append("--no-git")
            
        return cmd

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
        
        # Gitleaks output often goes to the report file
        # BaseToolAgent._recover_output_from_artifacts should handle loading it into 'stdout' 
        # if the command tokens match.
        
        raw_output = stdout.strip()
        if not raw_output:
            return KaisonResult(
                mission_id=mission_id,
                source_agent=self.TOOL_NAME,
                status=status,
                target_context={
                    "target": target,
                    "command": command,
                    "exit_code": exit_code,
                    "stderr": stderr[:2000],
                },
                metadata=KaisonResultMetadata(
                    started_at=started_at,
                    ended_at=ended_at,
                    runtime_ms=runtime_ms,
                ),
                findings=[],
            )

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            return KaisonResult(
                mission_id=mission_id,
                source_agent=self.TOOL_NAME,
                status="failure",
                target_context={
                    "target": target,
                    "command": command,
                    "exit_code": exit_code,
                    "error": "failed_to_parse_json_output",
                },
                metadata=KaisonResultMetadata(
                    started_at=started_at,
                    ended_at=ended_at,
                    runtime_ms=runtime_ms,
                ),
                findings=[],
            )

        results = data if isinstance(data, list) else data.get("results", [])
        if not isinstance(results, list):
            results = []

        for entry in results:
            if not isinstance(entry, dict):
                continue

            file_path = self._derive_location(entry)
            vuln_type = self._derive_vuln_type(entry)
            
            # Skip noise
            if any(marker in file_path.lower() for marker in ["test", "fixture", "mock", "example"]):
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

            mask_id = hashlib.sha256(f"{registry.vuln_type}|{registry.location}".encode("utf-8")).hexdigest()[:12]
            
            findings.append(
                KaisonFinding(
                    finding_type=FindingType.SECRET,
                    value=f"{registry.vuln_type} masked_at {registry.location} [ID:{mask_id}]",
                    source_agent=self.TOOL_NAME,
                    confidence=0.92,
                    severity=Severity.CRITICAL,
                    raw_evidence={
                        "vuln_type": registry.vuln_type,
                        "location": registry.location,
                        "mask_id": mask_id,
                        "vulnerability_registry": registry.model_dump(mode="json"),
                    },
                )
            )

        # Trigger V-RAD Telemetry
        if findings:
            self._emit_telemetry(
                "V-RAD_EVENT",
                "Secret Exposed",
                payload={
                    "v-rad_color": "NEON_RED",
                    "secret_count": len(findings),
                    "summary": f"Gitleaks detected {len(findings)} sensitive patterns in {target}"
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

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        if not raw_output.strip():
            return result
        try:
            entries = json.loads(raw_output)
            if not isinstance(entries, list):
                entries = [entries]
        except json.JSONDecodeError:
            entries = []
            for line in raw_output.splitlines():
                token = line.strip()
                if not token:
                    continue
                try:
                    entries.append(json.loads(token))
                except json.JSONDecodeError:
                    entries.append({"raw": token})
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            vuln_type = self._derive_vuln_type(entry)
            location = self._derive_location(entry)
            if any(m in location.lower() for m in ["test", "fixture", "mock", "example"]):
                continue
            derived = {"vuln_type": vuln_type, "location": location}
            result.append({
                "type": "secret_exposure",
                "value": f"{vuln_type}@{location}"[:500],
                "target": target,
                "severity": "critical",
                "confidence": 0.9,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": json.dumps(derived, ensure_ascii=True)[:1200],
                "context": {"vuln_type": vuln_type, "location": location},
                "recommended_next_tools": ["EvidenceAnalystAgent"],
                "recommended_next_actions": ["rotate_credential", "investigate"],
            })
        return result

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()
        for finding in findings:
            value = str(finding.get("value", "")).lower()
            ftype = str(finding.get("type", "secret_exposure")).lower()
            tgt = str(finding.get("target", "")).lower()
            if f"{tgt}|{ftype}|{value}" in known:
                noise.append(finding)
                continue
            if str(finding.get("severity", "info")).lower() == "info":
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
            "total_findings": len(signal),
            "operator_summary": (
                f"Gitleaks found {len(signal)} credential exposures in {target}."
            ),
        }

    def execute(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        """
        Executes Gitleaks with policy validation and live scanning.
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
        
        # Enrich context
        enriched_context = dict(result.target_context)
        enriched_context["snl_interface"] = policy.get("snl_interface")
        enriched_context["telemetry"] = self.get_telemetry_events()
        
        return result.model_copy(update={"target_context": enriched_context})
