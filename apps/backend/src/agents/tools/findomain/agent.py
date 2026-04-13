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
from apps.backend.src.core.secret_manager import SecretManagerError, get_secret_manager

from ..base_tool_agent import BaseToolAgent
from .schemas import DiscoveryRegistry

_HIGH_VALUE_KEYWORDS = {
    "admin",
    "api",
    "dev",
    "staging",
    "internal",
    "backend",
    "portal",
    "dashboard",
    "jenkins",
    "grafana",
}
_RATE_LIMIT_RE = re.compile(
    r"(429|rate[\s_-]*limit|too many requests|quota exceeded|api.*limit)",
    re.IGNORECASE,
)
_DEFAULT_VPN_INTERFACES = ("tun0", "wg0", "vpn0")
_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")


class FindomainAgent(BaseToolAgent):
    TOOL_NAME = "findomain"
    DEFAULT_TIMEOUT_SECONDS = 300

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._runtime_environment = self._load_runtime_environment()
        self._active_process: subprocess.Popen[str] | None = None
        self._lifecycle_status = "IDLE"
        self._telemetry_hook: Callable[[dict[str, Any]], None] | None = None

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def register_telemetry_hook(self, hook: Callable[[dict[str, Any]], None]) -> None:
        self._telemetry_hook = hook

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        cmd = ["findomain", "--target", target, "--quiet", "--json"]

        if bool(opts.get("resolved", False)):
            cmd.append("--resolved")
        if bool(opts.get("http_status", False)):
            cmd.append("--http-status")

        threads = self._resolve_threads(opts)
        cmd += ["--threads", str(threads)]

        if opts.get("output_file"):
            cmd += ["--output", str(opts["output_file"])]

        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        seen: set[str] = set()

        for line in raw_output.splitlines():
            token = line.strip()
            if not token:
                continue

            record = self._parse_json_record(token, target) or self._parse_plain_record(token, target)
            if record is None:
                continue

            value = record.discovered_domain
            if value in seen:
                continue
            seen.add(value)

            findings.append(
                {
                    "type": "subdomain",
                    "value": value,
                    "target": target,
                    "severity": "info",
                    "confidence": 0.82,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": line,
                    "context": {
                        "source": "passive_findomain",
                        "discovery_registry": record.model_dump(mode="json"),
                        "resolved_ips": record.resolved_ips,
                        "http_status": record.http_status,
                    },
                    "recommended_next_tools": ["dnsx", "httpx_probe"],
                    "recommended_next_actions": ["resolve_dns", "probe_http"],
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
            target = str(finding.get("target", "")).lower()
            if f"{target}|subdomain|{value}" in known:
                noise.append(finding)
                continue

            if any(token in value for token in _HIGH_VALUE_KEYWORDS):
                finding["severity"] = "medium"
                finding["confidence"] = 0.9
            signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        high_value = [
            item for item in signal if str(item.get("severity", "")).lower() in {"medium", "high", "critical"}
        ]
        return {
            "next_agents": ["dnsx", "httpx_probe"],
            "next_agent": "dnsx",
            "action": "resolve_subdomains",
            "target": target,
            "input_subdomains": [s.get("value") for s in signal if s.get("value")],
            "priority_targets": [f["value"] for f in high_value[:20]],
            "operator_summary": (
                f"Findomain discovered {len(signal)} unique subdomains for {target}. "
                "Route to dnsx/httpx for validation and service discovery."
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
        self._lifecycle_status = "IDLE"
        return {"tool": self.TOOL_NAME, "stopped": stopped, "status": self._lifecycle_status}

    def health_check(self) -> dict[str, Any]:
        binary_path = shutil.which("findomain")
        return {
            "tool": self.TOOL_NAME,
            "status": self._lifecycle_status,
            "healthy": bool(binary_path),
            "binary_path": binary_path,
        }

    def execute(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        opts = dict(options or {})
        timeout_seconds = max(1, int(opts.get("timeout_seconds", self.DEFAULT_TIMEOUT_SECONDS)))
        telemetry_events: list[dict[str, Any]] = []
        telemetry_hook = opts.get("telemetry_hook") or self._telemetry_hook
        self._emit_telemetry(telemetry_events, "AGENT_STATUS", "ENUMERATING", telemetry_hook)

        precheck = self._opsec_precheck(opts)
        if precheck["blocked"]:
            return self._build_failure_result(
                target=target,
                mission_id=mission_id,
                command=["findomain"],
                stderr=precheck["reason"],
                telemetry=telemetry_events,
                status="failure",
            )

        targets = self._resolve_targets(target, opts)
        started_at = datetime.now(UTC)
        monitor = ResourceMonitor()
        stdout_buffer: list[str] = []
        stderr_buffer: list[str] = []
        status = "success"

        unique_subdomains: set[str] = set()
        resolved_hosts = 0

        for entry in targets:
            command = self.build_command(entry, opts)
            process: subprocess.Popen[str] | None = None
            stop_stream = threading.Event()
            stdout_lines: list[str] = []
            stderr_lines: list[str] = []
            stdout_chars = {"count": 0}
            stderr_chars = {"count": 0}

            def _on_stdout_line(line: str) -> None:
                nonlocal resolved_hosts
                parsed = self.parse_output(line, entry)
                for finding in parsed:
                    value = str(finding.get("value", "")).strip().lower()
                    if not value:
                        continue
                    if value not in unique_subdomains:
                        unique_subdomains.add(value)
                        total = len(unique_subdomains)
                        self._emit_telemetry(telemetry_events, "UNIQUE_SUBDOMAINS", total, telemetry_hook)
                        if total % 10 == 0:
                            self._emit_telemetry(
                                telemetry_events,
                                "EventLog",
                                f"DIGITAL_RAIN:GOLD_TINT:{total}",
                                telemetry_hook,
                            )

                    has_ip = bool(finding.get("context", {}).get("resolved_ips"))
                    if has_ip:
                        resolved_hosts += 1
                        self._emit_telemetry(telemetry_events, "RESOLVED_HOSTS", resolved_hosts, telemetry_hook)

            previous_sigterm = None
            sigterm_installed = False

            def _on_sigterm(_: int, __: Any) -> None:
                stop_stream.set()
                if process is not None and process.poll() is None:
                    self._kill_process_group(process)  # type: ignore[arg-type]

            try:
                env = os.environ.copy()
                self._inject_secret_manager_env(env)
                proxy = self._resolve_proxy(opts)
                if proxy:
                    env["HTTP_PROXY"] = proxy
                    env["HTTPS_PROXY"] = proxy
                    env["ALL_PROXY"] = proxy

                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=False,
                    start_new_session=True,
                    bufsize=1,
                    env=env,
                )
                self._active_process = process

                if threading.current_thread() is threading.main_thread():
                    previous_sigterm = signal.getsignal(signal.SIGTERM)
                    signal.signal(signal.SIGTERM, _on_sigterm)
                    sigterm_installed = True

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
                    if int(process.returncode or 0) != 0:
                        status = "failure"
                except subprocess.TimeoutExpired:
                    status = "timeout"
                    stop_stream.set()
                    self._kill_process_group(process)  # type: ignore[arg-type]

                stdout_thread.join(timeout=2.0)
                stderr_thread.join(timeout=2.0)

            except OSError as exc:
                status = "failure"
                stderr_lines.append(str(exc))
            finally:
                self._active_process = None
                if process is not None and process.poll() is None:
                    self._kill_process_group(process)  # type: ignore[arg-type]
                if sigterm_installed and previous_sigterm is not None:
                    signal.signal(signal.SIGTERM, previous_sigterm)

            stdout_buffer.extend(stdout_lines)
            stderr_buffer.extend(stderr_lines)

        stdout = "".join(stdout_buffer)[: self.MAX_STDIO_CHARS]
        stderr = "".join(stderr_buffer)[: self.MAX_STDIO_CHARS]

        if self._is_rate_limited(stdout, stderr):
            status = "cooldown"
            self._emit_telemetry(telemetry_events, "AGENT_STATUS", "COOLDOWN", telemetry_hook)

        ended_at = datetime.now(UTC)
        runtime_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))
        resource_usage = monitor.finish()
        command_repr = ["findomain", "--json", "<batch>"] if len(targets) > 1 else self.build_command(targets[0], opts)

        try:
            result = self.map_output(
                target=target,
                command=command_repr,
                stdout=stdout,
                stderr=stderr,
                exit_code=0 if status == "success" else 1,
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
                    "command": command_repr,
                    "exit_code": 1,
                    "stderr": stderr[:4000],
                    "mapping_error": str(exc),
                },
                metadata=KaisonResultMetadata(started_at=started_at, ended_at=ended_at, runtime_ms=runtime_ms),
                findings=[],
            )

        enriched_context = dict(result.target_context)
        enriched_context["resource_usage"] = resource_usage
        enriched_context["telemetry"] = telemetry_events
        enriched_context["unique_subdomains"] = len(unique_subdomains)
        enriched_context["resolved_hosts"] = resolved_hosts
        result = result.model_copy(update={"target_context": enriched_context, "status": status})

        deduped_findings = self._filter_duplicates(target, result.findings)
        if len(deduped_findings) != len(result.findings):
            adjusted_status = "partial" if result.status == "success" else result.status
            result = result.model_copy(update={"status": adjusted_status, "findings": deduped_findings})

        self._record_scan_history(
            target=target,
            command=command_repr,
            status=result.status,
            findings=deduped_findings,
            started_at=started_at,
            runtime_ms=runtime_ms,
            handoff_report=result.target_context.get("handoff_report"),
        )
        self._record_findings_correlation(target=target, findings=deduped_findings, started_at=started_at)
        self._persist_memory(target, deduped_findings)

        self._lifecycle_status = "IDLE"
        self._emit_telemetry(telemetry_events, "AGENT_STATUS", "IDLE", telemetry_hook)
        return result

    def _build_failure_result(
        self,
        *,
        target: str,
        mission_id: str,
        command: list[str],
        stderr: str,
        telemetry: list[dict[str, Any]],
        status: str,
    ) -> KaisonResult:
        now = datetime.now(UTC)
        self._lifecycle_status = "IDLE"
        return KaisonResult(
            mission_id=mission_id,
            source_agent=self.TOOL_NAME,
            status=status,
            target_context={
                "target": target,
                "command": command,
                "exit_code": 127,
                "stderr": stderr[:4000],
                "telemetry": telemetry,
            },
            metadata=KaisonResultMetadata(started_at=now, ended_at=now, runtime_ms=0),
            findings=[],
        )

    @staticmethod
    def _resolve_targets(target: str, options: dict[str, Any]) -> list[str]:
        if not bool(options.get("listener_mode")):
            return [target]
        data = options.get("input_data", [])
        if isinstance(data, str):
            values = [line.strip() for line in data.splitlines() if line.strip()]
            if values:
                return values
        if isinstance(data, list):
            values = [str(item).strip() for item in data if str(item).strip()]
            if values:
                return values
        return [target]

    def _resolve_threads(self, options: dict[str, Any]) -> int:
        global_limit = int(os.getenv("K1_GLOBAL_THREAD_LIMIT", "20"))
        scope_size = int(options.get("scope_size", 50))
        if scope_size >= 1000:
            recommended = 6
        elif scope_size >= 250:
            recommended = 10
        else:
            recommended = 16
        requested = int(options.get("threads", recommended))
        return max(1, min(requested, global_limit))

    def _opsec_precheck(self, options: dict[str, Any]) -> dict[str, Any]:
        binary_path = shutil.which("findomain")
        if not binary_path:
            return {"blocked": True, "reason": "findomain binary not found in PATH"}

        requires_active_path = bool(options.get("resolved", False) or options.get("http_status", False))
        require_sovereign = bool(options.get("require_sovereign_network", requires_active_path))
        if not require_sovereign:
            return {"blocked": False}

        proxy = self._resolve_proxy(options)
        vpn_up = bool(self._runtime_environment.get("vpn_up_interfaces"))
        proxychains_enabled = bool(self._runtime_environment.get("proxychains_enabled"))
        if proxy or vpn_up or proxychains_enabled:
            return {"blocked": False}
        return {"blocked": True, "reason": "Sovereign Network Layer not detected for active resolution flow"}

    def _inject_secret_manager_env(self, env: dict[str, str]) -> None:
        secret_names = [
            "SPYSE_API_KEY",
            "SECURITYTRAILS_API_KEY",
            "CRTSH_API_KEY",
            "VIRUSTOTAL_API_KEY",
        ]
        try:
            manager = get_secret_manager()
        except SecretManagerError:
            return

        for name in secret_names:
            value = manager.get_optional(name)
            if value:
                env[name] = value

    @staticmethod
    def _resolve_proxy(options: dict[str, Any]) -> str | None:
        for key in ("proxy", "K1_FINDOMAIN_PROXY", "ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY"):
            value = options.get(key) if key in options else os.getenv(key)
            if value:
                token = str(value).strip()
                if token:
                    return token
        return None

    def _parse_json_record(self, line: str, target: str) -> DiscoveryRegistry | None:
        if not line.startswith("{"):
            return None
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None

        discovered_domain = str(
            payload.get("subdomain")
            or payload.get("host")
            or payload.get("domain")
            or payload.get("name")
            or ""
        ).strip().lower()
        if not discovered_domain:
            return None

        if discovered_domain.startswith("*."):
            discovered_domain = discovered_domain[2:]

        if target and not (
            discovered_domain == target.lower() or discovered_domain.endswith(f".{target.lower()}")
        ):
            return None

        resolved_ips = payload.get("ip") or payload.get("ips") or []
        if isinstance(resolved_ips, str):
            resolved_ips = [resolved_ips]
        elif not isinstance(resolved_ips, list):
            resolved_ips = []
        cleaned_ips = [str(item).strip() for item in resolved_ips if str(item).strip()]

        status_value = payload.get("http_status") or payload.get("status")
        http_status: int | None = None
        if isinstance(status_value, int):
            http_status = status_value
        elif isinstance(status_value, str) and status_value.strip().isdigit():
            http_status = int(status_value.strip())

        try:
            return DiscoveryRegistry.model_validate(
                {
                    "discovered_domain": discovered_domain,
                    "source": "passive_findomain",
                    "root_domain": target,
                    "resolved_ips": cleaned_ips,
                    "http_status": http_status,
                    "raw_evidence": payload,
                }
            )
        except ValidationError:
            return None

    def _parse_plain_record(self, line: str, target: str) -> DiscoveryRegistry | None:
        token = line.strip().lower()
        if not token or token.startswith("["):
            return None
        if token.startswith("*."):
            token = token[2:]
        if not _DOMAIN_RE.match(token):
            return None
        if target and not (token == target.lower() or token.endswith(f".{target.lower()}")):
            return None
        try:
            return DiscoveryRegistry.model_validate(
                {
                    "discovered_domain": token,
                    "source": "passive_findomain",
                    "root_domain": target,
                    "raw_evidence": {"line": line},
                }
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
        event = {"key": key, "value": value, "timestamp": datetime.now(UTC).isoformat()}
        sink.append(event)
        if callable(hook):
            try:
                hook(event)
            except Exception:
                return

    @staticmethod
    def _is_rate_limited(stdout: str, stderr: str) -> bool:
        return _RATE_LIMIT_RE.search(f"{stdout}\n{stderr}") is not None

    def _load_runtime_environment(self) -> dict[str, Any]:
        interfaces = os.getenv("K1_VPN_INTERFACES", "").strip()
        if interfaces:
            vpn_interfaces = tuple(item.strip() for item in interfaces.split(",") if item.strip())
        else:
            vpn_interfaces = _DEFAULT_VPN_INTERFACES

        proxychains_enabled = os.getenv("K1_USE_PROXIES", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        return {
            "vpn_interfaces": vpn_interfaces,
            "vpn_up_interfaces": self._detect_up_interfaces(vpn_interfaces),
            "proxychains_enabled": proxychains_enabled,
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
        return {"wall_time_s": round(wall_s, 6), "cpu_time_s": round(cpu_s, 6)}

