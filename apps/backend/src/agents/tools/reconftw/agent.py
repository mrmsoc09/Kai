from __future__ import annotations

from datetime import UTC, datetime
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
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
from ..osint_schemas import DiscoveryRegistry
from .install import install_reconftw, get_install_commands
from .reconftw_config import load_snl_settings, write_reconftw_cfg
from .schemas import AssetInventoryRegistry


_APPROVED_SCOPE_LABEL = "Approved Research Scope"
_ALLOWED_SNL_INTERFACES = {"tun0", "wg0", "vpn0", "snl0"}
_MANAGED_K1_TOOLS = ("nuclei", "findomain", "subfinder", "httpx", "naabu", "amass")
_SUBDOMAIN_RE = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")
_URL_RE = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
_PHASE_BY_MODE = {
    "subdomains": ["SUBDOMAINS"],
    "web": ["WEB"],
    "deep": ["SUBDOMAINS", "WEB", "DEEP"],
    "all": ["SUBDOMAINS", "WEB", "DEEP", "ALL"],
}
_MODE_FLAGS = {
    "subdomains": "--subdomains",
    "web": "--web",
    "deep": "--deep",
    "all": "-all",
}


class ReconftwAgent(BaseToolAgent):
    """
    ReconFTW Meta-Orchestrator Agent for K1 platform.
    Acts as a high-level multi-tool sub-orchestrator with SNL enforcement.
    """
    TOOL_NAME = "reconftw"

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
    def _normalize_modes(options: dict[str, Any]) -> list[str]:
        modes_raw = options.get("modes")
        if isinstance(modes_raw, str) and modes_raw.strip():
            modes = [modes_raw.strip().lower()]
        elif isinstance(modes_raw, list):
            modes = [str(item).strip().lower() for item in modes_raw if str(item).strip()]
        else:
            modes = [str(options.get("mode", "subdomains")).strip().lower()]

        normalized: list[str] = []
        for mode in modes:
            if mode in _PHASE_BY_MODE and mode not in normalized:
                normalized.append(mode)
        return normalized or ["subdomains"]

    def check_policy(self, target: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """Strictly enforce execution policy to ensure targets are within scope."""
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
        """Support granular flags and ensure SNL interface via generated config."""
        opts = options or {}

        modes = self._normalize_modes(opts)
        cmd = ["reconftw.sh", "-d", target]

        # Selectivity Logic: trigger specific phases
        if "all" in modes:
            cmd.append("-all")
        else:
            for mode in modes:
                flag = _MODE_FLAGS.get(mode)
                if flag:
                    cmd.append(flag)

        # Config path for SNL enforcement: explicit opt takes priority
        explicit_config = opts.get("config_path")
        if explicit_config:
            cmd.extend(["-c", str(explicit_config)])
        else:
            output_root = str(opts.get("output_root") or os.getenv("K1_WORKFLOW_OUTPUT_ROOT", "output"))
            derived_cfg = Path(output_root).expanduser().resolve() / "reconftw" / target / "reconftw.cfg"
            if derived_cfg.exists():
                cmd.extend(["-c", str(derived_cfg)])

        if bool(opts.get("deep", False)) and "--deep" not in cmd:
            cmd.append("--deep")

        return cmd

    def install(self, target: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """Handle full reconftw dependency tree and config injection."""
        opts = options or {}
        snl_settings = load_snl_settings(opts)
        nvme_root = str(opts.get("nvme_root") or os.getenv("K1_NVME_ROOT", "/mnt/nvme"))
        output_root = str(opts.get("output_root") or os.getenv("K1_WORKFLOW_OUTPUT_ROOT", "output"))
        config_path = str(
            opts.get("config_path")
            or (Path(output_root).expanduser().resolve() / "reconftw" / target / "reconftw.cfg")
        )
        
        target_dir = Path(nvme_root) / "reconftw"
        install_info = install_reconftw(install_dir=target_dir, nvme_root=nvme_root)
        
        # Config Injection: Generate reconftw.cfg forcing traffic through SNL
        cfg = write_reconftw_cfg(
            target=target,
            config_path=config_path,
            snl_settings=snl_settings,
            nvme_root=nvme_root,
            output_root=output_root,
            managed_tools=list(_MANAGED_K1_TOOLS),
        )

        return {
            "tool": self.TOOL_NAME,
            "install_commands": get_install_commands(target_dir),
            "config_path": cfg.config_path,
            "install_info": install_info,
            "managed_tools_disabled": cfg.managed_tools_disabled,
            "conflict_resolution": {
                "k1_managed_tools": list(_MANAGED_K1_TOOLS),
                "reconftw_autoinstall_disabled": True,
            },
            "snl_settings": snl_settings,
        }

    @staticmethod
    def _extract_subdomains(value: str, root_target: str) -> list[str]:
        root = root_target.strip().lower().rstrip(".")
        matches = []
        for token in _SUBDOMAIN_RE.findall(value):
            candidate = token.lower().rstrip(".")
            if candidate == root or candidate.endswith(f".{root}"):
                matches.append(candidate)
        return matches

    @staticmethod
    def _extract_urls(value: str) -> list[str]:
        return [token.strip() for token in _URL_RE.findall(value)]

    @staticmethod
    def _extract_ips(value: str) -> list[str]:
        ips: list[str] = []
        for token in _IP_RE.findall(value):
            try:
                ipaddress.ip_address(token)
            except ValueError:
                continue
            ips.append(token)
        return ips

    def _build_asset_inventory(
        self,
        *,
        asset_type: str,
        asset_value: str,
        target: str,
        phase: str,
        metadata: dict[str, Any] | None = None,
        provider: str | None = None,
        screenshot_path: str | None = None,
    ) -> AssetInventoryRegistry | None:
        try:
            return AssetInventoryRegistry.model_validate(
                {
                    "asset_type": asset_type,
                    "asset_value": asset_value,
                    "target_root": target,
                    "intel_source": "reconftw_meta_orchestrator",
                    "phase": phase,
                    "provider": provider,
                    "screenshot_path": screenshot_path,
                    "metadata": metadata or {},
                    "observed_at": datetime.now(UTC),
                }
            )
        except Exception:
            return None

    def _build_subdomain_finding(self, domain: str, target: str, phase: str, evidence: str) -> dict[str, Any] | None:
        try:
            discovery = DiscoveryRegistry.model_validate(
                {
                    "discovered_domain": domain,
                    "intel_source": "reconftw_meta_orchestrator",
                    "timestamp": datetime.now(UTC),
                }
            )
        except Exception:
            return None

        inventory = self._build_asset_inventory(
            asset_type="subdomain",
            asset_value=domain,
            target=target,
            phase=phase,
            metadata={"record_type": "subdomain"},
        )
        if inventory is None:
            return None

        return {
            "type": "subdomain",
            "value": discovery.discovered_domain,
            "target": target,
            "severity": "info",
            "confidence": 0.85,
            "source_tool": self.TOOL_NAME,
            "raw_evidence": evidence[:1000],
            "context": {
                "record_type": "subdomain",
                "phase": phase,
                "discovery_registry": discovery.model_dump(mode="json"),
                "asset_inventory_registry": inventory.model_dump(mode="json"),
            },
            "recommended_next_tools": ["dnsx", "httpx_probe"],
            "recommended_next_actions": ["resolve_dns"],
        }

    def _build_inventory_finding(
        self,
        *,
        asset_type: str,
        asset_value: str,
        target: str,
        phase: str,
        evidence: str,
        metadata: dict[str, Any] | None = None,
        provider: str | None = None,
        screenshot_path: str | None = None,
    ) -> dict[str, Any] | None:
        intel_source = "reconftw_meta_orchestrator"
        if asset_type == "darknet_link":
            intel_source = "tor"

        inventory = self._build_asset_inventory(
            asset_type=asset_type,
            asset_value=asset_value,
            target=target,
            phase=phase,
            metadata=metadata,
            provider=provider,
            screenshot_path=screenshot_path,
        )
        if inventory is None:
            return None

        finding = {
            "type": "asset_inventory",
            "value": asset_value,
            "target": target,
            "severity": "info",
            "confidence": 0.8,
            "source_tool": self.TOOL_NAME,
            "raw_evidence": evidence[:1000],
            "context": {
                "record_type": asset_type,
                "phase": phase,
                "asset_inventory_registry": inventory.model_dump(mode="json"),
            },
            "recommended_next_tools": ["httpx_probe", "nuclei_scan"],
            "recommended_next_actions": ["inventory_enrichment"],
        }
        
        if asset_type == "darknet_link":
            try:
                discovery = DiscoveryRegistry.model_validate(
                    {
                        "discovered_domain": asset_value,
                        "intel_source": "tor",
                        "timestamp": datetime.now(UTC),
                    }
                )
                finding["context"]["discovery_registry"] = discovery.model_dump(mode="json")
            except Exception:
                pass
                
        return finding

    def parse_output_directory(self, output_dir: str | Path, target: str) -> list[dict[str, Any]]:
        """High-performance parser for the reconftw output directory."""
        base = Path(output_dir).expanduser().resolve()
        findings: list[dict[str, Any]] = []
        if not base.exists() or not base.is_dir():
            return findings

        seen: set[tuple[str, str]] = set()

        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            name = path.name.lower()

            # Handle Screenshots
            if suffix in _SCREENSHOT_EXTENSIONS:
                finding = self._build_inventory_finding(
                    asset_type="screenshot",
                    asset_value=str(path),
                    target=target,
                    phase="WEB",
                    evidence=f"screenshot:{path}",
                    metadata={"record_type": "screenshot"},
                    screenshot_path=str(path),
                )
                if finding:
                    key = (finding["type"], finding["value"].lower())
                    if key not in seen:
                        seen.add(key)
                        findings.append(finding)
                continue

            if suffix not in {".txt", ".log", ".json", ".jsonl", ".csv"}:
                continue

            try:
                # Optimized chunk-based or buffered reading could be here for very large files
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            phase = "DEEP" if "deep" in str(path).lower() else "SUBDOMAINS"
            if any(tag in str(path).lower() for tag in ("web", "alive", "httpx", "url")):
                phase = "WEB"

            for line in content.splitlines():
                token = line.strip()
                if not token:
                    continue

                # Normalization: Map all results to K1 registries
                for domain in self._extract_subdomains(token, target):
                    finding = self._build_subdomain_finding(domain, target, phase, f"{path}:{token}")
                    if finding:
                        key = (finding["type"], finding["value"].lower())
                        if key not in seen:
                            seen.add(key)
                            findings.append(finding)

                for ip_value in self._extract_ips(token):
                    finding = self._build_inventory_finding(
                        asset_type="ip",
                        asset_value=ip_value,
                        target=target,
                        phase=phase,
                        evidence=f"{path}:{token}",
                        metadata={"record_type": "ip_address"},
                    )
                    if finding:
                        key = (finding["type"], finding["value"].lower())
                        if key not in seen:
                            seen.add(key)
                            findings.append(finding)

                if ".onion" in token.lower():
                    finding = self._build_inventory_finding(
                        asset_type="darknet_link",
                        asset_value=token,
                        target=target,
                        phase=phase,
                        evidence=f"{path}:{token}",
                        metadata={"record_type": "darknet_link"},
                    )
                    if finding:
                        key = (finding["type"], finding["value"].lower())
                        if key not in seen:
                            seen.add(key)
                            findings.append(finding)

                if "provider" in name or "cloud" in name or "bucket" in name:
                    asset_type = "cloud_bucket" if "bucket" in token.lower() else "provider"
                    provider = token.split(":", 1)[0].strip().lower()
                    finding = self._build_inventory_finding(
                        asset_type=asset_type,
                        asset_value=token,
                        target=target,
                        phase=phase,
                        evidence=f"{path}:{token}",
                        metadata={"record_type": "cloud_data"},
                        provider=provider[:255] or None,
                    )
                    if finding:
                        key = (finding["type"], finding["value"].lower())
                        if key not in seen:
                            seen.add(key)
                            findings.append(finding)

                for url in self._extract_urls(token):
                    finding = self._build_inventory_finding(
                        asset_type="url",
                        asset_value=url,
                        target=target,
                        phase=phase,
                        evidence=f"{path}:{token}",
                        metadata={"record_type": "url"},
                    )
                    if finding:
                        key = (finding["type"], finding["value"].lower())
                        if key not in seen:
                            seen.add(key)
                            findings.append(finding)

        return findings

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        """Parse raw reconftw text output, extracting subdomains, URLs, and IPs."""
        findings: list[dict[str, Any]] = []
        if not raw_output.strip():
            return findings
        seen: set[tuple[str, str]] = set()
        for line in raw_output.splitlines():
            token = line.strip()
            if not token:
                continue
            for domain in self._extract_subdomains(token, target):
                f = self._build_subdomain_finding(domain, target, "SUBDOMAINS", token)
                if f:
                    key = (f["type"], f["value"].lower())
                    if key not in seen:
                        seen.add(key)
                        findings.append(f)
            for url in self._extract_urls(token):
                f = self._build_inventory_finding(
                    asset_type="url", asset_value=url, target=target,
                    phase="WEB", evidence=token, metadata={"record_type": "url"},
                )
                if f:
                    key = (f["type"], f["value"].lower())
                    if key not in seen:
                        seen.add(key)
                        findings.append(f)
            for ip in self._extract_ips(token):
                f = self._build_inventory_finding(
                    asset_type="ip", asset_value=ip, target=target,
                    phase="SUBDOMAINS", evidence=token, metadata={"record_type": "ip_address"},
                )
                if f:
                    key = (f["type"], f["value"].lower())
                    if key not in seen:
                        seen.add(key)
                        findings.append(f)
        return findings

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
        """Convert json-encoded directory findings list from stdout into KaisonResult."""
        kaison_findings: list[KaisonFinding] = []
        raw = stdout.strip()
        if raw:
            try:
                raw_list = json.loads(raw)
                if not isinstance(raw_list, list):
                    raw_list = []
            except json.JSONDecodeError:
                raw_list = []

            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                ftype_str = str(item.get("type", "asset_inventory")).lower()
                if "subdomain" in ftype_str:
                    finding_type = FindingType.SUBDOMAIN
                else:
                    finding_type = FindingType.CONFIG
                value = str(item.get("value", "")).strip()[:500]
                if not value:
                    continue
                try:
                    kaison_findings.append(
                        KaisonFinding(
                            finding_type=finding_type,
                            value=value,
                            source_agent=self.TOOL_NAME,
                            confidence=float(item.get("confidence", 0.8)),
                            severity=Severity.INFO,
                            raw_evidence=item.get("context") or {},
                        )
                    )
                except Exception:
                    continue

        return KaisonResult(
            mission_id=mission_id,
            source_agent=self.TOOL_NAME,
            status=status,
            target_context={
                "target": target,
                "command": command,
                "exit_code": exit_code,
                "stderr": (stderr or "")[:2000],
                "options": options,
            },
            metadata=KaisonResultMetadata(
                started_at=started_at,
                ended_at=ended_at,
                runtime_ms=runtime_ms,
            ),
            findings=kaison_findings,
        )

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()
        for finding in findings:
            value = str(finding.get("value", "")).lower()
            ftype = str(finding.get("type", "asset_inventory")).lower()
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
            "next_agents": ["OSINTIntelligenceAgent", "VulnerabilityAgent"],
            "total_findings": len(signal),
            "operator_summary": (
                f"ReconFTW meta-orchestrator mapped {len(signal)} assets for {target}."
            ),
        }

    def _run_phase_gate(self, *, target: str, phase: str, findings_count: int, options: dict[str, Any]) -> dict[str, Any]:
        """Implementation of Phase-Gate where the agent pauses for orchestrator strategy handshake."""
        payload = {
            "tool": self.TOOL_NAME,
            "target": target,
            "phase": phase,
            "findings_count": findings_count,
            "playbook_library": str(options.get("playbook_library", "tools/knowledge/playbooks")),
            "timestamp": datetime.now(UTC).isoformat(),
            "status": "GATE_OPEN",
        }
        
        # Trigger cross-reference signal
        self._emit_telemetry("PHASE_GATE_HANDSHAKE", phase, payload=payload)
        
        hook = options.get("phase_hook")
        if callable(hook):
            try:
                result = hook(payload)
                payload["orchestrator_response"] = result
            except Exception as exc:
                payload["hook_error"] = str(exc)
        
        return payload

    def execute(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        opts = dict(options or {})
        started_at = datetime.now(UTC)
        
        # Guardrail: strictly enforce check_policy
        policy = self.check_policy(target, opts)
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
                    runtime_ms=0,
                ),
                findings=[],
            )

        if bool(opts.get("install_only", False)):
            install_payload = self.install(target=target, options=opts)
            ended_at = datetime.now(UTC)
            return KaisonResult(
                mission_id=mission_id,
                source_agent=self.TOOL_NAME,
                status="success",
                target_context={
                    "target": target,
                    "mode": "install_plan",
                    "install_payload": install_payload,
                },
                metadata=KaisonResultMetadata(
                    started_at=started_at,
                    ended_at=ended_at,
                    runtime_ms=max(0, int((ended_at - started_at).total_seconds() * 1000)),
                ),
                findings=[],
            )

        fixture = opts.get("fixture_data")
        output_dir = str(opts.get("output_dir", "")).strip()
        directory_findings: list[dict[str, Any]] = []
        if fixture is not None:
            fixture_text = fixture if isinstance(fixture, str) else json.dumps(fixture)
            directory_findings = self.parse_output(fixture_text, target)
        elif output_dir:
            directory_findings = self.parse_output_directory(output_dir, target)

        modes = self._normalize_modes(opts)
        phases = []
        for mode in modes:
            phases.extend(_PHASE_BY_MODE.get(mode, []))
        
        # Telemetry: Visuals
        self._emit_telemetry("AGENT_STATUS", "ACTIVE")
        self._emit_telemetry("EventLog", "SATELLITE_SWEEP_LARGE_ARCS")
        
        phase_gates = []
        for index, phase in enumerate(phases, start=1):
            # Telemetry: Metrics
            completion = int((index / len(phases)) * 100)
            self._emit_telemetry("CURRENT_PHASE", phase)
            self._emit_telemetry("PHASE_COMPLETION", completion)
            
            # Phase-Gate logic
            gate_result = self._run_phase_gate(
                target=target,
                phase=phase,
                findings_count=len(directory_findings),
                options=opts,
            )
            phase_gates.append(gate_result)

        # Normalization and Result Mapping
        result = self.map_output(
            target=target,
            command=self.build_command(target, opts),
            stdout=json.dumps(directory_findings),
            stderr="",
            exit_code=0,
            started_at=started_at,
            ended_at=datetime.now(UTC),
            runtime_ms=0,
            mission_id=mission_id,
            status="success",
            options=opts,
        )

        self._emit_telemetry("TOTAL_ASSETS_MAPPED", len(result.findings))

        context = dict(result.target_context)
        context.update({
            "snl_interface": policy["snl_interface"],
            "selective_modes": modes,
            "phase_gates": phase_gates,
            "managed_tools_disabled": list(_MANAGED_K1_TOOLS),
            "telemetry": self.get_telemetry_events(),
        })
        return result.model_copy(update={"target_context": context})


ReconftfwAgent = ReconftwAgent
