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
from typing import Any

from pydantic import ValidationError

from apps.backend.src.core.protocol import KaisonResult, KaisonResultMetadata

from ..base_tool_agent import BaseToolAgent
from .schemas import AmassNormalizedAsset, AmassRawRecord

_HIGH_SIGNAL_KEYWORDS = {
    "admin", "api", "staging", "internal", "jenkins", "grafana",
    "vault", "k8s", "dev", "portal", "dashboard", "backend",
    "gateway", "graphql", "rest", "swagger", "debug", "mgmt",
}
_NOISE_KEYWORDS = {"mail", "smtp", "ftp", "cdn", "mx", "pop", "imap"}
_PHASE_DNS_BRUTE = "DNS_BRUTE"
_PHASE_SCRAPING = "SCRAPING"
_PHASE_ARCHIVE = "ARCHIVE"
_RATE_LIMIT_RE = re.compile(
    r"(429|rate[\s_-]*limit|too many requests|quota exceeded|api.*limit)",
    re.IGNORECASE,
)
_DEFAULT_VPN_INTERFACES = ("tun0", "wg0", "vpn0")


class AmassAgent(BaseToolAgent):
    TOOL_NAME = "amass"
    DEFAULT_TIMEOUT_SECONDS = 900

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._runtime_environment = self._load_runtime_environment()

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        binary = str(opts.get("binary_path") or opts.get("binary") or "amass")
        mode = str(opts.get("mode", "enum")).strip().lower()
        config_path = str(opts.get("config", "")).strip()

        if mode == "intel" or opts.get("intel"):
            cmd = [binary, "intel", "-d", target, "-whois", "-json", "-"]
        else:
            cmd = [binary, "enum", "-d", target]
            sub_mode = str(opts.get("sub_mode", "passive")).strip().lower()
            active_mode = bool(opts.get("active")) or sub_mode == "active"
            if not active_mode:
                cmd.append("-passive")
            if opts.get("brute"):
                cmd.append("-brute")
            cmd += ["-json", "-"]

        if config_path:
            cmd += ["-config", config_path]
        resolvers_file = str(opts.get("resolvers_file", "")).strip()
        if resolvers_file:
            cmd += ["-rf", resolvers_file]
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for raw_line in raw_output.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            normalized = self._parse_amass_json_line(line)
            if normalized is None:
                continue
            fqdn = normalized.fqdn.lower()
            if not (fqdn == target.lower() or fqdn.endswith(f".{target.lower()}")):
                continue
            findings.append({
                "type": "subdomain",
                "subdomain": normalized.fqdn,
                "value": normalized.fqdn,
                "target": target,
                "severity": "info",
                "confidence": 0.9,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": normalized.model_dump(mode="json"),
                "context": {
                    "fqdn": normalized.fqdn,
                    "ip_registry": normalized.ip_registry,
                    "intel_origin": normalized.intel_origin,
                    "tag": normalized.tag or "",
                },
                "recommended_next_tools": ["dnsx"],
                "recommended_next_actions": ["resolve_dns"],
            })
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()
        for item in findings:
            value = item["value"].lower()
            if f"{item['target'].lower()}|subdomain|{value}" in known:
                noise.append(item)
                continue

            label = item["subdomain"].lower().split(".")[0]
            if any(kw in label for kw in _HIGH_SIGNAL_KEYWORDS):
                item["signal_reason"] = "high_signal_keyword"
                item["severity"] = "medium"
                signal.append(item)
            elif any(kw in label for kw in _NOISE_KEYWORDS):
                item["noise_reason"] = "low_signal_keyword"
                noise.append(item)
            else:
                signal.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        subdomains = [s["subdomain"] for s in signal]
        asn_note = (
            "Run: amass intel -org '<Company Name>' to find related ASNs. "
            "Then enumerate each ASN for related infrastructure."
        )
        return {
            "next_agent": "dnsx",
            "action": "resolve_subdomains",
            "target": target,
            "input_subdomains": subdomains,
            "asn_enumeration_note": asn_note,
            "instructions": (
                "Combine amass results with subfinder output, deduplicate with sort -u, "
                "then feed combined list to dnsx for DNS resolution."
            ),
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
        telemetry_events: list[dict[str, Any]] = []
        telemetry_hook = opts.get("telemetry_hook")

        self._emit_telemetry(telemetry_events, "AGENT_STATUS", "ACTIVE", telemetry_hook)
        self._emit_telemetry(
            telemetry_events,
            "CURRENT_PHASE",
            _PHASE_SCRAPING,
            telemetry_hook,
        )

        started_at = datetime.now(UTC)
        monitor = ResourceMonitor()

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        process: subprocess.Popen[str] | None = None
        kill_telemetry: dict[str, Any] = {}
        status = "failure"
        exit_code = 127
        phase_state = {"current_phase": _PHASE_SCRAPING}
        discovery_counter = {"count": 0}

        previous_sigterm = None
        sigterm_installed = False
        sigterm_requested = {"requested": False}

        def _on_stdout_line(line: str) -> None:
            normalized = self._parse_amass_json_line(line)
            if normalized is None:
                return
            discovery_counter["count"] += 1
            discovered_phase = self._infer_phase(normalized)
            if discovered_phase != phase_state["current_phase"]:
                phase_state["current_phase"] = discovered_phase
                self._emit_telemetry(
                    telemetry_events,
                    "CURRENT_PHASE",
                    discovered_phase,
                    telemetry_hook,
                )
            self._emit_telemetry(
                telemetry_events,
                "DISCOVERY_COUNT",
                discovery_counter["count"],
                telemetry_hook,
            )

        def _on_sigterm(_: int, __: Any) -> None:
            sigterm_requested["requested"] = True
            if process is not None and process.poll() is None:
                self._kill_process_group(process)  # type: ignore[arg-type]

        if not preflight.get("binary_available", False):
            stderr_text = str(preflight.get("error", "amass binary unavailable"))
            ended_at = datetime.now(UTC)
            runtime_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))
            result = self.map_output(
                target=target,
                command=command,
                stdout="",
                stderr=stderr_text,
                exit_code=127,
                started_at=started_at,
                ended_at=ended_at,
                runtime_ms=runtime_ms,
                mission_id=mission_id,
                status="failure",
                options=opts,
            )
            result = result.model_copy(
                update={
                    "target_context": {
                        **result.target_context,
                        "preflight": preflight,
                        "telemetry": telemetry_events,
                    }
                }
            )
            return result

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
            exit_code = -1

            stdout_thread = threading.Thread(
                target=self._consume_stream,
                args=(process.stdout, stdout_lines, _on_stdout_line),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self._consume_stream,
                args=(process.stderr, stderr_lines, None),
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
                kill_telemetry = self._kill_process_group(process)  # type: ignore[arg-type]

            stdout_thread.join(timeout=2.0)
            stderr_thread.join(timeout=2.0)

        except OSError as exc:
            status = "failure"
            exit_code = 127
            stderr_lines.append(str(exc))
        finally:
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

        self._emit_telemetry(
            telemetry_events,
            "DISCOVERY_COUNT",
            discovery_counter["count"],
            telemetry_hook,
        )

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
        enriched_context["current_phase"] = phase_state["current_phase"]
        if kill_telemetry:
            enriched_context["process_termination"] = kill_telemetry

        result = result.model_copy(update={"target_context": enriched_context, "status": status})

        deduped_findings = self._filter_duplicates(target, result.findings)
        if len(deduped_findings) != len(result.findings):
            adjusted_status = "partial" if result.status == "success" else result.status
            result = result.model_copy(
                update={
                    "status": adjusted_status,
                    "findings": deduped_findings,
                }
            )

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
        return result

    def _preflight(self, *, command: list[str], options: dict[str, Any]) -> dict[str, Any]:
        binary = command[0] if command else "amass"
        binary_path = shutil.which(binary) if not Path(binary).is_file() else str(Path(binary))
        config_path = self._resolve_config_path(options)
        version = ""

        if binary_path:
            for args in (["version"], ["-version"]):
                try:
                    proc = subprocess.run(
                        [binary_path, *args],
                        capture_output=True,
                        text=True,
                        timeout=8,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    continue
                candidate = (proc.stdout or proc.stderr or "").strip()
                if candidate:
                    version = candidate
                    break

        config_exists = bool(config_path and config_path.exists())
        return {
            "binary_requested": binary,
            "binary_path": binary_path,
            "binary_available": bool(binary_path),
            "version": version,
            "config_ini_path": str(config_path) if config_path else None,
            "config_ini_available": config_exists,
            "api_sources_configured": self._config_has_sources(config_path) if config_exists else False,
            "runtime_environment": self._runtime_environment,
            "error": None if binary_path else "amass binary not found in PATH",
        }

    def _resolve_config_path(self, options: dict[str, Any]) -> Path | None:
        explicit = str(options.get("config", "")).strip()
        if explicit:
            return Path(explicit).expanduser()

        env_path = os.getenv("AMASS_CONFIG_PATH", "").strip()
        if env_path:
            return Path(env_path).expanduser()

        candidates = [
            Path.home() / ".config" / "amass" / "config.ini",
            Path.home() / ".amass" / "config.ini",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    @staticmethod
    def _config_has_sources(config_path: Path | None) -> bool:
        if config_path is None or not config_path.exists():
            return False
        try:
            content = config_path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            return False
        providers = ("censys", "binaryedge", "shodan", "virustotal", "securitytrails", "whoisxml")
        return any(provider in content for provider in providers)

    def _load_runtime_environment(self) -> dict[str, Any]:
        interfaces = os.getenv("K1_VPN_INTERFACES", "").strip()
        if interfaces:
            vpn_interfaces = tuple(item.strip() for item in interfaces.split(",") if item.strip())
        else:
            vpn_interfaces = _DEFAULT_VPN_INTERFACES
        proxy_chain = os.getenv("K1_PROXYCHAINS_FILE", "").strip()
        proxy_enabled = os.getenv("K1_USE_PROXIES", "false").strip().lower() in {"1", "true", "yes", "on"}
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

    def _parse_amass_json_line(self, line: str) -> AmassNormalizedAsset | None:
        token = line.strip()
        if not token or not token.startswith("{"):
            return None
        try:
            raw = AmassRawRecord.model_validate_json(token)
            return AmassNormalizedAsset.from_raw(raw)
        except ValidationError:
            return None
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _infer_phase(asset: AmassNormalizedAsset) -> str:
        origin = asset.intel_origin.lower()
        tag = (asset.tag or "").lower()
        if "brute" in origin or "brute" in tag:
            return _PHASE_DNS_BRUTE
        if any(token in origin for token in ("archive", "wayback", "crt", "cert", "historic")):
            return _PHASE_ARCHIVE
        return _PHASE_SCRAPING

    @staticmethod
    def _consume_stream(
        stream: Any,
        collector: list[str],
        on_line: Any | None,
    ) -> None:
        if stream is None:
            return
        try:
            for line in iter(stream.readline, ""):
                if line == "":
                    break
                collector.append(line)
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
        corpus = f"{stdout}\n{stderr}"
        return _RATE_LIMIT_RE.search(corpus) is not None


class ResourceMonitor:
    """Local execution telemetry without importing the entire base monitor internals."""

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
