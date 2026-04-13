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
from urllib.parse import urlparse

from pydantic import ValidationError

from apps.backend.src.core.protocol import KaisonResult, KaisonResultMetadata

from ..base_tool_agent import BaseToolAgent
from .schemas import HttpxRawRecord, ServiceRegistry

_RATE_LIMIT_RE = re.compile(
    r"(429|rate[\s_-]*limit|too many requests|quota exceeded|request limit)",
    re.IGNORECASE,
)
_DEFAULT_VPN_INTERFACES = ("tun0", "wg0", "vpn0")


class HttpxProbeAgent(BaseToolAgent):
    TOOL_NAME = "httpx_probe"
    DEFAULT_TIMEOUT_SECONDS = 300

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._runtime_environment = self._load_runtime_environment()
        self._active_process: subprocess.Popen[str] | None = None
        self._lifecycle_status = "ANALYSIS_IDLE"
        self._telemetry_hook: Callable[[dict[str, Any]], None] | None = None
        self._last_preflight: dict[str, Any] = {}

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def register_telemetry_hook(self, hook: Callable[[dict[str, Any]], None]) -> None:
        self._telemetry_hook = hook

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        binary = str(opts.get("binary_path") or opts.get("binary") or "httpx")
        listener_mode = bool(opts.get("listener_mode"))

        cmd = [
            binary,
            "-silent",
            "-json",
            "-status-code",
            "-title",
            "-td",
            "-cdn",
            "-ip",
            "-cname",
            "-server",
            "-cl",
        ]

        if bool(opts.get("follow_redirects", True)):
            cmd.append("-follow-redirects")

        threads = int(opts.get("threads", 50))
        cmd += ["-t", str(max(1, threads))]
        rate_limit = int(opts.get("rate_limit", 150))
        cmd += ["-rl", str(max(1, rate_limit))]

        if opts.get("filter_status"):
            cmd += ["-fc", str(opts["filter_status"])]
        elif bool(opts.get("exclude_404")):
            cmd += ["-fc", "404"]
        else:
            # Keep compatibility with existing tests/behavior.
            cmd += ["-mc", "200,401,403,500"]

        if not listener_mode:
            input_file = str(opts.get("input_file", "subdomains.txt")).strip()
            if input_file:
                cmd += ["-l", input_file]
            else:
                cmd += ["-u", target]

        if opts.get("output_file"):
            cmd += ["-o", str(opts["output_file"])]

        return cmd

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

            registry = self._parse_httpx_json_line(line, target)
            if registry is None:
                # Backward compatibility for legacy depth-tests.
                if line.startswith(("http://", "https://")):
                    findings.append(
                        {
                            "type": "url",
                            "url": line,
                            "value": line,
                            "status_code": 0,
                            "target": target,
                            "severity": "info",
                            "confidence": 0.7,
                            "source_tool": self.TOOL_NAME,
                            "raw_evidence": line,
                            "context": {
                                "status_code": 0,
                                "title": "",
                                "tech": [],
                                "cdn": False,
                                "cdn_name": "",
                                "content_length": 0,
                                "server": "",
                            },
                            "recommended_next_tools": ["naabu", "nuclei_scan"],
                            "recommended_next_actions": ["port_scan", "vulnerability_scan"],
                        }
                    )
                continue

            status_code = registry.http_status
            finding = {
                "type": "url",
                "url": registry.service_url,
                "value": registry.service_url,
                "status_code": status_code,
                "target": target,
                "severity": "info",
                "confidence": 0.9,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": registry.raw_evidence,
                "context": {
                    "service_registry": registry.model_dump(mode="json"),
                    "status_code": status_code,
                    "title": registry.page_title,
                    "tech": registry.tech_stack,
                    "cdn": bool(registry.raw_evidence.get("cdn", False)),
                    "cdn_name": str(registry.raw_evidence.get("cdn_name", "")),
                    "content_length": registry.content_length or 0,
                    "server": registry.server_header,
                    "resolved_ips": registry.resolved_ips,
                    "cname_records": registry.cname_records,
                },
                "recommended_next_tools": ["naabu", "nuclei_scan"],
                "recommended_next_actions": ["port_scan", "vulnerability_scan"],
            }
            findings.append(finding)

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()

        for item in findings:
            value = item["value"].lower()
            if f"{item['target'].lower()}|url|{value}" in known:
                noise.append(item)
                continue

            context = item.get("context", {})
            status_code = int(context.get("status_code", item.get("status_code", 0)) or 0)
            is_cdn = bool(context.get("cdn"))

            if is_cdn and status_code not in {401, 403}:
                item["noise_reason"] = "cdn_hosted_static"
                noise.append(item)
                continue

            if status_code == 403:
                server = str(context.get("server", "")).lower()
                if "cloudflare" in server or "akamai" in server or is_cdn:
                    item["signal_reason"] = "waf_403"
                else:
                    item["signal_reason"] = "app_403"
                    item["severity"] = "medium"
                signal.append(item)
                continue

            if status_code == 401:
                item["signal_reason"] = "auth_required"
                item["severity"] = "medium"
                signal.append(item)
                continue

            signal.append(item)

        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        urls = [item["url"] for item in signal if item.get("url")]
        tech_map: dict[str, int] = {}
        for item in signal:
            for tech in item.get("context", {}).get("tech", []):
                token = str(tech).strip()
                if not token:
                    continue
                tech_map[token] = tech_map.get(token, 0) + 1

        return {
            "next_agent": "naabu",
            "action": "port_scan_live_hosts",
            "target": target,
            "input_urls": urls,
            "detected_tech": sorted(tech_map.keys()),
            "instructions": (
                f"Probed {len(urls)} live services via httpx. "
                f"Detected technologies: {', '.join(sorted(tech_map.keys())[:10]) or 'none'}. "
                "Continue with naabu then nuclei for validation."
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
        preflight = self._preflight(command=["httpx"], options={})
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
                stderr=str(preflight.get("error", "httpx binary unavailable")),
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

        started_at = datetime.now(UTC)
        monitor = ResourceMonitor()
        self._lifecycle_status = "PROBING_TARGETS"

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        stdout_chars = {"count": 0}
        stderr_chars = {"count": 0}
        stop_stream = threading.Event()
        live_web_services = {"count": 0}
        seen_live_urls: set[str] = set()

        status = "failure"
        exit_code = 127
        process: subprocess.Popen[str] | None = None
        kill_telemetry: dict[str, Any] = {}

        previous_sigterm = None
        sigterm_installed = False
        sigterm_requested = {"requested": False}

        def _on_stdout_line(line: str) -> None:
            record = self._parse_httpx_json_line(line, target)
            if record is None:
                return
            status_code = record.http_status
            if self._is_live_status(status_code) and record.service_url not in seen_live_urls:
                seen_live_urls.add(record.service_url)
                live_web_services["count"] += 1
                self._emit_telemetry(
                    telemetry_events,
                    "LIVE_WEB_SERVICES",
                    live_web_services["count"],
                    telemetry_hook,
                )
                self._emit_telemetry(
                    telemetry_events,
                    "EventLog",
                    f"WEB_SERVICE_DETECTED_GOLD:{record.service_url}",
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
        enriched_context["live_web_services"] = live_web_services["count"]
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
        binary = command[0] if command else "httpx"
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
        sovereign_ok = bool(self._runtime_environment.get("vpn_up_interfaces")) or bool(
            self._runtime_environment.get("proxychains_enabled")
        )

        return {
            "binary_requested": binary,
            "binary_path": binary_path,
            "binary_available": bool(binary_path),
            "version": version,
            "runtime_environment": self._runtime_environment,
            "require_sovereign_network": require_sovereign,
            "sovereign_network_ok": sovereign_ok,
            "error": None if binary_path else "httpx binary not found in PATH",
        }

    def _parse_httpx_json_line(self, line: str, target: str | None = None) -> ServiceRegistry | None:
        token = line.strip()
        if not token or not token.startswith("{"):
            return None
        try:
            raw = HttpxRawRecord.model_validate_json(token)
            registry = ServiceRegistry.from_raw(raw, target_domain=target)
        except ValidationError:
            return None
        except json.JSONDecodeError:
            return None

        if target:
            parsed = urlparse(registry.service_url)
            host = parsed.hostname or ""
            target_l = target.lower()
            if host and not (host == target_l or host.endswith(f".{target_l}")):
                return None
        return registry

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
    def _is_live_status(status_code: int) -> bool:
        if status_code == 403:
            return True
        if 200 <= status_code < 400:
            return True
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
