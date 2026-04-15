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
from ..content_discovery_schemas import ParameterRegistry


_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}
_MAX_RPS_CAP = 50


class ArjunAgent(BaseToolAgent):
    TOOL_NAME = "arjun"

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
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        endpoint = str(opts.get("endpoint", target))
        output_path = f"{artifact_dir}/arjun.json"
        rps = self._normalize_rps(opts)
        delay = round(1.0 / float(rps), 3)
        return [
            "arjun",
            "-u",
            endpoint,
            "--stable",
            "-oJ",
            output_path,
            "--delay",
            str(delay),
        ]

    @staticmethod
    def _extract_records(data: Any, target: str) -> list[tuple[str, list[str], str]]:
        records: list[tuple[str, list[str], str]] = []
        if isinstance(data, dict):
            if "endpoint" in data and isinstance(data.get("parameters"), list):
                endpoint = str(data.get("endpoint", target))
                params = [str(p).strip() for p in data.get("parameters", []) if str(p).strip()]
                method = str(data.get("method", "GET"))
                records.append((endpoint, params, method))
            else:
                for endpoint, params in data.items():
                    if isinstance(params, list):
                        clean = [str(p).strip() for p in params if str(p).strip()]
                        records.append((str(endpoint), clean, "GET"))
            return records

        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                endpoint = str(item.get("endpoint", target))
                params = item.get("parameters") or item.get("params") or []
                method = str(item.get("method", "GET"))
                if isinstance(params, list):
                    clean = [str(p).strip() for p in params if str(p).strip()]
                    records.append((endpoint, clean, method))
        return records

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        token = raw_output.strip()
        if not token:
            return findings

        try:
            data = json.loads(token)
        except json.JSONDecodeError:
            data = None

        if data is None:
            return findings

        for endpoint, params, method in self._extract_records(data, target):
            for param in params:
                try:
                    parameter_registry = ParameterRegistry.model_validate(
                        {
                            "endpoint_url": endpoint,
                            "parameter_name": param,
                            "source": self.TOOL_NAME,
                            "timestamp": datetime.now(UTC),
                        }
                    )
                except Exception:
                    continue

                findings.append(
                    {
                        "type": "parameter",
                        "value": parameter_registry.parameter_name,
                        "target": target,
                        "severity": "info",
                        "confidence": 0.88,
                        "source_tool": self.TOOL_NAME,
                        "raw_evidence": token[:1200],
                        "context": {
                            "endpoint": parameter_registry.endpoint_url,
                            "method": method,
                            "parameter_registry": parameter_registry.model_dump(mode="json"),
                            "target_context": {
                                "dalfox_targets": [parameter_registry.endpoint_url],
                                "ssrfmap_targets": [
                                    {
                                        "endpoint": parameter_registry.endpoint_url,
                                        "parameter": parameter_registry.parameter_name,
                                        "method": method,
                                    }
                                ],
                            },
                            "snl_mode": "fixture_only",
                        },
                        "recommended_next_tools": ["dalfox", "ssrfmap"],
                        "recommended_next_actions": ["xss_param_validation", "ssrf_param_validation"],
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
            endpoint = str(finding.get("context", {}).get("endpoint", "")).lower()
            value = str(finding.get("value", "")).lower()
            key = f"{str(finding.get('target', '')).lower()}|parameter|{value}@{endpoint}"
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
        endpoint_param_map: dict[str, list[str]] = {}
        for finding in signal:
            endpoint = str(finding.get("context", {}).get("endpoint", target))
            param = str(finding.get("value", "")).strip()
            if not param:
                continue
            endpoint_param_map.setdefault(endpoint, [])
            if param not in endpoint_param_map[endpoint]:
                endpoint_param_map[endpoint].append(param)

        parameter_list = sorted({p for params in endpoint_param_map.values() for p in params})
        dalfox_targets = sorted(endpoint_param_map.keys())
        ssrf_targets = [
            {"endpoint": endpoint, "parameters": params}
            for endpoint, params in endpoint_param_map.items()
        ]

        return {
            "next_agents": ["dalfox", "ssrfmap"],
            "parameter_list": parameter_list,
            "endpoint_param_map": endpoint_param_map,
            "target_context": {
                "dalfox_targets": dalfox_targets,
                "ssrfmap_targets": ssrf_targets,
            },
            "operator_summary": (
                f"Arjun identified {len(parameter_list)} unique parameters across "
                f"{len(endpoint_param_map)} endpoints for {target}."
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
            command=["fixture://arjun"],
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

        self._emit_telemetry("AGENT_STATUS", "PARAMETER_DISCOVERY")
        self._emit_telemetry("PARAM_MAP", len(result.findings))
        if result.findings:
            self._emit_telemetry("EventLog", "TREE_EXPANSION")

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
