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
from .schemas import CorsyRawRecord, WebPolicyRegistry

_RATE_LIMIT_RE = re.compile(
    r"(429|rate[\s_-]*limit|too many requests|quota exceeded|request limit)",
    re.IGNORECASE,
)
_DEFAULT_VPN_INTERFACES = ("tun0", "wg0", "vpn0")
_PUBLIC_HINTS = ("/public", "/status", "/health", "/docs", "/openapi")
_SENSITIVE_HINTS = ("/api", "/admin", "/account", "/profile", "/billing", "/user", "/auth")


class CorsyAgent(BaseToolAgent):
    TOOL_NAME = "corsy"
    DEFAULT_TIMEOUT_SECONDS = 360

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._runtime_environment = self._load_runtime_environment()
        self._active_process: subprocess.Popen[str] | None = None
        self._lifecycle_status = "ANALYSIS_IDLE"
        self._telemetry_hook: Callable[[dict[str, Any]], None] | None = None

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def register_telemetry_hook(self, hook: Callable[[dict[str, Any]], None]) -> None:
        self._telemetry_hook = hook

    def check_binary(self) -> dict[str, Any]:
        binary_path = shutil.which("corsy")
        return {
            "tool": self.TOOL_NAME,
            "available": bool(binary_path),
            "binary_path": binary_path,
        }

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        cmd = ["corsy", "-u", target]

        global_limit = int(os.getenv("K1_GLOBAL_THREAD_LIMIT", "20"))
        requested_threads = int(opts.get("threads", 10))
        threads = max(1, min(requested_threads, global_limit))
        cmd += ["-t", str(threads)]

        if opts.get("header"):
            cmd += ["-H", str(opts["header"])]

        if opts.get("json_output", True):
            # Keep wrapper intent explicit; parser supports both json/plain text.
            cmd += ["--json"]

        proxy = self._resolve_proxy(opts)
        if proxy:
            cmd += ["--proxy", proxy]

        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        for raw_line in raw_output.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            record = self._parse_raw_line(line=line, fallback_target=target)
            if record is None:
                continue

            allows_credentials = self._coerce_allows_credentials(record)
            leak_potential = self._infer_data_leak_potential(
                endpoint=record.url,
                allows_credentials=allows_credentials,
                misconfig_type=record.type,
            )
            poc_js = self._build_poc(
                endpoint=record.url,
                allows_credentials=allows_credentials,
            )
            registry = WebPolicyRegistry.from_raw(
                record,
                allows_credentials=allows_credentials,
                data_leak_potential=leak_potential,
                poc_javascript=poc_js,
            )

            findings.append(
                {
                    "type": "vulnerability",
                    "value": f"{registry.target_endpoint}|{registry.misconfig_type}",
                    "target": target,
                    "severity": registry.risk_level,
                    "confidence": 0.9 if registry.data_leak_potential != "low" else 0.75,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": registry.raw_evidence,
                    "context": {
                        "web_policy_registry": registry.model_dump(mode="json"),
                        "target_endpoint": registry.target_endpoint,
                        "misconfig_type": registry.misconfig_type,
                        "risk_level": registry.risk_level,
                        "data_leak_potential": registry.data_leak_potential,
                        "allows_credentials": registry.allows_credentials,
                        "poc_javascript": registry.poc_javascript,
                        "vulnerability_type": "cors_misconfig",
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["check_cors_exploitability"],
                }
            )

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
            if f"{target}|vulnerability|{value}" in known:
                noise.append(item)
                continue

            leak = str(item.get("context", {}).get("data_leak_potential", "low")).lower()
            if leak == "low":
                item["noise_reason"] = "public_or_low_impact_cors"
                noise.append(item)
                continue

            if leak == "high":
                item["signal_reason"] = "origin_reflection_with_credentials"
                item["severity"] = "critical"
            else:
                item["signal_reason"] = "cors_misconfig_moderate"
                item["severity"] = "medium"
            signal.append(item)

        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        critical = [item for item in signal if str(item.get("severity", "")).lower() == "critical"]
        return {
            "next_agent": "EvidenceAnalystAgent",
            "action": "check_cors_exploitability",
            "target": target,
            "critical_findings": critical[:10],
            "instructions": (
                f"CORSy identified {len(signal)} impactful CORS misconfigurations. "
                f"Critical count: {len(critical)}. "
                "Use generated PoC fetch snippets to validate cross-origin data leakage."
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

        self._emit_telemetry(telemetry_events, "AGENT_STATUS", "CORS_AUDIT_ACTIVE", telemetry_hook)

        precheck = self._opsec_precheck(opts)
        if precheck["blocked"]:
            return self._build_failure_result(
                target=target,
                mission_id=mission_id,
                command=["corsy"],
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

        misconfigs_total = 0
        leak_counts = {"high": 0, "medium": 0, "low": 0}

        for entry in targets:
            command = self.build_command(entry, opts)
            process: subprocess.Popen[str] | None = None
            stop_stream = threading.Event()
            stdout_lines: list[str] = []
            stderr_lines: list[str] = []
            stdout_chars = {"count": 0}
            stderr_chars = {"count": 0}

            def _on_stdout_line(line: str) -> None:
                nonlocal misconfigs_total
                parsed = self.parse_output(line, target)
                for finding in parsed:
                    misconfigs_total += 1
                    leak = str(finding.get("context", {}).get("data_leak_potential", "low")).lower()
                    if leak in leak_counts:
                        leak_counts[leak] += 1
                    self._emit_telemetry(
                        telemetry_events,
                        "CORS_MISCONFIGS_TOTAL",
                        misconfigs_total,
                        telemetry_hook,
                    )
                    self._emit_telemetry(
                        telemetry_events,
                        "DATA_LEAK_POTENTIAL",
                        dict(leak_counts),
                        telemetry_hook,
                    )
                    self._emit_telemetry(
                        telemetry_events,
                        "DATA_LEAK_POTENTIAL_LEVEL",
                        self._current_leak_level(leak_counts),
                        telemetry_hook,
                    )
                    if str(finding.get("severity", "")).lower() == "critical":
                        endpoint = str(finding.get("context", {}).get("target_endpoint", entry))
                        self._emit_telemetry(
                            telemetry_events,
                            "EventLog",
                            f"DATA_LEAKAGE:PURPLE_RING_EXPAND:{endpoint}",
                            telemetry_hook,
                        )

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

        command_repr = ["corsy", "-u", "<batch>"] if len(targets) > 1 else self.build_command(target, opts)

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
                metadata=KaisonResultMetadata(
                    started_at=started_at,
                    ended_at=ended_at,
                    runtime_ms=runtime_ms,
                ),
                findings=[],
            )

        enriched_context = dict(result.target_context)
        enriched_context["resource_usage"] = resource_usage
        enriched_context["telemetry"] = telemetry_events
        enriched_context["cors_misconfigs_total"] = misconfigs_total
        enriched_context["data_leak_potential"] = leak_counts
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
    def _coerce_allows_credentials(record: CorsyRawRecord) -> bool:
        if isinstance(record.allow_credentials, bool):
            return record.allow_credentials
        acac = (record.access_control_allow_credentials or "").strip().lower()
        return acac == "true"

    @staticmethod
    def _infer_data_leak_potential(
        *,
        endpoint: str,
        allows_credentials: bool,
        misconfig_type: str,
    ) -> str:
        endpoint_l = endpoint.lower()
        misconfig_l = misconfig_type.lower()

        is_public = any(hint in endpoint_l for hint in _PUBLIC_HINTS)
        is_sensitive = any(hint in endpoint_l for hint in _SENSITIVE_HINTS)

        if allows_credentials and (is_sensitive or "reflection" in misconfig_l):
            return "high"
        if allows_credentials or is_sensitive or "null" in misconfig_l:
            return "medium"
        if is_public and "*" in misconfig_l:
            return "low"
        return "low"

    @staticmethod
    def _build_poc(*, endpoint: str, allows_credentials: bool) -> str:
        creds_mode = "include" if allows_credentials else "omit"
        return (
            "fetch('" + endpoint + "', {\\n"
            "  method: 'GET',\\n"
            "  mode: 'cors',\\n"
            "  credentials: '" + creds_mode + "'\\n"
            "})\\n"
            ".then(r => r.text())\\n"
            ".then(body => console.log('exfil', body))\\n"
            ".catch(err => console.error(err));"
        )

    def _parse_raw_line(self, *, line: str, fallback_target: str) -> CorsyRawRecord | None:
        token = line.strip()

        if token.startswith("{"):
            try:
                data = json.loads(token)
            except json.JSONDecodeError:
                data = None

            if isinstance(data, dict):
                if "url" not in data:
                    data["url"] = fallback_target
                if "severity" not in data:
                    data["severity"] = "medium"
                if "type" not in data:
                    data["type"] = "cors_misconfig"
                try:
                    return CorsyRawRecord.model_validate(data)
                except ValidationError:
                    return None

        lowered = token.lower()
        if "access-control-allow-origin" in lowered or "vulnerability" in lowered or "cors" in lowered:
            misconfig = "origin_reflection"
            severity = "medium"
            if "*" in token:
                misconfig = "wildcard_acao"
            if "null" in lowered:
                misconfig = "null_origin"
            if "credential" in lowered and "true" in lowered:
                severity = "high"

            try:
                return CorsyRawRecord.model_validate(
                    {
                        "url": fallback_target,
                        "type": misconfig,
                        "severity": severity,
                        "access_control_allow_origin": "*" if "*" in token else None,
                        "access_control_allow_credentials": "true" if "credential" in lowered and "true" in lowered else None,
                    }
                )
            except ValidationError:
                return None

        return None

    @staticmethod
    def _resolve_targets(target: str, options: dict[str, Any]) -> list[str]:
        if bool(options.get("listener_mode")):
            for key in ("input_data", "targets", "input_urls"):
                data = options.get(key, [])
                if isinstance(data, str):
                    values = [line.strip() for line in data.splitlines() if line.strip()]
                    if values:
                        return values
                elif isinstance(data, list):
                    values = [str(item).strip() for item in data if str(item).strip()]
                    if values:
                        return values
        return [target]

    def _opsec_precheck(self, options: dict[str, Any]) -> dict[str, Any]:
        binary_path = shutil.which("corsy")
        if not binary_path:
            return {"blocked": True, "reason": "corsy binary not found in PATH"}

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
            "reason": "Sovereign Network Layer not detected: origin tests require proxy/tor or active tunnel",
        }

    @staticmethod
    def _resolve_proxy(options: dict[str, Any]) -> str | None:
        for key in ("proxy", "K1_CORSY_PROXY", "ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY"):
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
    def _current_leak_level(leak_counts: dict[str, int]) -> str:
        if int(leak_counts.get("high", 0)) > 0:
            return "high"
        if int(leak_counts.get("medium", 0)) > 0:
            return "medium"
        return "low"

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
        return {
            "wall_time_s": round(wall_s, 6),
            "cpu_time_s": round(cpu_s, 6),
        }
