from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from apps.backend.src.core.protocol import KaisonResult, KaisonResultMetadata

from ..base_tool_agent import BaseToolAgent
from .schemas import IntelRegistry, SubfinderRawRecord

_HIGH_SIGNAL_KEYWORDS = {
    "admin",
    "api",
    "staging",
    "internal",
    "jenkins",
    "grafana",
    "vault",
    "k8s",
    "dev",
    "portal",
    "dashboard",
    "backend",
    "gateway",
    "graphql",
    "rest",
    "swagger",
    "debug",
    "test",
    "mgmt",
    "management",
    "console",
    "kibana",
    "elastic",
}
_NOISE_KEYWORDS = {"mail", "smtp", "ftp", "pop", "imap", "cdn", "mx"}
_RATE_LIMIT_RE = re.compile(
    r"(429|rate[\s_-]*limit|too many requests|quota exceeded|api.*limit)",
    re.IGNORECASE,
)
_HIGH_INTEREST_TLDS = {"gov", "mil", "edu", "int"}
_DEFAULT_VPN_INTERFACES = ("tun0", "wg0", "vpn0")


class SubfinderAgent(BaseToolAgent):
    TOOL_NAME = "subfinder"
    DEFAULT_TIMEOUT_SECONDS = 600

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._runtime_environment = self._load_runtime_environment()
        self._active_process: subprocess.Popen[str] | None = None
        self._lifecycle_status = "AGENT_READY"
        self._telemetry_hook: Callable[[dict[str, Any]], None] | None = None
        self._last_preflight: dict[str, Any] = {}

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def register_telemetry_hook(self, hook: Callable[[dict[str, Any]], None]) -> None:
        self._telemetry_hook = hook

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        binary = str(opts.get("binary_path") or opts.get("binary") or "subfinder")
        cmd = [binary, "-d", target, "-silent", "-json"]

        # Passive-only profile: do not enable active mode.
        if opts.get("all_sources", True):
            cmd.append("-all")
        if opts.get("recursive"):
            cmd.append("-recursive")

        threads = int(opts.get("threads", 50))
        cmd += ["-t", str(max(1, threads))]

        timeout_minutes = int(opts.get("timeout", 30))
        cmd += ["-timeout", str(max(1, timeout_minutes))]

        sources = str(opts.get("sources", "")).strip()
        if sources:
            cmd += ["-sources", sources]

        provider_config = self._resolve_provider_config(opts)
        if provider_config and provider_config.exists():
            cmd += ["-pc", str(provider_config)]

        if opts.get("output_file"):
            cmd += ["-o", str(opts["output_file"])]

        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for raw_line in raw_output.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            registry = self._parse_subfinder_json_line(line)
            if registry is None:
                # Backward compatibility for legacy plain-text parsing in existing tests.
                if not line.startswith("{") and (line == target or line.endswith(f".{target}")):
                    findings.append(
                        {
                            "type": "subdomain",
                            "subdomain": line,
                            "value": line,
                            "target": target,
                            "severity": "info",
                            "confidence": 0.8,
                            "source_tool": self.TOOL_NAME,
                            "raw_evidence": line,
                            "context": {"source": "subfinder"},
                            "recommended_next_tools": ["dnsx"],
                            "recommended_next_actions": ["resolve_dns"],
                        }
                    )
                continue

            fqdn = registry.fqdn.lower()
            if not (fqdn == target.lower() or fqdn.endswith(f".{target.lower()}")):
                continue

            findings.append(
                {
                    "type": "subdomain",
                    "subdomain": registry.fqdn,
                    "value": registry.fqdn,
                    "target": target,
                    "severity": "info",
                    "confidence": 0.9,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": registry.raw_evidence,
                    "context": {
                        "fqdn": registry.fqdn,
                        "intel_origin": registry.intel_origin,
                        "resolved_ips": registry.resolved_ips,
                        "intel_registry": registry.model_dump(mode="json"),
                    },
                    "recommended_next_tools": ["dnsx"],
                    "recommended_next_actions": ["resolve_dns"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal_findings: list[dict[str, Any]] = []
        noise_findings: list[dict[str, Any]] = []
        known = self.load_memory()

        for item in findings:
            value = item["value"].lower()
            if f"{item['target'].lower()}|subdomain|{value}" in known:
                noise_findings.append(item)
                continue

            label = item["subdomain"].lower().split(".")[0]
            if any(keyword in label for keyword in _HIGH_SIGNAL_KEYWORDS):
                item["signal_reason"] = "high_signal_keyword"
                item["severity"] = "medium"
                signal_findings.append(item)
            elif any(keyword in label for keyword in _NOISE_KEYWORDS):
                item["noise_reason"] = "low_signal_keyword"
                noise_findings.append(item)
            else:
                signal_findings.append(item)

        return signal_findings, noise_findings

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        subdomains = [item["subdomain"] for item in signal]
        high_value = [
            item["subdomain"] for item in signal if item.get("signal_reason") == "high_signal_keyword"
        ]
        return {
            "next_agent": "dnsx",
            "action": "resolve_subdomains",
            "target": target,
            "input_subdomains": subdomains,
            "priority_subdomains": high_value,
            "instructions": (
                "Run dnsx on all discovered subdomains to verify DNS resolution and CNAME posture. "
                f"Priority targets: {', '.join(high_value[:5]) if high_value else 'none identified'}."
            ),
        }

    def start(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        self._lifecycle_status = "ENUMERATING"
        return self.execute(target=target, options=options, mission_id=mission_id)

    def stop(self) -> dict[str, Any]:
        stopped = False
        if self._active_process is not None and self._active_process.poll() is None:
            self._kill_process_group(self._active_process)  # type: ignore[arg-type]
            stopped = True
        self._active_process = None
        self._lifecycle_status = "AGENT_READY"
        return {
            "tool": self.TOOL_NAME,
            "stopped": stopped,
            "status": self._lifecycle_status,
        }

    def health_check(self) -> dict[str, Any]:
        preflight = self._preflight(command=["subfinder"], options={})
        healthy = bool(preflight.get("binary_available")) and bool(preflight.get("provider_config_available"))
        return {
            "tool": self.TOOL_NAME,
            "status": self._lifecycle_status,
            "healthy": healthy,
            "preflight": preflight,
        }

    def execute(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        opts = options or {}
        timeout_seconds = max(1, int(opts.get("timeout_seconds", self.DEFAULT_TIMEOUT_SECONDS)))
        max_discovery_cap = max(
            1,
            int(opts.get("max_discovery_cap", os.getenv("K1_SUBFINDER_MAX_DISCOVERY_CAP", "10000"))),
        )
        command = self.build_command(target, opts)
        preflight = self._preflight(command=command, options=opts)
        self._last_preflight = preflight

        telemetry_events: list[dict[str, Any]] = []
        telemetry_hook = opts.get("telemetry_hook") or self._telemetry_hook
        self._emit_telemetry(telemetry_events, "AGENT_STATUS", "AGENT_READY", telemetry_hook)

        if not preflight.get("binary_available", False):
            return self._build_failure_result(
                target=target,
                command=command,
                mission_id=mission_id,
                stderr=str(preflight.get("error", "subfinder binary unavailable")),
                preflight=preflight,
                telemetry=telemetry_events,
                status="failure",
            )

        if not preflight.get("provider_config_available", False):
            return self._build_failure_result(
                target=target,
                command=command,
                mission_id=mission_id,
                stderr="provider-config.yaml not found; passive source APIs are not configured",
                preflight=preflight,
                telemetry=telemetry_events,
                status="failure",
            )

        if preflight.get("require_sovereign_network") and not preflight.get("sovereign_network_ok"):
            return self._build_failure_result(
                target=target,
                command=command,
                mission_id=mission_id,
                stderr="Sovereign Network Layer not detected (VPN/Proxy unavailable)",
                preflight=preflight,
                telemetry=telemetry_events,
                status="failure",
            )

        started_at = datetime.now(UTC)
        monitor = ResourceMonitor()
        self._lifecycle_status = "ENUMERATING"
        self._emit_telemetry(telemetry_events, "AGENT_STATUS", "ENUMERATING", telemetry_hook)

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        stdout_chars = {"count": 0}
        stderr_chars = {"count": 0}
        discovery_counter = {"count": 0}
        discovery_started_monotonic = time.monotonic()
        cap_reached = {"value": False}
        stop_stream = threading.Event()

        status = "failure"
        exit_code = 127
        process: subprocess.Popen[str] | None = None
        kill_telemetry: dict[str, Any] = {}

        previous_sigterm = None
        sigterm_installed = False
        sigterm_requested = {"requested": False}

        def _on_stdout_line(line: str) -> None:
            registry = self._parse_subfinder_json_line(line)
            if registry is None:
                return
            discovery_counter["count"] += 1
            elapsed = max(0.001, time.monotonic() - discovery_started_monotonic)
            velocity = round(discovery_counter["count"] / elapsed, 4)
            self._emit_telemetry(telemetry_events, "DISCOVERY_VELOCITY", velocity, telemetry_hook)

            if self._is_high_interest_tld(registry.fqdn):
                self._emit_telemetry(
                    telemetry_events,
                    "EventLog",
                    f"HIGH_INTEREST_TLD:{registry.fqdn}",
                    telemetry_hook,
                )

            if discovery_counter["count"] >= max_discovery_cap:
                cap_reached["value"] = True
                stop_stream.set()
                if process is not None and process.poll() is None:
                    self._kill_process_group(process)  # type: ignore[arg-type]

        def _on_sigterm(_: int, __: Any) -> None:
            sigterm_requested["requested"] = True
            stop_stream.set()
            if process is not None and process.poll() is None:
                self._kill_process_group(process)  # type: ignore[arg-type]

        try:
            if threading.current_thread() is threading.main_thread():
                previous_sigterm = signal.getsignal(signal.SIGTERM)
                signal.signal(signal.SIGTERM, _on_sigterm)
                sigterm_installed = True

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
                start_new_session=True,
                bufsize=1,
            )
            self._active_process = process
            exit_code = -1

            stdout_thread = threading.Thread(
                target=self._consume_stream,
                args=(
                    process.stdout,
                    stdout_lines,
                    stdout_chars,
                    self.MAX_STDIO_CHARS,
                    _on_stdout_line,
                    stop_stream,
                ),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self._consume_stream,
                args=(
                    process.stderr,
                    stderr_lines,
                    stderr_chars,
                    self.MAX_STDIO_CHARS,
                    None,
                    stop_stream,
                ),
                daemon=True,
            )
            stdout_thread.start()
            stderr_thread.start()

            try:
                process.wait(timeout=timeout_seconds)
                exit_code = int(process.returncode or 0)
                status = "success" if exit_code == 0 else "failure"
            except subprocess.TimeoutExpired:
                status = "timeout"
                exit_code = 124
                stop_stream.set()
                kill_telemetry = self._kill_process_group(process)  # type: ignore[arg-type]

            stdout_thread.join(timeout=2.0)
            stderr_thread.join(timeout=2.0)

        except OSError as exc:
            status = "failure"
            exit_code = 127
            stderr_lines.append(str(exc))
        finally:
            self._active_process = None
            if process is not None and process.poll() is None:
                kill_telemetry = self._kill_process_group(process)  # type: ignore[arg-type]
            if sigterm_installed and previous_sigterm is not None:
                signal.signal(signal.SIGTERM, previous_sigterm)

        stdout = "".join(stdout_lines)[: self.MAX_STDIO_CHARS]
        stderr = "".join(stderr_lines)[: self.MAX_STDIO_CHARS]

        if cap_reached["value"]:
            status = "partial"
        if self._is_rate_limited(stdout, stderr):
            status = "cooldown"
            self._emit_telemetry(telemetry_events, "AGENT_STATUS", "COOLDOWN", telemetry_hook)
        if sigterm_requested["requested"] and status == "success":
            status = "cancelled"

        ended_at = datetime.now(UTC)
        runtime_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))
        resource_usage = monitor.finish()

        try:
            result = self.map_output(
                target=target,
                command=command,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                started_at=started_at,
                ended_at=ended_at,
                runtime_ms=runtime_ms,
                mission_id=mission_id,
                status=status,
                options=opts,
            )
            result = KaisonResult.model_validate(result)
        except Exception as exc:
            result = KaisonResult(
                mission_id=mission_id,
                source_agent=self.TOOL_NAME,
                status="failure",
                target_context={
                    "target": target,
                    "command": command,
                    "exit_code": exit_code,
                    "stderr": stderr[:4000],
                    "mapping_error": str(exc),
                },
                metadata=KaisonResultMetadata(
                    started_at=started_at,
                    ended_at=ended_at,
                    runtime_ms=runtime_ms,
                ),
                findings=[],
            )

        enriched_context = dict(result.target_context)
        enriched_context["resource_usage"] = resource_usage
        enriched_context["preflight"] = preflight
        enriched_context["telemetry"] = telemetry_events
        enriched_context["discovery_count"] = discovery_counter["count"]
        enriched_context["max_discovery_cap"] = max_discovery_cap
        enriched_context["cap_reached"] = cap_reached["value"]
        if kill_telemetry:
            enriched_context["process_termination"] = kill_telemetry

        result = result.model_copy(update={"target_context": enriched_context, "status": status})
        deduped_findings = self._filter_duplicates(target, result.findings)
        if len(deduped_findings) != len(result.findings):
            adjusted_status = "partial" if result.status == "success" else result.status
            result = result.model_copy(update={"status": adjusted_status, "findings": deduped_findings})

        self._record_scan_history(
            target=target,
            command=command,
            status=result.status,
            findings=deduped_findings,
            started_at=started_at,
            runtime_ms=runtime_ms,
            handoff_report=result.target_context.get("handoff_report"),
        )
        self._record_findings_correlation(
            target=target,
            findings=deduped_findings,
            started_at=started_at,
        )
        self._persist_memory(target, deduped_findings)
        self._lifecycle_status = "AGENT_READY"
        self._emit_telemetry(telemetry_events, "AGENT_STATUS", "AGENT_READY", telemetry_hook)
        return result

    def _build_failure_result(
        self,
        *,
        target: str,
        command: list[str],
        mission_id: str,
        stderr: str,
        preflight: dict[str, Any],
        telemetry: list[dict[str, Any]],
        status: str,
    ) -> KaisonResult:
        started_at = datetime.now(UTC)
        ended_at = datetime.now(UTC)
        result = KaisonResult(
            mission_id=mission_id,
            source_agent=self.TOOL_NAME,
            status=status,
            target_context={
                "target": target,
                "command": command,
                "exit_code": 127,
                "stderr": stderr[:4000],
                "preflight": preflight,
                "telemetry": telemetry,
            },
            metadata=KaisonResultMetadata(
                started_at=started_at,
                ended_at=ended_at,
                runtime_ms=0,
            ),
            findings=[],
        )
        self._lifecycle_status = "AGENT_READY"
        return result

    def _preflight(self, *, command: list[str], options: dict[str, Any]) -> dict[str, Any]:
        binary = command[0] if command else "subfinder"
        binary_path = shutil.which(binary) if not Path(binary).is_file() else str(Path(binary))
        version = ""

        if binary_path:
            try:
                proc = subprocess.run(
                    [binary_path, "-version"],
                    capture_output=True,
                    text=True,
                    timeout=8,
                )
                version = (proc.stdout or proc.stderr or "").strip()
            except (OSError, subprocess.TimeoutExpired):
                version = ""

        provider_config = self._resolve_provider_config(options)
        provider_available = bool(provider_config and provider_config.exists())
        provider_key_status = self._provider_key_status(provider_config) if provider_available else {}

        require_sovereign = bool(options.get("require_sovereign_network")) or os.getenv(
            "K1_REQUIRE_SOVEREIGN_NETWORK", "false"
        ).strip().lower() in {"1", "true", "yes", "on"}
        sovereign_ok = bool(self._runtime_environment.get("vpn_up_interfaces")) or bool(
            self._runtime_environment.get("proxychains_enabled")
        )

        return {
            "binary_requested": binary,
            "binary_path": binary_path,
            "binary_available": bool(binary_path),
            "version": version,
            "provider_config_path": str(provider_config) if provider_config else None,
            "provider_config_available": provider_available,
            "provider_keys": provider_key_status,
            "provider_keys_active": all(provider_key_status.values()) if provider_key_status else False,
            "runtime_environment": self._runtime_environment,
            "require_sovereign_network": require_sovereign,
            "sovereign_network_ok": sovereign_ok,
            "error": None if binary_path else "subfinder binary not found in PATH",
        }

    def _resolve_provider_config(self, options: dict[str, Any]) -> Path | None:
        explicit = str(options.get("provider_config", "")).strip()
        if explicit:
            return Path(explicit).expanduser()

        env_path = os.getenv("SUBFINDER_PROVIDER_CONFIG", "").strip()
        if env_path:
            return Path(env_path).expanduser()

        candidates = [
            Path.home() / ".config" / "subfinder" / "provider-config.yaml",
            Path.home() / ".config" / "subfinder" / "provider-config.yml",
            Path.home() / ".subfinder" / "provider-config.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    @staticmethod
    def _provider_key_status(provider_config: Path | None) -> dict[str, bool]:
        if provider_config is None or not provider_config.exists():
            return {"chaos": False, "github": False, "shodan": False}
        try:
            content = provider_config.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            return {"chaos": False, "github": False, "shodan": False}
        return {
            "chaos": "chaos" in content,
            "github": "github" in content,
            "shodan": "shodan" in content,
        }

    def _parse_subfinder_json_line(self, line: str) -> IntelRegistry | None:
        token = line.strip()
        if not token or not token.startswith("{"):
            return None
        try:
            raw = SubfinderRawRecord.model_validate_json(token)
            return IntelRegistry.from_raw(raw)
        except ValidationError:
            return None
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _consume_stream(
        stream: Any,
        collector: list[str],
        collector_counter: dict[str, int],
        collector_limit: int,
        on_line: Callable[[str], None] | None,
        stop_event: threading.Event,
    ) -> None:
        if stream is None:
            return
        try:
            for line in iter(stream.readline, ""):
                if line == "" or stop_event.is_set():
                    break
                if collector_counter["count"] < collector_limit:
                    remaining = collector_limit - collector_counter["count"]
                    clipped = line[:remaining]
                    collector.append(clipped)
                    collector_counter["count"] += len(clipped)
                if on_line is not None:
                    on_line(line)
        finally:
            try:
                stream.close()
            except Exception:
                pass

    @staticmethod
    def _emit_telemetry(
        sink: list[dict[str, Any]],
        key: str,
        value: Any,
        hook: Any | None,
    ) -> None:
        event = {
            "key": key,
            "value": value,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        sink.append(event)
        if callable(hook):
            try:
                hook(event)
            except Exception:
                return

    @staticmethod
    def _is_rate_limited(stdout: str, stderr: str) -> bool:
        return _RATE_LIMIT_RE.search(f"{stdout}\n{stderr}") is not None

    @staticmethod
    def _is_high_interest_tld(fqdn: str) -> bool:
        parts = fqdn.lower().split(".")
        if len(parts) < 2:
            return False
        return parts[-1] in _HIGH_INTEREST_TLDS

    def _load_runtime_environment(self) -> dict[str, Any]:
        interfaces = os.getenv("K1_VPN_INTERFACES", "").strip()
        if interfaces:
            vpn_interfaces = tuple(item.strip() for item in interfaces.split(",") if item.strip())
        else:
            vpn_interfaces = _DEFAULT_VPN_INTERFACES
        proxy_chain = os.getenv("K1_PROXYCHAINS_FILE", "").strip()
        proxy_enabled = os.getenv("K1_USE_PROXIES", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        return {
            "vpn_interfaces": vpn_interfaces,
            "vpn_up_interfaces": self._detect_up_interfaces(vpn_interfaces),
            "proxychains_file": proxy_chain or None,
            "proxychains_enabled": proxy_enabled,
        }

    @staticmethod
    def _detect_up_interfaces(interfaces: tuple[str, ...]) -> list[str]:
        up_interfaces: list[str] = []
        for interface in interfaces:
            state_path = Path("/sys/class/net") / interface / "operstate"
            if not state_path.exists():
                continue
            try:
                state = state_path.read_text(encoding="utf-8").strip().lower()
            except OSError:
                continue
            if state == "up":
                up_interfaces.append(interface)
        return up_interfaces


class ResourceMonitor:
    """Lightweight CPU/wall telemetry for agent-local execution wrapper."""

    def __init__(self) -> None:
        self._start_monotonic = time.monotonic()
        self._start_cpu = time.process_time()

    def finish(self) -> dict[str, Any]:
        wall_s = max(0.0, time.monotonic() - self._start_monotonic)
        cpu_s = max(0.0, time.process_time() - self._start_cpu)
        return {
            "wall_time_s": round(wall_s, 6),
            "cpu_time_s": round(cpu_s, 6),
        }
