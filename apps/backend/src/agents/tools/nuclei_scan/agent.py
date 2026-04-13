from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from apps.backend.src.core.protocol import KaisonResult, KaisonResultMetadata

from ..base_tool_agent import BaseToolAgent
from .schemas import NucleiRawRecord, VulnerabilityRegistry

_RATE_LIMIT_RE = re.compile(
    r"(429|rate[\s_-]*limit|too many requests|quota exceeded|request limit)",
    re.IGNORECASE,
)
_DEFAULT_VPN_INTERFACES = ("tun0", "wg0", "vpn0")
_DEFAULT_TEMPLATE_UPDATE_INTERVAL_SECONDS = 6 * 60 * 60
_DEFAULT_SEVERITY = "critical,high,medium"


class NucleiScanAgent(BaseToolAgent):
    TOOL_NAME = "nuclei_scan"
    DEFAULT_TIMEOUT_SECONDS = 900

    # Tech-to-Template Mapping for Smart Selection
    TECH_TEMPLATE_MAP = {
        "spring": "tags/spring,tags/java",
        "django": "tags/django,tags/python",
        "flask": "tags/flask,tags/python",
        "wordpress": "tags/wordpress,tags/wp",
        "php": "tags/php",
        "node": "tags/nodejs",
        "react": "tags/react",
        "angular": "tags/angular",
        "laravel": "tags/laravel",
        "iis": "tags/iis",
        "apache": "tags/apache",
        "nginx": "tags/nginx",
        "kubernetes": "tags/k8s",
        "docker": "tags/docker",
    }

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._runtime_environment = self._load_runtime_environment()
        self._lifecycle_status = "ANALYSIS_IDLE"
        self._telemetry_hook: Callable[[dict[str, Any]], None] | None = None
        self._last_preflight: dict[str, Any] = {}

        self._template_state_path = self.memory_dir / "template_update_state.json"
        self._template_state = self._load_template_state()

        self._vuln_hashes_path = self.memory_dir / "vuln_hashes.jsonl"
        self._known_vuln_hashes = self._load_vuln_hashes()

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def register_telemetry_hook(self, hook: Callable[[dict[str, Any]], None]) -> None:
        self._telemetry_hook = hook

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}

        cmd = ["nuclei", "-silent", "-jsonl"]

        input_file = str(opts.get("input_file", "")).strip()
        if input_file:
            cmd += ["-l", input_file]
        else:
            cmd += ["-u", target]

        tech_list = opts.get("tech_list", [])
        tags = set()
        for tech in tech_list:
            token = str(tech).strip().lower()
            if not token:
                continue
            for mapped_tech, tag_list in self.TECH_TEMPLATE_MAP.items():
                if mapped_tech in token:
                    tags.update(tag_list.split(","))

        if tags:
            cmd += ["-t", ",".join(sorted(tags))]
        elif opts.get("templates"):
            cmd += ["-t", str(opts["templates"]) ]
        else:
            # Fallback to general high-impact template groups.
            cmd += ["-t", "cves,vulnerabilities,misconfiguration,exposure"]

        severity = str(opts.get("severity", _DEFAULT_SEVERITY)).strip().lower()
        if "info" in {item.strip() for item in severity.split(",") if item.strip()}:
            severity = _DEFAULT_SEVERITY
        cmd += ["-s", severity]

        if opts.get("threads"):
            cmd += ["-c", str(max(1, int(opts["threads"]))) ]

        if opts.get("rate_limit"):
            cmd += ["-rl", str(max(1, int(opts["rate_limit"]))) ]

        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        for raw_line in raw_output.splitlines():
            line = raw_line.strip()
            if not line or not line.startswith("{"):
                continue

            registry = self._parse_registry_line(line)
            if registry is None:
                continue

            severity = registry.risk_level
            endpoint = registry.target_endpoint
            vuln_value = f"{registry.vuln_id}@{endpoint}"

            findings.append(
                {
                    "type": "vulnerability",
                    "template_id": registry.vuln_id,
                    "vuln_name": registry.vuln_name,
                    "severity": severity,
                    "value": vuln_value,
                    "target": target,
                    "confidence": 0.95,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": registry.raw_evidence,
                    "context": {
                        "vulnerability_registry": registry.model_dump(mode="json"),
                        "vuln_id": registry.vuln_id,
                        "vuln_name": registry.vuln_name,
                        "risk_level": severity,
                        "target_endpoint": endpoint,
                        "vuln_hash": registry.dedupe_hash,
                        "description": registry.description,
                        "reference": registry.references,
                        "type": registry.vuln_type,
                        "curl_command": registry.curl_command,
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["validate_finding"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal_items: list[dict[str, Any]] = []
        noise_items: list[dict[str, Any]] = []

        known = self.load_memory()
        session_hashes: set[str] = set()

        for item in findings:
            value = str(item.get("value", "")).lower()
            target = str(item.get("target", "")).lower()
            if f"{target}|vulnerability|{value}" in known:
                noise_items.append(item)
                continue

            vuln_hash = str(item.get("context", {}).get("vuln_hash", "")).strip().lower()
            if vuln_hash and (vuln_hash in self._known_vuln_hashes or vuln_hash in session_hashes):
                item["noise_reason"] = "duplicate_vuln_hash"
                noise_items.append(item)
                continue

            if vuln_hash:
                session_hashes.add(vuln_hash)

            severity = str(item.get("severity", "info")).strip().lower()
            if severity in {"critical", "high"}:
                item["signal_reason"] = "high_severity_vulnerability"
                signal_items.append(item)
            elif severity == "medium":
                item["signal_reason"] = "medium_severity_vulnerability"
                signal_items.append(item)
            elif severity == "low":
                item["noise_reason"] = "low_severity_vulnerability"
                noise_items.append(item)
            else:
                item["noise_reason"] = "unsupported_or_info_severity"
                noise_items.append(item)

        return signal_items, noise_items

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        critical = [item for item in signal if str(item.get("severity", "")).lower() == "critical"]
        high = [item for item in signal if str(item.get("severity", "")).lower() == "high"]

        critical_ids = sorted({str(item.get("template_id", "")).strip() for item in critical if item.get("template_id")})

        return {
            "next_agent": "EvidenceAnalystAgent",
            "action": "validate_findings",
            "target": target,
            "critical_findings": critical[:10],
            "high_findings": high[:10],
            "instructions": (
                f"Found {len(critical)} critical and {len(high)} high severity vulnerabilities. "
                "Trigger evidence validation and screenshot capture for confirmed findings. "
                f"Priority templates: {', '.join(critical_ids[:5]) or 'none'}."
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
        preflight = self._preflight(options=opts)
        telemetry_events: list[dict[str, Any]] = []
        telemetry_hook = opts.get("telemetry_hook") or self._telemetry_hook

        template_category = self._resolve_template_category(opts)
        self._emit_telemetry(telemetry_events, "AGENT_STATUS", "SCANNING_TEMPLATES", telemetry_hook)
        self._emit_telemetry(telemetry_events, "SCANNING_TEMPLATES", template_category, telemetry_hook)

        if not preflight.get("docker_available"):
            return self._build_failure_result(
                target=target,
                mission_id=mission_id,
                stderr=str(preflight.get("error", "docker runtime unavailable")),
                preflight=preflight,
                telemetry=telemetry_events,
                status="failure",
            )

        if preflight.get("require_sovereign_network") and not preflight.get("sovereign_network_ok"):
            return self._build_failure_result(
                target=target,
                mission_id=mission_id,
                stderr="Sovereign Network Layer not detected (SOCKS5/VPN unavailable)",
                preflight=preflight,
                telemetry=telemetry_events,
                status="failure",
            )

        started_at = datetime.now(UTC)
        monitor = ResourceMonitor()

        status = "failure"
        exit_code = 127
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        with tempfile.TemporaryDirectory(prefix="k1-nuclei-") as temp_dir:
            temp_path = Path(temp_dir)
            input_targets = self._resolve_input_targets(target, opts)
            targets_file = temp_path / "targets.txt"
            targets_file.write_text("\n".join(input_targets) + "\n", encoding="utf-8")

            command_options = dict(opts)
            command_options["input_file"] = "/k1-input/targets.txt"
            command = self.build_command(target, command_options)
            container_command = self._strip_binary_prefix(command)

            image = str(opts.get("container_image") or "projectdiscovery/nuclei:latest")
            network_mode = str(
                opts.get("docker_network")
                or self._runtime_environment.get("docker_network")
                or "bridge"
            )

            volumes = self._build_container_volumes(temp_path, opts)
            environment = self._build_container_environment(opts)

            vuln_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

            try:
                client = self._get_docker_client()

                if self._should_update_templates(opts):
                    self._run_template_update(
                        client=client,
                        image=image,
                        network_mode=network_mode,
                        volumes=volumes,
                        environment=environment,
                        telemetry=telemetry_events,
                        telemetry_hook=telemetry_hook,
                    )

                container = client.containers.create(
                    image=image,
                    command=container_command,
                    detach=True,
                    stdin_open=False,
                    tty=False,
                    network_mode=network_mode,
                    volumes=volumes,
                    environment=environment,
                    labels={"k1.agent": self.TOOL_NAME, "k1.mission_id": mission_id},
                )

                stop_stream = threading.Event()

                def _log_worker() -> None:
                    try:
                        for chunk in container.logs(stream=True, follow=True):
                            if stop_stream.is_set():
                                break
                            line = self._decode_docker_chunk(chunk).strip()
                            if not line:
                                continue
                            stdout_lines.append(line + "\n")
                            parsed = self._parse_registry_line(line)
                            if parsed is None:
                                continue
                            risk = parsed.risk_level
                            if risk in vuln_counts:
                                vuln_counts[risk] += 1
                            self._emit_telemetry(
                                telemetry_events,
                                "VULNS_FOUND",
                                dict(vuln_counts),
                                telemetry_hook,
                            )
                            if risk == "critical":
                                self._emit_telemetry(
                                    telemetry_events,
                                    "EventLog",
                                    (
                                        "TOP10_PANEL:KINETIC_JITTER_PULSATING_RED:"
                                        f"{parsed.target_endpoint}"
                                    ),
                                    telemetry_hook,
                                )
                    except Exception as exc:  # pragma: no cover - defensive
                        stderr_lines.append(f"log_stream_error:{exc}\n")

                log_thread = threading.Thread(target=_log_worker, daemon=True)

                container.start()
                log_thread.start()

                try:
                    wait_result = container.wait(timeout=timeout_seconds)
                    if isinstance(wait_result, dict):
                        exit_code = int(wait_result.get("StatusCode", 1))
                    else:
                        exit_code = int(wait_result)
                    status = "success" if exit_code == 0 else "failure"
                except Exception as exc:
                    status = "timeout"
                    exit_code = 124
                    stderr_lines.append(f"timeout_exceeded:{timeout_seconds}s {exc}\n")
                    try:
                        container.kill()
                    except Exception:
                        pass

                stop_stream.set()
                log_thread.join(timeout=2.0)

                try:
                    stderr_bytes = container.logs(stdout=False, stderr=True)
                    if isinstance(stderr_bytes, (bytes, bytearray)):
                        stderr_lines.append(self._decode_docker_chunk(stderr_bytes))
                except Exception:
                    pass

                try:
                    container.remove(force=True)
                except Exception:
                    pass

                self._prune_agent_containers(client)

            except RuntimeError as exc:
                status = "failure"
                exit_code = 127
                stderr_lines.append(str(exc))
                command = ["nuclei", "<docker-unavailable>"]
            except Exception as exc:
                status = "failure"
                exit_code = 127
                stderr_lines.append(str(exc))

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
        enriched_context["preflight"] = preflight
        enriched_context["telemetry"] = telemetry_events
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
        self._persist_vuln_hashes(deduped_findings)

        self._lifecycle_status = "ANALYSIS_IDLE"
        self._emit_telemetry(telemetry_events, "AGENT_STATUS", "ANALYSIS_IDLE", telemetry_hook)
        return result

    def _build_failure_result(
        self,
        *,
        target: str,
        mission_id: str,
        stderr: str,
        preflight: dict[str, Any],
        telemetry: list[dict[str, Any]],
        status: str,
    ) -> KaisonResult:
        started_at = datetime.now(UTC)
        ended_at = datetime.now(UTC)
        self._lifecycle_status = "ANALYSIS_IDLE"
        return KaisonResult(
            mission_id=mission_id,
            source_agent=self.TOOL_NAME,
            status=status,
            target_context={
                "target": target,
                "command": ["nuclei", "<docker-mode>"],
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

    def _preflight(self, *, options: dict[str, Any]) -> dict[str, Any]:
        docker_available = shutil.which("docker") is not None
        require_sovereign = bool(options.get("require_sovereign_network")) or os.getenv(
            "K1_REQUIRE_SOVEREIGN_NETWORK", "false"
        ).strip().lower() in {"1", "true", "yes", "on"}

        vpn_up = bool(self._runtime_environment.get("vpn_up_interfaces"))
        proxy_enabled = bool(self._runtime_environment.get("proxychains_enabled"))
        sovereign_ok = vpn_up or proxy_enabled

        return {
            "docker_available": docker_available,
            "runtime_environment": self._runtime_environment,
            "require_sovereign_network": require_sovereign,
            "sovereign_network_ok": sovereign_ok,
            "error": None if docker_available else "docker runtime not found in PATH",
        }

    @staticmethod
    def _resolve_input_targets(target: str, options: dict[str, Any]) -> list[str]:
        if bool(options.get("listener_mode")):
            data = options.get("input_data", [])
            if isinstance(data, str):
                candidates = [line.strip() for line in data.splitlines() if line.strip()]
                if candidates:
                    return candidates
            elif isinstance(data, list):
                candidates = [str(item).strip() for item in data if str(item).strip()]
                if candidates:
                    return candidates

        return [target]

    def _parse_registry_line(self, line: str) -> VulnerabilityRegistry | None:
        token = line.strip()
        if not token or not token.startswith("{"):
            return None

        try:
            raw = NucleiRawRecord.model_validate_json(token)
        except (ValidationError, json.JSONDecodeError):
            return None

        dedupe_hash = self._build_vuln_hash(raw)
        try:
            return VulnerabilityRegistry.from_raw(raw, dedupe_hash=dedupe_hash)
        except ValidationError:
            return None

    @staticmethod
    def _build_vuln_hash(raw: NucleiRawRecord) -> str:
        digest_input = "|".join(
            [
                raw.template_id.strip().lower(),
                (raw.info.severity or "unknown").strip().lower(),
                raw.matched_at.strip().lower(),
                (raw.host or "").strip().lower(),
                (raw.ip or "").strip().lower(),
            ]
        )
        return hashlib.sha256(digest_input.encode("utf-8", errors="ignore")).hexdigest()

    def _build_container_volumes(self, temp_path: Path, options: dict[str, Any]) -> dict[str, dict[str, str]]:
        volumes: dict[str, dict[str, str]] = {
            str(temp_path): {"bind": "/k1-input", "mode": "ro"},
        }

        template_dir = Path(
            str(
                options.get("template_repo_dir")
                or options.get("custom_template_dir")
                or os.getenv("K1_NUCLEI_TEMPLATE_REPO", "runtime/nuclei-templates")
            )
        ).expanduser()
        template_dir.mkdir(parents=True, exist_ok=True)
        volumes[str(template_dir)] = {"bind": "/root/nuclei-templates", "mode": "rw"}
        return volumes

    def _build_container_environment(self, options: dict[str, Any]) -> dict[str, str]:
        env: dict[str, str] = {
            "NUCLEI_TEMPLATES_DIRECTORY": "/root/nuclei-templates",
        }

        if self._runtime_environment.get("proxychains_enabled"):
            for key in ("ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "all_proxy", "https_proxy", "http_proxy"):
                value = str(options.get(key) or os.getenv(key, "")).strip()
                if value:
                    env[key] = value

        return env

    @staticmethod
    def _strip_binary_prefix(command: list[str]) -> list[str]:
        if command and command[0] == "nuclei":
            return command[1:]
        return command

    @staticmethod
    def _decode_docker_chunk(chunk: Any) -> str:
        if isinstance(chunk, bytes):
            return chunk.decode("utf-8", errors="replace")
        return str(chunk)

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

    def _resolve_template_category(self, options: dict[str, Any]) -> str:
        if options.get("templates"):
            return "CUSTOM"
        tech_list = options.get("tech_list", [])
        if tech_list:
            return "TECH_MAPPED"
        return "GENERAL"

    def _should_update_templates(self, options: dict[str, Any]) -> bool:
        if bool(options.get("skip_template_update")):
            return False
        if bool(options.get("major_scan_cycle")):
            return True

        interval = int(options.get("template_update_interval_seconds", _DEFAULT_TEMPLATE_UPDATE_INTERVAL_SECONDS))
        last_update = str(self._template_state.get("last_template_update", "")).strip()
        if not last_update:
            return True

        try:
            last_dt = datetime.fromisoformat(last_update)
        except ValueError:
            return True

        delta = (datetime.now(UTC) - last_dt).total_seconds()
        return delta >= interval

    def _run_template_update(
        self,
        *,
        client: Any,
        image: str,
        network_mode: str,
        volumes: dict[str, dict[str, str]],
        environment: dict[str, str],
        telemetry: list[dict[str, Any]],
        telemetry_hook: Any,
    ) -> None:
        self._emit_telemetry(telemetry, "TEMPLATE_SYNC", "nuclei -ut", telemetry_hook)

        container = client.containers.create(
            image=image,
            command=["-ut"],
            detach=True,
            stdin_open=False,
            tty=False,
            network_mode=network_mode,
            volumes=volumes,
            environment=environment,
            labels={"k1.agent": self.TOOL_NAME, "k1.op": "template-update"},
        )
        container.start()
        wait_result = container.wait(timeout=300)
        status_code = int(wait_result.get("StatusCode", 1)) if isinstance(wait_result, dict) else int(wait_result)
        try:
            container.remove(force=True)
        except Exception:
            pass

        if status_code != 0:
            raise RuntimeError("nuclei template update failed")

        self._template_state["last_template_update"] = datetime.now(UTC).isoformat()
        self._save_template_state()

    @staticmethod
    def _prune_agent_containers(client: Any) -> None:
        try:
            client.containers.prune(filters={"label": "k1.agent=nuclei_scan"})
        except Exception:
            return

    def _get_docker_client(self) -> Any:
        try:
            import docker  # type: ignore
        except ImportError as exc:
            raise RuntimeError("python docker SDK not installed") from exc

        return docker.from_env()

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

        docker_network = os.getenv("K1_SOVEREIGN_DOCKER_NETWORK", "bridge").strip() or "bridge"

        return {
            "vpn_interfaces": vpn_interfaces,
            "vpn_up_interfaces": self._detect_up_interfaces(vpn_interfaces),
            "proxychains_file": proxy_chain or None,
            "proxychains_enabled": proxy_enabled,
            "docker_network": docker_network,
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

    def _load_template_state(self) -> dict[str, Any]:
        if not self._template_state_path.exists():
            return {}
        try:
            payload = json.loads(self._template_state_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save_template_state(self) -> None:
        try:
            self._template_state_path.write_text(
                json.dumps(self._template_state, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
        except OSError:
            return

    def _load_vuln_hashes(self) -> set[str]:
        seen: set[str] = set()
        if not self._vuln_hashes_path.exists():
            return seen

        try:
            for line in self._vuln_hashes_path.read_text(encoding="utf-8", errors="replace").splitlines():
                token = line.strip()
                if not token:
                    continue
                try:
                    payload = json.loads(token)
                except json.JSONDecodeError:
                    continue
                vuln_hash = str(payload.get("vuln_hash", "")).strip().lower()
                if vuln_hash:
                    seen.add(vuln_hash)
        except OSError:
            return seen

        return seen

    def _persist_vuln_hashes(self, findings: list[Any]) -> None:
        if not findings:
            return

        now = datetime.now(UTC).isoformat()
        lines: list[str] = []
        for finding in findings:
            raw_context = getattr(finding, "raw_evidence", {}) if hasattr(finding, "raw_evidence") else {}
            if isinstance(raw_context, dict):
                context = raw_context.get("context", {}) if isinstance(raw_context.get("context"), dict) else {}
            else:
                context = {}
            vuln_hash = str(context.get("vuln_hash", "")).strip().lower()
            if not vuln_hash:
                continue
            if vuln_hash in self._known_vuln_hashes:
                continue
            self._known_vuln_hashes.add(vuln_hash)
            lines.append(
                json.dumps(
                    {
                        "vuln_hash": vuln_hash,
                        "timestamp": now,
                        "source_agent": self.TOOL_NAME,
                    },
                    ensure_ascii=True,
                )
            )

        if not lines:
            return

        try:
            with self._vuln_hashes_path.open("a", encoding="utf-8") as handle:
                for line in lines:
                    handle.write(line + "\n")
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
