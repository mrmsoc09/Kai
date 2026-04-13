from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from apps.backend.src.core.protocol import KaisonResult, KaisonResultMetadata

from ..base_tool_agent import BaseToolAgent
from .schemas import DatabaseSecurityRegistry, SqlmapRawRecord

_VULN_RE = re.compile(
    r"(?i)(is\s+vulnerable|appears\s+to\s+be\s+vulnerable|injectable\s+parameter|sql\s+injection)"
)
_DBMS_RE = re.compile(r"(?im)back-end\s+dbms:\s*([^\n]+)")
_PARAM_RE = re.compile(r"(?im)Parameter:\s*([^\s\(]+)\s*\(([^\)]+)\)")
_PAYLOAD_RE = re.compile(r"(?im)^\s*Payload:\s*(.+)$")
_SCHEMA_RE = re.compile(r"(?i)(database\s+schema|available\s+databases|current\s+database)")
_RATE_LIMIT_RE = re.compile(
    r"(429|rate[\s_-]*limit|too many requests|quota exceeded|request limit)",
    re.IGNORECASE,
)
_DEFAULT_VPN_INTERFACES = ("tun0", "wg0", "vpn0")


class SqlmapAgent(BaseToolAgent):
    TOOL_NAME = "sqlmap"
    DEFAULT_TIMEOUT_SECONDS = 900

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._runtime_environment = self._load_runtime_environment()
        self._active_process: subprocess.Popen[str] | None = None
        self._lifecycle_status = "ANALYSIS_IDLE"
        self._telemetry_hook: Callable[[dict[str, Any]], None] | None = None

        self._sessions_root = self.memory_dir / "sessions"
        self._sessions_root.mkdir(parents=True, exist_ok=True)

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def register_telemetry_hook(self, hook: Callable[[dict[str, Any]], None]) -> None:
        self._telemetry_hook = hook

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}

        phase = str(opts.get("scan_phase", "testing")).strip().lower()
        deep_dive = bool(opts.get("deep_dive", False)) or phase == "exploitation"

        level = 5 if deep_dive else 1
        risk = 3 if deep_dive else 1

        cmd = [
            "sqlmap",
            "--batch",
            "--disable-coloring",
            "--level",
            str(level),
            "--risk",
            str(risk),
        ]

        input_file = str(opts.get("input_file", "")).strip()
        if input_file:
            cmd += ["-m", input_file]
        else:
            cmd += ["-u", target]

        session_dir = str(opts.get("session_dir") or self._session_dir_for_target(target))
        Path(session_dir).mkdir(parents=True, exist_ok=True)
        cmd += ["--output-dir", session_dir]

        if bool(opts.get("flush_session", False)):
            cmd.append("--flush-session")

        boolean_only = bool(opts.get("boolean_only", phase != "exploitation"))
        if boolean_only:
            cmd += ["--technique", "B"]

        if bool(opts.get("random_agent", True)):
            cmd.append("--random-agent")

        if opts.get("threads"):
            cmd += ["--threads", str(max(1, int(opts["threads"]))) ]

        if deep_dive:
            cmd += ["--fingerprint", "--banner"]
            if bool(opts.get("map_schema", True)):
                cmd.append("--schema")

        # Hard-block destructive extraction defaults.
        forbidden_switches = {
            "--dump",
            "--os-shell",
            "--sql-shell",
            "--file-read",
            "--file-write",
            "--os-pwn",
            "--priv-esc",
        }
        custom_flags = opts.get("custom_flags", [])
        if isinstance(custom_flags, list):
            for token in custom_flags:
                text = str(token).strip()
                if not text or text in forbidden_switches:
                    continue
                cmd.append(text)

        proxy = self._resolve_proxy(opts)
        use_tor = self._resolve_tor(opts)

        if proxy:
            cmd += ["--proxy", proxy]
        elif use_tor:
            cmd += ["--tor", "--check-tor"]

        # Tracking header for defensive audit chain.
        pgp_fingerprint = str(
            opts.get("k1_pgp_fingerprint")
            or os.getenv("K1_PGP_FINGERPRINT", "UNSET")
        ).strip()
        header_value = f"X-K1-PGP-Fingerprint: {pgp_fingerprint}"
        cmd += ["--headers", header_value]

        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        parsed_records = self._extract_records(raw_output=raw_output, phase_hint="testing")
        if not parsed_records:
            return findings

        session_path = str(self._session_dir_for_target(target))
        schema_mapped = _SCHEMA_RE.search(raw_output) is not None

        for record in parsed_records:
            severity = "critical" if record.phase == "exploitation" else "high"
            registry = DatabaseSecurityRegistry.from_raw(
                record,
                target_url=target,
                session_path=session_path,
                severity=severity,
                schema_mapped=schema_mapped,
            )
            vuln_hash = self._build_vuln_hash(registry)

            findings.append(
                {
                    "type": "vulnerability",
                    "value": f"{registry.db_technology}:{registry.vuln_parameter}@{registry.injection_point}",
                    "target": target,
                    "severity": severity,
                    "confidence": registry.confidence,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": registry.raw_evidence,
                    "context": {
                        "database_security_registry": registry.model_dump(mode="json"),
                        "db_technology": registry.db_technology,
                        "injection_point": registry.injection_point,
                        "vuln_parameter": registry.vuln_parameter,
                        "scan_phase": registry.phase,
                        "schema_mapped": registry.is_schema_mapped,
                        "vuln_hash": vuln_hash,
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["validate_sqli"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()

        seen_hashes: set[str] = set()

        for item in findings:
            value = str(item.get("value", "")).lower()
            target = str(item.get("target", "")).lower()
            if f"{target}|vulnerability|{value}" in known:
                noise.append(item)
                continue

            vuln_hash = str(item.get("context", {}).get("vuln_hash", "")).strip().lower()
            if vuln_hash and vuln_hash in seen_hashes:
                item["noise_reason"] = "duplicate_sqlmap_finding"
                noise.append(item)
                continue

            if vuln_hash:
                seen_hashes.add(vuln_hash)

            if item.get("context", {}).get("scan_phase") == "exploitation":
                item["signal_reason"] = "sqlmap_exploitation_phase"
                item["severity"] = "critical"
            else:
                item["signal_reason"] = "sqlmap_testing_phase"

            signal.append(item)

        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        exploitation_hits = [item for item in signal if item.get("context", {}).get("scan_phase") == "exploitation"]

        return {
            "next_agent": "EvidenceAnalystAgent",
            "action": "confirm_sql_injection",
            "target": target,
            "confirmed_count": len(signal),
            "exploitation_count": len(exploitation_hits),
            "instructions": (
                f"SQLMap confirmed {len(signal)} SQL injection indicators. "
                f"{len(exploitation_hits)} were identified in exploitation phase. "
                "Capture reproducible evidence and route to analyst validation workflow."
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
        binary_path = shutil.which("sqlmap")
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

        self._emit_telemetry(telemetry_events, "AGENT_STATUS", "SQLMAP_ACTIVE", telemetry_hook)

        safety_check = self._safety_precheck(target=target, options=opts)
        if safety_check["blocked"]:
            return self._build_failure_result(
                target=target,
                mission_id=mission_id,
                command=["sqlmap"],
                stderr=safety_check["reason"],
                telemetry=telemetry_events,
                status="failure",
            )

        temp_input_file: Path | None = None
        if bool(opts.get("listener_mode")) and opts.get("input_data"):
            candidates = self._normalize_listener_input(opts.get("input_data"))
            if candidates:
                temp_dir = Path(tempfile.mkdtemp(prefix="k1-sqlmap-input-"))
                temp_input_file = temp_dir / "targets.txt"
                temp_input_file.write_text("\n".join(candidates) + "\n", encoding="utf-8")
                opts["input_file"] = str(temp_input_file)

        command = self.build_command(target, opts)

        started_at = datetime.now(UTC)
        monitor = ResourceMonitor()

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        stdout_chars = {"count": 0}
        stderr_chars = {"count": 0}
        stop_stream = threading.Event()

        status = "failure"
        exit_code = 127
        process: subprocess.Popen[str] | None = None
        kill_telemetry: dict[str, Any] = {}

        db_vulns_confirmed = {"count": 0}
        table_schema_mapped = {"count": 0}

        def _on_stdout_line(line: str) -> None:
            if _VULN_RE.search(line):
                db_vulns_confirmed["count"] += 1
                self._emit_telemetry(
                    telemetry_events,
                    "DB_VULNS_CONFIRMED",
                    db_vulns_confirmed["count"],
                    telemetry_hook,
                )
            if _SCHEMA_RE.search(line):
                table_schema_mapped["count"] += 1
                self._emit_telemetry(
                    telemetry_events,
                    "TABLE_SCHEMA_MAPPED",
                    table_schema_mapped["count"],
                    telemetry_hook,
                )
            if _DBMS_RE.search(line):
                self._emit_telemetry(
                    telemetry_events,
                    "EventLog",
                    "DATABASE_BREACH:FALLING_GOLD_HEX",
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

            if temp_input_file is not None:
                try:
                    temp_input_file.unlink(missing_ok=True)
                    temp_input_file.parent.rmdir()
                except OSError:
                    pass

        stdout = "".join(stdout_lines)[: self.MAX_STDIO_CHARS]
        stderr = "".join(stderr_lines)[: self.MAX_STDIO_CHARS]

        if self._is_rate_limited(stdout, stderr):
            status = "cooldown"
            self._emit_telemetry(telemetry_events, "AGENT_STATUS", "COOLDOWN", telemetry_hook)

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
        enriched_context["telemetry"] = telemetry_events
        enriched_context["db_vulns_confirmed"] = db_vulns_confirmed["count"]
        enriched_context["table_schema_mapped"] = table_schema_mapped["count"]
        enriched_context["session_dir"] = str(self._session_dir_for_target(target))
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

    def _safety_precheck(self, *, target: str, options: dict[str, Any]) -> dict[str, Any]:
        binary = shutil.which("sqlmap")
        if not binary:
            return {"blocked": True, "reason": "sqlmap binary not found in PATH"}

        environment_tag = str(
            options.get("environment_tag") or os.getenv("K1_ENVIRONMENT_TAG", "staging")
        ).strip().lower()
        phase = str(options.get("scan_phase", "testing")).strip().lower()
        deep_dive = bool(options.get("deep_dive", False)) or phase == "exploitation"

        if environment_tag == "production" and deep_dive and not bool(options.get("production_authorized", False)):
            return {
                "blocked": True,
                "reason": "Production deep-dive blocked: explicit production_authorized=true required",
            }

        proxy = self._resolve_proxy(options)
        use_tor = self._resolve_tor(options)
        if not proxy and not use_tor:
            return {
                "blocked": True,
                "reason": "Sovereign OPSEC violation: sqlmap requires --proxy or --tor",
            }

        return {"blocked": False}

    @staticmethod
    def _resolve_proxy(options: dict[str, Any]) -> str | None:
        for key in ("proxy", "K1_SQLMAP_PROXY", "ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY"):
            value = options.get(key) if key in options else os.getenv(key)
            if value:
                token = str(value).strip()
                if token:
                    return token
        return None

    @staticmethod
    def _resolve_tor(options: dict[str, Any]) -> bool:
        if bool(options.get("use_tor", False)):
            return True
        return os.getenv("K1_USE_TOR", "false").strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _normalize_listener_input(value: Any) -> list[str]:
        if isinstance(value, str):
            return [line.strip() for line in value.splitlines() if line.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _session_dir_for_target(self, target: str) -> Path:
        digest = hashlib.sha1(target.encode("utf-8", errors="ignore")).hexdigest()[:16]
        return self._sessions_root / digest

    @staticmethod
    def _build_vuln_hash(registry: DatabaseSecurityRegistry) -> str:
        material = "|".join(
            [
                registry.db_technology.lower(),
                registry.injection_point.lower(),
                registry.vuln_parameter.lower(),
                (registry.target_url or "").lower(),
            ]
        )
        return hashlib.sha256(material.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _extract_records(raw_output: str, phase_hint: str) -> list[SqlmapRawRecord]:
        records: list[SqlmapRawRecord] = []

        dbms_match = _DBMS_RE.search(raw_output)
        dbms = dbms_match.group(1).strip() if dbms_match else "unknown"

        payload_match = _PAYLOAD_RE.search(raw_output)
        payload = payload_match.group(1).strip() if payload_match else None

        param_matches = _PARAM_RE.findall(raw_output)
        if param_matches:
            for parameter, place in param_matches:
                place_norm = place.strip().lower().replace(" ", "_")
                records.append(
                    SqlmapRawRecord(
                        dbms=dbms,
                        place=place_norm,
                        parameter=parameter.strip(),
                        payload=payload,
                        phase=phase_hint,
                        confidence=0.9,
                        evidence=f"Parameter {parameter} injectable at {place}",
                    )
                )

        if not records and _VULN_RE.search(raw_output):
            records.append(
                SqlmapRawRecord(
                    dbms=dbms,
                    place="unknown",
                    parameter="unknown",
                    payload=payload,
                    phase=phase_hint,
                    confidence=0.75,
                    evidence="sqlmap output contained vulnerability markers",
                )
            )

        return records

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

    def _load_runtime_environment(self) -> dict[str, Any]:
        interfaces = os.getenv("K1_VPN_INTERFACES", "").strip()
        if interfaces:
            vpn_interfaces = tuple(item.strip() for item in interfaces.split(",") if item.strip())
        else:
            vpn_interfaces = _DEFAULT_VPN_INTERFACES

        proxy_enabled = os.getenv("K1_USE_PROXIES", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        return {
            "vpn_interfaces": vpn_interfaces,
            "vpn_up_interfaces": self._detect_up_interfaces(vpn_interfaces),
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
