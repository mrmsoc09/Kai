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
from .schemas import EndpointRegistry, KiterunnerRawRecord
from .wordlists import KiterunnerWordlistManager

_RATE_LIMIT_RE = re.compile(
    r"(429|rate[\s_-]*limit|too many requests|quota exceeded|request limit)",
    re.IGNORECASE,
)
_LEGACY_LINE_RE = re.compile(r"^\[(?P<method>[A-Z]+)\]\s+\[(?P<status>\d{3})\]\s+\[(?P<length>\d+)\]\s+(?P<url>\S+)$")
_DEFAULT_VPN_INTERFACES = ("tun0", "wg0", "vpn0")
_SIGNAL_STATUSES = {200, 201, 202, 204, 301, 302, 307, 308, 401, 403, 405}


class KiterunnerAgent(BaseToolAgent):
    TOOL_NAME = "kiterunner"
    DEFAULT_TIMEOUT_SECONDS = 600

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._runtime_environment = self._load_runtime_environment()
        self._active_process: subprocess.Popen[str] | None = None
        self._lifecycle_status = "ANALYSIS_IDLE"
        self._telemetry_hook: Callable[[dict[str, Any]], None] | None = None
        self._wordlists = KiterunnerWordlistManager()

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def register_telemetry_hook(self, hook: Callable[[dict[str, Any]], None]) -> None:
        self._telemetry_hook = hook

    def check_binary(self) -> dict[str, Any]:
        binary_path = shutil.which("kr")
        return {
            "tool": self.TOOL_NAME,
            "available": bool(binary_path),
            "binary_path": binary_path,
        }

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        binary = str(opts.get("binary_path") or opts.get("binary") or "kr")
        mode = str(opts.get("mode", "scan")).strip().lower()
        if mode not in {"scan", "brute"}:
            mode = "scan"

        tech_stack_raw = opts.get("tech_stack", [])
        tech_stack = (
            [str(item) for item in tech_stack_raw]
            if isinstance(tech_stack_raw, list)
            else [str(tech_stack_raw)]
        )
        wordlist = self._wordlists.select_wordlist(
            tech_stack=tech_stack,
            mode=mode,
            requested_wordlist=str(opts.get("wordlist")) if opts.get("wordlist") else None,
        )

        cmd = [binary, mode, target, "-w", wordlist]

        global_limit = int(os.getenv("K1_GLOBAL_THREAD_LIMIT", "20"))
        requested_concurrency = int(opts.get("concurrency", opts.get("threads", 12)))
        concurrency = max(1, min(requested_concurrency, global_limit))
        cmd += ["-c", str(concurrency)]

        delay_ms = int(opts.get("delay_ms", opts.get("delay", 75)))
        cmd += ["--delay", str(max(0, delay_ms))]

        fail_status_codes = str(opts.get("fail_status_codes", "404")).strip()
        if fail_status_codes:
            cmd += ["--fail-status-codes", fail_status_codes]

        if bool(opts.get("json_output", True)):
            cmd.append("-j")

        if opts.get("output_file"):
            cmd += ["-o", str(opts["output_file"])]

        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        target_url = self._normalize_target_url(target)

        for raw_line in raw_output.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            raw_record = self._parse_json_line(line) or self._parse_legacy_line(line, target_url=target_url)
            if raw_record is None:
                continue

            try:
                registry = EndpointRegistry.from_raw(raw_record, target_url=target_url)
            except ValidationError:
                continue

            full_url = f"{registry.service_url}{registry.endpoint_path}"
            finding = {
                "type": "url",
                "url": full_url,
                "value": full_url,
                "target": target,
                "severity": "info",
                "confidence": 0.88,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": registry.raw_evidence,
                "status_code": str(registry.http_status),
                "method": registry.http_method,
                "context": {
                    "endpoint_registry": registry.model_dump(mode="json"),
                    "endpoint_path": registry.endpoint_path,
                    "status_code": str(registry.http_status),
                    "method": registry.http_method,
                    "response_size": registry.response_size or 0,
                    "service_url": registry.service_url,
                },
                "recommended_next_tools": ["nuclei_scan", "httpx_probe"],
                "recommended_next_actions": ["scan_api_endpoints", "revalidate_with_httpx"],
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
            value = str(item.get("value", "")).lower()
            target = str(item.get("target", "")).lower()
            if f"{target}|url|{value}" in known:
                noise.append(item)
                continue

            status = int(str(item.get("context", {}).get("status_code", "0")))
            if status in _SIGNAL_STATUSES:
                item["signal_reason"] = "api_endpoint_discovered"
                if status in {401, 403, 405}:
                    item["severity"] = "medium"
                signal.append(item)
            else:
                item["noise_reason"] = "non_actionable_http_status"
                noise.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        urls = [str(item.get("url", "")).strip() for item in signal if str(item.get("url", "")).strip()]
        recursive_candidates = []
        for item in signal:
            endpoint_path = str(item.get("context", {}).get("endpoint_path", "")).strip().lower()
            if endpoint_path.startswith("/api/v2"):
                recursive_candidates.append(str(item.get("url", "")).strip())

        return {
            "next_agent": "nuclei_scan",
            "fallback_agent": "httpx_probe",
            "action": "scan_api_endpoints",
            "target": target,
            "input_urls": urls,
            "recursive_scan_queue": sorted(set(recursive_candidates)),
            "instructions": (
                f"Kiterunner discovered {len(urls)} API routes. "
                "Trigger nuclei for endpoint vulnerability checks. "
                "Use httpx_probe to re-validate routes requiring auth/context."
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
        self._lifecycle_status = "ANALYSIS_IDLE"
        return {"tool": self.TOOL_NAME, "stopped": stopped, "status": self._lifecycle_status}

    def health_check(self) -> dict[str, Any]:
        check = self.check_binary()
        return {
            "tool": self.TOOL_NAME,
            "status": self._lifecycle_status,
            "healthy": bool(check.get("available")),
            "binary_path": check.get("binary_path"),
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
                command=["kr", str(opts.get("mode", "scan"))],
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

        routes_discovered = 0
        scan_depth = max(1, int(opts.get("scan_depth", 1)))
        max_depth = max(scan_depth, int(opts.get("max_depth", 2)))
        recursive_queue: list[str] = []

        for entry in targets:
            command = self.build_command(entry, opts)
            process: subprocess.Popen[str] | None = None
            stop_stream = threading.Event()
            stdout_lines: list[str] = []
            stderr_lines: list[str] = []
            stdout_chars = {"count": 0}
            stderr_chars = {"count": 0}

            def _on_stdout_line(line: str) -> None:
                nonlocal routes_discovered
                parsed = self.parse_output(line, entry)
                for finding in parsed:
                    routes_discovered += 1
                    self._emit_telemetry(
                        telemetry_events,
                        "API_ROUTES_DISCOVERED",
                        routes_discovered,
                        telemetry_hook,
                    )
                    self._emit_telemetry(telemetry_events, "SCAN_DEPTH", scan_depth, telemetry_hook)
                    self._emit_telemetry(
                        telemetry_events,
                        "EventLog",
                        f"NETWORK_BRANCHING:GOLD_WEB:{finding.get('url', entry)}",
                        telemetry_hook,
                    )

                    endpoint_path = str(finding.get("context", {}).get("endpoint_path", ""))
                    if (
                        bool(opts.get("enable_recursive", True))
                        and scan_depth < max_depth
                        and endpoint_path.lower().startswith("/api/v2")
                    ):
                        recursive_target = self._build_recursive_target(entry, endpoint_path)
                        if recursive_target not in recursive_queue:
                            recursive_queue.append(recursive_target)

            previous_sigterm = None
            sigterm_installed = False

            def _on_sigterm(_: int, __: Any) -> None:
                stop_stream.set()
                if process is not None and process.poll() is None:
                    self._kill_process_group(process)  # type: ignore[arg-type]

            try:
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
        mode = str(opts.get("mode", "scan")).strip().lower()
        command_repr = ["kr", mode, "<batch>"] if len(targets) > 1 else self.build_command(targets[0], opts)

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
        enriched_context["api_routes_discovered"] = routes_discovered
        enriched_context["scan_depth"] = scan_depth
        enriched_context["recursive_scan_queue"] = recursive_queue
        enriched_context["recursive_requeue"] = bool(recursive_queue)
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

        self._lifecycle_status = "ANALYSIS_IDLE"
        self._emit_telemetry(telemetry_events, "AGENT_STATUS", "ANALYSIS_IDLE", telemetry_hook)
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
        self._lifecycle_status = "ANALYSIS_IDLE"
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
    def _parse_json_line(line: str) -> KiterunnerRawRecord | None:
        if not line.startswith("{"):
            return None
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        try:
            return KiterunnerRawRecord.model_validate(payload)
        except ValidationError:
            return None

    @staticmethod
    def _parse_legacy_line(line: str, *, target_url: str) -> KiterunnerRawRecord | None:
        match = _LEGACY_LINE_RE.match(line)
        if not match:
            return None
        raw_url = match.group("url").strip()
        if raw_url.startswith("/"):
            raw_url = f"{target_url.rstrip('/')}{raw_url}"
        try:
            return KiterunnerRawRecord.model_validate(
                {
                    "url": raw_url,
                    "method": match.group("method"),
                    "status": match.group("status"),
                    "length": match.group("length"),
                }
            )
        except ValidationError:
            return None

    @staticmethod
    def _normalize_target_url(target: str) -> str:
        token = str(target).strip()
        if token.startswith(("http://", "https://")):
            return token
        if ":" in token and token.split(":", 1)[1].isdigit():
            host, port = token.split(":", 1)
            scheme = "https" if port == "443" else "http"
            return f"{scheme}://{host}:{port}"
        return f"https://{token}"

    def _resolve_targets(self, target: str, options: dict[str, Any]) -> list[str]:
        if not bool(options.get("listener_mode")):
            return [self._normalize_target_url(target)]

        data = options.get("input_data", [])
        values: list[str] = []
        if isinstance(data, str):
            values = [line.strip() for line in data.splitlines() if line.strip()]
        elif isinstance(data, list):
            values = [str(item).strip() for item in data if str(item).strip()]

        if not values:
            return [self._normalize_target_url(target)]
        return [self._normalize_target_url(item) for item in values]

    @staticmethod
    def _build_recursive_target(base_target: str, endpoint_path: str) -> str:
        parsed = urlparse(base_target)
        return f"{parsed.scheme}://{parsed.netloc}{endpoint_path}"

    def _opsec_precheck(self, options: dict[str, Any]) -> dict[str, Any]:
        binary_path = shutil.which("kr")
        if not binary_path:
            return {"blocked": True, "reason": "kiterunner binary not found in PATH"}

        require_sovereign = bool(options.get("require_sovereign_network", True))
        if not require_sovereign:
            return {"blocked": False}

        proxy = self._resolve_proxy(options)
        use_tor = bool(options.get("use_tor", False)) or os.getenv("K1_USE_TOR", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        vpn_up = bool(self._runtime_environment.get("vpn_up_interfaces"))
        proxychains_enabled = bool(self._runtime_environment.get("proxychains_enabled"))

        if proxy or use_tor or vpn_up or proxychains_enabled:
            return {"blocked": False}

        return {
            "blocked": True,
            "reason": "Sovereign Network Layer not detected: API brute-force requires proxy/tor or active tunnel",
        }

    @staticmethod
    def _resolve_proxy(options: dict[str, Any]) -> str | None:
        for key in ("proxy", "K1_KITERUNNER_PROXY", "ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY"):
            value = options.get(key) if key in options else os.getenv(key)
            if value:
                token = str(value).strip()
                if token:
                    return token
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
