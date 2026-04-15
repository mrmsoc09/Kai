from __future__ import annotations

from datetime import UTC, datetime
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


_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}


class SearchsploitAgent(BaseToolAgent):
    TOOL_NAME = "searchsploit"

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
        query = str(opts.get("software_version") or opts.get("cve") or target).strip()
        return ["searchsploit", "--json", query]

    @staticmethod
    def _extract_results(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []

        candidates: list[dict[str, Any]] = []
        for key in ("RESULTS", "RESULTS_EXPLOIT", "results", "exploits"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates.extend(item for item in value if isinstance(item, dict))
        if candidates:
            return candidates

        return [payload]

    @staticmethod
    def _derive_title(record: dict[str, Any]) -> str:
        for key in ("Title", "title", "name"):
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "unknown_searchsploit_match"

    @staticmethod
    def _derive_path(record: dict[str, Any]) -> str:
        for key in ("Path", "path", "File", "file"):
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _derive_classifier(record: dict[str, Any], title: str) -> tuple[str, str]:
        lower_blob = " ".join(
            [
                title.lower(),
                str(record.get("Type", "")).lower(),
                str(record.get("EDB-ID", "")).lower(),
                str(record.get("CVE", "")).lower(),
            ]
        )
        if any(token in lower_blob for token in ["rce", "remote code execution", "auth bypass"]):
            return "critical", "high_impact_match"
        if any(token in lower_blob for token in ["sql", "sqli", "deserialization", "xxe"]):
            return "high", "actionable_match"
        if "xss" in lower_blob:
            return "medium", "client_side_match"
        return "medium", "general_match"

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        token = raw_output.strip()
        if not token:
            return findings

        try:
            payload = json.loads(token)
        except json.JSONDecodeError:
            return findings

        for record in self._extract_results(payload):
            title = self._derive_title(record)
            path = self._derive_path(record)
            severity, signal_reason = self._derive_classifier(record, title)
            has_local_script = path.lower().endswith((".py", ".rb"))

            findings.append(
                {
                    "type": "known_cve_match",
                    "value": title,
                    "target": target,
                    "severity": severity,
                    "confidence": 0.9 if has_local_script else 0.82,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(record, ensure_ascii=True)[:2000],
                    "context": {
                        "exploitdb_id": str(record.get("EDB-ID", record.get("id", ""))),
                        "cve": str(record.get("CVE", "")),
                        "template_id": str(record.get("Template", record.get("template-id", ""))),
                        "poc_local_path": path,
                        "poc_script_available": has_local_script,
                        "signal_reason": signal_reason,
                        "snl_mode": "fixture_only",
                    },
                    "recommended_next_tools": ["nuclei_scan", "EvidenceAnalystAgent"],
                    "recommended_next_actions": ["validate_exploitability", "document_poc_reference"],
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
            key = f"{str(finding.get('target', '')).lower()}|known_cve_match|{str(finding.get('value', '')).lower()}"
            if key in known:
                noise.append(finding)
                continue

            if not str(finding.get("context", {}).get("exploitdb_id", "")).strip() and not str(
                finding.get("context", {}).get("cve", "")
            ).strip():
                noise.append(finding)
                continue

            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        poc_count = len([f for f in signal if f.get("context", {}).get("poc_script_available")])
        return {
            "next_agents": ["nuclei_scan", "EvidenceAnalystAgent"],
            "total_matches": len(signal),
            "local_poc_scripts": poc_count,
            "operator_summary": (
                f"Searchsploit matched {len(signal)} exploit references for {target}; "
                f"{poc_count} include local .py/.rb PoC script paths."
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
            command=["fixture://searchsploit"],
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

        local_poc_hits = 0
        for finding in result.findings:
            ctx = finding.raw_evidence.get("context", {}) if isinstance(finding.raw_evidence, dict) else {}
            if bool(ctx.get("poc_script_available", False)):
                local_poc_hits += 1

        self._emit_telemetry("AGENT_STATUS", "POC_LOOKUP")
        self._emit_telemetry("SEARCHSPLOIT_MATCH_COUNT", len(result.findings))
        self._emit_telemetry("LOCAL_POC_COUNT", local_poc_hits)
        if local_poc_hits > 0:
            self._emit_telemetry("EventLog", "EXPLOIT_AVAILABLE_GOLD_BORDER")

        context = dict(result.target_context)
        context.update(
            {
                "mode": "stub_fixture",
                "snl_interface": policy.get("snl_interface"),
                "telemetry": self.get_telemetry_events(),
            }
        )
        return result.model_copy(update={"target_context": context})
