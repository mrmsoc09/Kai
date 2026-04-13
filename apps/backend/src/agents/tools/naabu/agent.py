from __future__ import annotations

import ipaddress
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
from urllib.parse import urlparse

from pydantic import ValidationError

from apps.backend.src.core.protocol import KaisonResult, KaisonResultMetadata

from ..base_tool_agent import BaseToolAgent
from .schemas import NaabuRawRecord, PortRegistry

_RATE_LIMIT_RE = re.compile(
    r"(429|rate[\s_-]*limit|too many requests|quota exceeded|request limit)",
    re.IGNORECASE,
)
_DEFAULT_VPN_INTERFACES = ("tun0", "wg0", "vpn0")
_DEFAULT_RATE = 1000
_DEFAULT_RETRIES = 2
_DEFAULT_FULL_SCAN_COOLDOWN_SECONDS = 4 * 60 * 60
_WEB_PORTS = {
    80,
    81,
    88,
    443,
    591,
    593,
    8000,
    8080,
    8081,
    8443,
    8888,
    3000,
    5000,
    9000,
    9443,
    10000,
}


class NaabuAgent(BaseToolAgent):
    TOOL_NAME = "naabu"
    DEFAULT_TIMEOUT_SECONDS = 420

    # Backward-compatible defaults used in existing tests.
    BBP_WEB_PORTS = "80,443,8080,8443,9000,9090,9200,9443,10000"
    ALL_WEB_PORTS = "80,443,8080,8443,9000,9090,9200,9443,10000,3000,5000,8000,8888,9001"

    PORT_SERVICE_MAP = {
        22: "ssh",
        53: "dns",
        80: "http",
        443: "https",
        445: "smb",
        1433: "mssql",
        1521: "oracle",
        2375: "docker-api",
        2376: "docker-api-tls",
        3306: "mysql",
        3389: "rdp",
        5432: "postgresql",
        5601: "kibana",
        6379: "redis",
        8080: "http-alt",
        8443: "https-alt",
        9000: "php-fpm",
        9200: "elasticsearch",
        9300: "elasticsearch",
        10000: "webmin",
        27017: "mongodb",
    }

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._runtime_environment = self._load_runtime_environment()
        self._active_process: subprocess.Popen[str] | None = None
        self._lifecycle_status = "ANALYSIS_IDLE"
        self._telemetry_hook: Callable[[dict[str, Any]], None] | None = None
        self._last_preflight: dict[str, Any] = {}
        self._scan_state_path = self.memory_dir / "scan_state.json"
        self._scan_state = self._load_scan_state()

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def register_telemetry_hook(self, hook: Callable[[dict[str, Any]], None]) -> None:
        self._telemetry_hook = hook

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        binary = str(opts.get("binary_path") or opts.get("binary") or "naabu")
        listener_mode = bool(opts.get("listener_mode"))

        command_body: list[str] = [binary, "-silent", "-json"]

        scan_mode = self._resolve_scan_mode(opts)
        if scan_mode == "full":
            command_body += ["-p", "-"]
        elif scan_mode == "top1000":
            command_body += ["-top-ports", "1000"]
        else:
            ports = str(opts.get("ports") or self.BBP_WEB_PORTS)
            command_body += ["-p", ports]

        desired_scan_type = str(opts.get("scan_type", "")).strip().lower()
        raw_socket_ok = self._has_raw_socket_access(binary)
        if desired_scan_type in {"s", "syn"}:
            use_syn = True
        elif desired_scan_type in {"c", "connect"}:
            use_syn = False
        else:
            use_syn = raw_socket_ok

        if use_syn and not raw_socket_ok and bool(opts.get("use_sudo")):
            command: list[str] = ["sudo", "-n"] + command_body
        else:
            command = list(command_body)

        command += ["-scan-type", "s" if use_syn else "c"]

        if bool(opts.get("exclude_cdn", True)):
            command.append("-exclude-cdn")

        rate_limit = int(opts.get("rate_limit", _DEFAULT_RATE))
        retries = int(opts.get("retries", _DEFAULT_RETRIES))
        command += ["-rate", str(max(1, rate_limit))]
        command += ["-retries", str(max(0, retries))]

        if not listener_mode:
            input_file = str(opts.get("input_file", "")).strip()
            if input_file:
                command += ["-list", input_file]
            else:
                command += ["-host", target]

        if opts.get("output_file"):
            command += ["-o", str(opts["output_file"])]

        return command

    def build_input_stream(self, options: dict[str, Any] | None = None) -> str | None:
        opts = options or {}
        if not bool(opts.get("listener_mode")):
            return None

        input_source = opts.get("input_data", [])
        if isinstance(input_source, str):
            return input_source
        if isinstance(input_source, list):
            return "\n".join(str(item).strip() for item in input_source if str(item).strip())
        return None

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        for raw_line in raw_output.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            registry = self._parse_registry_line(line, target_scope=target)
            if registry is None:
                continue

            service_hint = registry.service_hint
            is_web_port = registry.is_web_port
            port_number = registry.port_number
            next_tools = ["httpx_probe"] if is_web_port else ["nmap"]
            next_actions = ["service_validation"] if is_web_port else ["service_enumeration"]

            finding = {
                "type": "port",
                "host": registry.target_host or registry.target_ip,
                "ip": registry.target_ip,
                "port": str(port_number),
                "protocol": registry.proto_type,
                "value": f"{registry.target_ip}:{port_number}/{registry.proto_type}",
                "target": target,
                "severity": "info",
                "confidence": 0.92,
                "service": service_hint,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": registry.raw_evidence,
                "context": {
                    "port_registry": registry.model_dump(mode="json"),
                    "target_ip": registry.target_ip,
                    "port_number": port_number,
                    "proto_type": registry.proto_type,
                    "service_hint": service_hint,
                    "is_web_port": is_web_port,
                },
                "recommended_next_tools": next_tools,
                "recommended_next_actions": next_actions,
            }
            findings.append(finding)

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal_items: list[dict[str, Any]] = []
        noise_items: list[dict[str, Any]] = []
        known = self.load_memory()

        for item in findings:
            value = str(item.get("value", "")).lower()
            target = str(item.get("target", "")).lower()
            if f"{target}|port|{value}" in known:
                noise_items.append(item)
                continue

            service_hint = str(item.get("context", {}).get("service_hint", "unknown")).lower()
            if service_hint not in {"unknown", "http", "https", "http-alt", "https-alt"}:
                item["signal_reason"] = "high_risk_service"
                item["severity"] = "medium"

            signal_items.append(item)

        return signal_items, noise_items

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        web_targets: list[str] = []
        non_web_targets: list[str] = []

        for item in signal:
            value = str(item.get("value", "")).strip()
            context = item.get("context", {})
            if bool(context.get("is_web_port")):
                web_targets.append(value)
            else:
                non_web_targets.append(value)

        if web_targets:
            return {
                "next_agent": "httpx_probe",
                "fallback_agent": "nmap",
                "action": "probe_web_services",
                "target": target,
                "input_targets": web_targets,
                "secondary_targets": non_web_targets,
                "instructions": (
                    f"Naabu discovered {len(signal)} open ports. "
                    f"Route {len(web_targets)} web-exposed targets to httpx_probe for service validation. "
                    "Use nmap for deeper service fingerprinting on non-web ports."
                ),
            }

        return {
            "next_agent": "nmap",
            "action": "service_enumeration",
            "target": target,
            "input_targets": non_web_targets,
            "instructions": (
                f"Naabu discovered {len(non_web_targets)} non-web ports. "
                "Run nmap service fingerprinting to identify exposed services and versions."
            ),
        }

    def start(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        self._lifecycle_status = "PROBING_TARGETS"
        return self.execute(target=target, options=options, mission_id=mission_id)

    def stop(self) -> dict[str, Any]:
        stopped = False
        if self._active_process is not None and self._active_process.poll() is None:
            self._kill_process_group(self._active_process)  # type: ignore[arg-type]
            stopped = True
        self._active_process = None
        self._lifecycle_status = "ANALYSIS_IDLE"
        return {
            "tool": self.TOOL_NAME,
            "stopped": stopped,
            "status": self._lifecycle_status,
        }

    def health_check(self) -> dict[str, Any]:
        preflight = self._preflight(command=["naabu"], options={})
        healthy = bool(preflight.get("binary_available"))
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
        command = self.build_command(target, opts)
        preflight = self._preflight(command=command, options=opts)
        self._last_preflight = preflight

        telemetry_events: list[dict[str, Any]] = []
        telemetry_hook = opts.get("telemetry_hook") or self._telemetry_hook
        self._emit_telemetry(telemetry_events, "AGENT_STATUS", "PROBING_TARGETS", telemetry_hook)

        if not preflight.get("binary_available", False):
            return self._build_failure_result(
                target=target,
                command=command,
                mission_id=mission_id,
                stderr=str(preflight.get("error", "naabu binary unavailable")),
                preflight=preflight,
                telemetry=telemetry_events,
                status="failure",
            )

        if preflight.get("require_sovereign_network") and not preflight.get("sovereign_network_ok"):
            return self._build_failure_result(
                target=target,
                command=command,
                mission_id=mission_id,
                stderr="Sovereign Network Layer not detected (SOCKS5/VPN unavailable)",
                preflight=preflight,
                telemetry=telemetry_events,
                status="failure",
            )

        if preflight.get("syn_scan_without_vpn"):
            return self._build_failure_result(
                target=target,
                command=command,
                mission_id=mission_id,
                stderr=(
                    "SYN scan blocked: raw socket scans require active VPN tunnel "
                    "to avoid Sovereign Network bypass"
                ),
                preflight=preflight,
                telemetry=telemetry_events,
                status="failure",
            )

        scope_key = self._resolve_scan_scope_key(target=target, options=opts)
        cooldown_state = self._check_high_intensity_cooldown(scope_key=scope_key, options=opts)
        if cooldown_state["blocked"]:
            return self._build_failure_result(
                target=target,
                command=command,
                mission_id=mission_id,
                stderr=(
                    "Cooldown active for high-intensity scan on scope "
                    f"{scope_key}; last scanned at {cooldown_state.get('last_scanned', 'unknown')}"
                ),
                preflight=preflight,
                telemetry=telemetry_events,
                status="cooldown",
            )

        started_at = datetime.now(UTC)
        monitor = ResourceMonitor()
        self._lifecycle_status = "PROBING_TARGETS"

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        stdout_chars = {"count": 0}
        stderr_chars = {"count": 0}
        stop_stream = threading.Event()

        open_port_total = {"count": 0}
        seen_ports: set[str] = set()
        seen_hosts: set[str] = set()

        status = "failure"
        exit_code = 127
        process: subprocess.Popen[str] | None = None
        kill_telemetry: dict[str, Any] = {}

        previous_sigterm = None
        sigterm_installed = False
        sigterm_requested = {"requested": False}
        start_monotonic = time.monotonic()

        def _on_stdout_line(line: str) -> None:
            registry = self._parse_registry_line(line, target_scope=target)
            if registry is None:
                return

            port_key = f"{registry.target_ip}:{registry.port_number}/{registry.proto_type}"
            if port_key not in seen_ports:
                seen_ports.add(port_key)
                open_port_total["count"] += 1
                self._emit_telemetry(
                    telemetry_events,
                    "OPEN_PORTS_DISCOVERED",
                    open_port_total["count"],
                    telemetry_hook,
                )
                self._emit_telemetry(
                    telemetry_events,
                    "EventLog",
                    f"PORT_BEACON:{registry.target_ip}:{registry.port_number}",
                    telemetry_hook,
                )

            if registry.target_ip not in seen_hosts:
                seen_hosts.add(registry.target_ip)
                elapsed = max(0.001, time.monotonic() - start_monotonic)
                velocity = len(seen_hosts) / elapsed
                self._emit_telemetry(
                    telemetry_events,
                    "SCAN_VELOCITY",
                    round(velocity, 3),
                    telemetry_hook,
                )

        def _on_sigterm(_: int, __: Any) -> None:
            sigterm_requested["requested"] = True
            stop_stream.set()
            if process is not None and process.poll() is None:
                self._kill_process_group(process)  # type: ignore[arg-type]

        try:
            stdin_stream = subprocess.PIPE if bool(opts.get("listener_mode")) else None
            process = subprocess.Popen(
                command,
                stdin=stdin_stream,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
                start_new_session=True,
                bufsize=1,
            )
            self._active_process = process
            exit_code = -1

            if threading.current_thread() is threading.main_thread():
                previous_sigterm = signal.getsignal(signal.SIGTERM)
                signal.signal(signal.SIGTERM, _on_sigterm)
                sigterm_installed = True

            input_stream = self.build_input_stream(opts)
            if input_stream is not None and process.stdin is not None:
                try:
                    process.stdin.write(input_stream + ("\n" if not input_stream.endswith("\n") else ""))
                    process.stdin.flush()
                except Exception:
                    pass
                finally:
                    try:
                        process.stdin.close()
                    except Exception:
                        pass

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
        enriched_context["open_ports_discovered"] = open_port_total["count"]
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

        if status == "success" and self._is_high_intensity_scan(opts):
            self._record_scan_state(scope_key=scope_key, options=opts, open_ports=open_port_total["count"])

        self._lifecycle_status = "ANALYSIS_IDLE"
        self._emit_telemetry(telemetry_events, "AGENT_STATUS", "ANALYSIS_IDLE", telemetry_hook)
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
        self._lifecycle_status = "ANALYSIS_IDLE"
        return result

    def _preflight(self, *, command: list[str], options: dict[str, Any]) -> dict[str, Any]:
        binary = self._extract_binary_from_command(command)
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

        require_sovereign = bool(options.get("require_sovereign_network")) or os.getenv(
            "K1_REQUIRE_SOVEREIGN_NETWORK", "false"
        ).strip().lower() in {"1", "true", "yes", "on"}
        vpn_up = bool(self._runtime_environment.get("vpn_up_interfaces"))
        proxy_enabled = bool(self._runtime_environment.get("proxychains_enabled"))
        sovereign_ok = vpn_up or proxy_enabled

        is_syn_scan = self._command_uses_syn_scan(command)
        syn_without_vpn = require_sovereign and is_syn_scan and not vpn_up

        return {
            "binary_requested": binary,
            "binary_path": binary_path,
            "binary_available": bool(binary_path),
            "version": version,
            "runtime_environment": self._runtime_environment,
            "require_sovereign_network": require_sovereign,
            "sovereign_network_ok": sovereign_ok,
            "syn_scan_without_vpn": syn_without_vpn,
            "error": None if binary_path else "naabu binary not found in PATH",
        }

    @staticmethod
    def _extract_binary_from_command(command: list[str]) -> str:
        if not command:
            return "naabu"
        if command[0] == "sudo" and len(command) >= 3:
            return command[2]
        return command[0]

    @staticmethod
    def _command_uses_syn_scan(command: list[str]) -> bool:
        try:
            idx = command.index("-scan-type")
            if idx + 1 < len(command):
                return command[idx + 1].strip().lower().startswith("s")
        except ValueError:
            return False
        return False

    def _parse_registry_line(self, line: str, *, target_scope: str | None) -> PortRegistry | None:
        token = line.strip()
        if not token:
            return None

        raw: NaabuRawRecord | None = None
        if token.startswith("{"):
            try:
                raw = NaabuRawRecord.model_validate_json(token)
            except (ValidationError, json.JSONDecodeError):
                raw = None

        if raw is None:
            # legacy plain format host:port
            first = token.split()[0]
            if ":" in first:
                host_token, port_token = first.rsplit(":", 1)
                if port_token.isdigit():
                    host = host_token.strip()
                    ip_candidate: str | None = None
                    try:
                        ipaddress.ip_address(host)
                        ip_candidate = host
                    except ValueError:
                        ip_candidate = None
                    raw = NaabuRawRecord(
                        ip=ip_candidate,
                        host=None if ip_candidate else host,
                        port=int(port_token),
                        protocol="tcp",
                    )

        if raw is None and token.startswith(("http://", "https://")):
            # compatibility path for depth-contract tests
            parsed = urlparse(token)
            host = parsed.hostname or ""
            if host:
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
                ip_candidate: str | None = None
                try:
                    ipaddress.ip_address(host)
                    ip_candidate = host
                except ValueError:
                    ip_candidate = None
                raw = NaabuRawRecord(
                    ip=ip_candidate,
                    host=None if ip_candidate else host,
                    port=port,
                    protocol="tcp",
                )

        if raw is None:
            return None

        port_number = int(raw.port)
        service_hint = self.PORT_SERVICE_MAP.get(port_number, "unknown")
        is_web_port = port_number in _WEB_PORTS or service_hint in {
            "http",
            "https",
            "http-alt",
            "https-alt",
        }

        try:
            return PortRegistry.from_raw(
                raw,
                target_scope=target_scope,
                service_hint=service_hint,
                is_web_port=is_web_port,
            )
        except ValidationError:
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
    def _resolve_scan_mode(options: dict[str, Any]) -> str:
        if bool(options.get("full_scan")):
            return "full"

        profile = str(options.get("scan_profile", "")).strip().lower()
        if profile in {"full", "all_ports", "deep"}:
            return "full"
        if profile in {"top1000", "top-1000", "top"}:
            return "top1000"

        priority = str(options.get("priority", "")).strip().lower()
        if priority in {"high", "critical", "deep"}:
            return "full"
        if priority in {"standard", "normal", "balanced"}:
            return "top1000"

        return "bbp"

    @staticmethod
    def _has_raw_socket_access(binary: str) -> bool:
        if os.geteuid() == 0:
            return True

        binary_path = shutil.which(binary)
        if not binary_path:
            return False

        getcap_path = shutil.which("getcap")
        if not getcap_path:
            return False

        try:
            proc = subprocess.run(
                [getcap_path, binary_path],
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            lowered = output.lower()
            return "cap_net_raw" in lowered and "=ep" in lowered
        except (OSError, subprocess.TimeoutExpired):
            return False

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

    def _resolve_scan_scope_key(self, *, target: str, options: dict[str, Any]) -> str:
        override = str(options.get("scan_scope_key", "")).strip().lower()
        if override:
            return override

        token = target.strip().lower()
        try:
            if "/" in token:
                network = ipaddress.ip_network(token, strict=False)
                return str(network)
        except ValueError:
            pass

        return token

    @staticmethod
    def _is_high_intensity_scan(options: dict[str, Any]) -> bool:
        return NaabuAgent._resolve_scan_mode(options) == "full"

    def _check_high_intensity_cooldown(
        self,
        *,
        scope_key: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        if not self._is_high_intensity_scan(options):
            return {"blocked": False}

        cooldown_seconds = int(options.get("high_intensity_cooldown_seconds", _DEFAULT_FULL_SCAN_COOLDOWN_SECONDS))
        scope = self._scan_state.get("scopes", {}).get(scope_key, {})
        last_scanned = str(scope.get("last_scanned", "")).strip()
        if not last_scanned:
            return {"blocked": False}

        try:
            last_dt = datetime.fromisoformat(last_scanned)
        except ValueError:
            return {"blocked": False}

        delta_seconds = (datetime.now(UTC) - last_dt).total_seconds()
        if delta_seconds < cooldown_seconds:
            return {
                "blocked": True,
                "last_scanned": last_scanned,
                "remaining_seconds": int(cooldown_seconds - delta_seconds),
            }

        return {"blocked": False}

    def _record_scan_state(self, *, scope_key: str, options: dict[str, Any], open_ports: int) -> None:
        scopes = self._scan_state.setdefault("scopes", {})
        scopes[scope_key] = {
            "last_scanned": datetime.now(UTC).isoformat(),
            "scan_mode": self._resolve_scan_mode(options),
            "open_ports": int(open_ports),
        }
        self._save_scan_state()

    def _load_scan_state(self) -> dict[str, Any]:
        if not self._scan_state_path.exists():
            return {"scopes": {}}

        try:
            payload = json.loads(self._scan_state_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("scopes"), dict):
                return payload
        except (OSError, json.JSONDecodeError):
            pass

        return {"scopes": {}}

    def _save_scan_state(self) -> None:
        try:
            self._scan_state_path.write_text(
                json.dumps(self._scan_state, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
        except OSError:
            return


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
