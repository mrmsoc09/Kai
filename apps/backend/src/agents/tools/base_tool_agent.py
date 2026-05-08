from __future__ import annotations

import json
import os
import resource
import signal
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apps.backend.src.core.protocol import (
    FindingType,
    KaisonFinding,
    KaisonResult,
    KaisonResultMetadata,
    Severity,
)
from apps.backend.src.core.governor import StealthWrapper
from apps.backend.src.core.docker_executor import get_executor as _get_docker_executor
from apps.backend.src.agents.tools.handoff_report import HandoffReport
from apps.backend.src.tools.knowledge.loader import ToolKnowledgeLoader
from apps.backend.src.tools.knowledge.interpreter import ToolOutputInterpreter
from apps.backend.src.tools.knowledge.executor import KnowledgeAwareExecutor


@dataclass(slots=True)
class _ResourceSnapshot:
    monotonic_s: float
    process_cpu_s: float
    child_user_s: float
    child_system_s: float
    child_max_rss_kb: int


class ResourceMonitor:
    """Captures lightweight CPU/memory telemetry across a tool execution."""

    def __init__(self) -> None:
        self._start = self._capture()

    def finish(self) -> dict[str, Any]:
        end = self._capture()
        wall_s = max(0.0, end.monotonic_s - self._start.monotonic_s)
        cpu_s = max(0.0, end.process_cpu_s - self._start.process_cpu_s)
        child_user_s = max(0.0, end.child_user_s - self._start.child_user_s)
        child_system_s = max(0.0, end.child_system_s - self._start.child_system_s)
        max_rss_kb = max(end.child_max_rss_kb, self._start.child_max_rss_kb)

        return {
            "wall_time_s": round(wall_s, 6),
            "cpu_time_s": round(cpu_s, 6),
            "child_user_cpu_s": round(child_user_s, 6),
            "child_system_cpu_s": round(child_system_s, 6),
            "child_max_rss_kb": int(max_rss_kb),
        }

    @staticmethod
    def _capture() -> _ResourceSnapshot:
        children = resource.getrusage(resource.RUSAGE_CHILDREN)
        return _ResourceSnapshot(
            monotonic_s=time.monotonic(),
            process_cpu_s=time.process_time(),
            child_user_s=float(children.ru_utime),
            child_system_s=float(children.ru_stime),
            child_max_rss_kb=int(children.ru_maxrss),
        )


class BaseToolAgent(ABC):
    """
    Base interface for CLI-backed specialist agents.

    Required implementation points for each specialist:
      - build_command(): normalize target/options into a safe argv list
      - map_output(): transform raw process output into a strict KaisonResult
    """

    TOOL_NAME: str = ""
    DEFAULT_TIMEOUT_SECONDS: int = 300
    TERMINATION_GRACE_SECONDS: float = 1.5
    MAX_STDIO_CHARS: int = 200_000

    def __init__(self, memory_root: str | Path | None = None) -> None:
        if not self.TOOL_NAME:
            raise ValueError("TOOL_NAME must be defined in subclass")

        if memory_root is None:
            memory_root = Path(__file__).resolve().parent / self.TOOL_NAME / "memory"
        self.memory_dir = Path(memory_root)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._memory_path = self.memory_dir / "known_assets.jsonl"
        self._scan_history_path = self.memory_dir / "scan_history.jsonl"
        self._findings_correlation_path = self.memory_dir / "findings_correlation.jsonl"
        self._scan_history_path.touch(exist_ok=True)
        self._findings_correlation_path.touch(exist_ok=True)

        # Initialize tool knowledge loader
        self._knowledge_loader = self._initialize_knowledge_loader()
        self._tool_knowledge: dict[str, Any] | None = None
        self._interpreter: ToolOutputInterpreter | None = None
        self._executor: KnowledgeAwareExecutor | None = None
        self._last_interpretation_summary: str = ""

        if self._knowledge_loader:
            try:
                self._tool_knowledge = self._knowledge_loader.get_tool_knowledge(self.TOOL_NAME)
                import logging

                logging.getLogger(__name__).debug(f"Loaded tool knowledge for {self.TOOL_NAME}")
                # Initialize interpreter and executor
                self._interpreter = ToolOutputInterpreter(self._knowledge_loader)
                self._executor = KnowledgeAwareExecutor(self._knowledge_loader, self._interpreter)
            except KeyError:
                import logging

                logging.getLogger(__name__).debug(
                    f"No tool knowledge available for {self.TOOL_NAME}"
                )

    @staticmethod
    def _initialize_knowledge_loader() -> ToolKnowledgeLoader | None:
        """Initialize tool knowledge loader if knowledge file exists.

        Returns:
            ToolKnowledgeLoader instance or None if knowledge file not found.
        """
        knowledge_file = (
            Path(__file__).resolve().parents[3] / "tools" / "knowledge" / "tool_knowledge.yaml"
        )
        if not knowledge_file.exists():
            return None
        try:
            return ToolKnowledgeLoader(knowledge_file)
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Failed to initialize knowledge loader: {e}")
            return None

    def get_tool_knowledge(self) -> dict[str, Any]:
        """Retrieve loaded tool knowledge for this agent's tool.

        Returns:
            Dictionary containing tool knowledge (metadata, concepts, findings, rules, etc.),
            or empty dict if knowledge is not available.
        """
        return self._tool_knowledge or {}

    def get_interpretation_context(self) -> str:
        """Generate agent-ready context string with tool knowledge.

        This context can be injected into agent prompts to provide domain expertise
        for interpreting tool output.

        Returns:
            Formatted text ready for agent injection, or empty string if knowledge unavailable.
        """
        if not self._knowledge_loader or not self._tool_knowledge:
            return ""
        try:
            return self._knowledge_loader.inject_into_context(self.TOOL_NAME, context_format="text")
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Failed to generate interpretation context: {e}")
            return ""

    def execute_with_knowledge(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ) -> dict[str, Any]:
        """Execute this agent's tool using knowledge-aware execution.

        Uses KnowledgeAwareExecutor to interpret tool output automatically,
        returning structured findings with severity, confidence, and next steps.

        Args:
            target: Target domain/IP/host.
            options: Optional execution options.
            mission_id: Mission identifier for tracking.

        Returns:
            Dictionary containing:
            - tool_name: str
            - target: str
            - status: 'success' | 'failure' | 'timeout'
            - raw_output: str
            - interpreted_findings: list[dict]
            - summary: str
            - execution_time: float
            - knowledge_applied: bool
            - severity_distribution: dict[str, int]
        """
        if not self._executor:
            import logging

            logging.getLogger(__name__).warning(
                f"KnowledgeAwareExecutor not initialized for {self.TOOL_NAME}"
            )
            # Fallback to regular execution
            result = self.execute(target, options, mission_id=mission_id)
            return {
                "tool_name": self.TOOL_NAME,
                "target": target,
                "status": result.status,
                "raw_output": "",
                "interpreted_findings": result.findings,
                "summary": f"Executed {self.TOOL_NAME} with {len(result.findings)} findings",
                "execution_time": result.metadata.runtime_ms / 1000.0,
                "knowledge_applied": False,
                "severity_distribution": self._count_findings_by_severity(result.findings),
            }

        # Create a tool executor function that uses self.execute()
        def tool_executor(tool_name: str, target: str, context: dict, timeout: int) -> str:
            result = self.execute(
                target,
                options=context.get("parameters", {}),
                mission_id=mission_id,
            )
            return result.target_context.get("stdout", "")

        # Execute with knowledge
        result = self._executor.execute_with_knowledge(
            self.TOOL_NAME,
            target,
            parameters=options,
            timeout=self.DEFAULT_TIMEOUT_SECONDS,
            tool_executor=tool_executor,
        )

        # Store summary for later retrieval
        self._last_interpretation_summary = result.get("summary", "")

        return result

    def get_interpretation_summary(self) -> str:
        """Return human-readable summary of latest execution interpretation.

        Returns:
            Summary string from last execute_with_knowledge() call,
            or empty string if no interpretation has been run.
        """
        return self._last_interpretation_summary

    @staticmethod
    def _count_findings_by_severity(findings: list[KaisonFinding]) -> dict[str, int]:
        """Count findings by severity level.

        Args:
            findings: List of findings.

        Returns:
            Dictionary with severity counts.
        """
        counts: dict[str, int] = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "INFO": 0,
        }
        for finding in findings:
            severity = finding.severity.value.upper()
            if severity in counts:
                counts[severity] += 1
        return counts

    @abstractmethod
    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        """Build a safe subprocess argv list for the target/tool."""

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
        """
        Map raw process output into strict KaisonResult payloads.

        Backward-compatibility path:
          - if a legacy subclass still exposes parse_output/filter_noise helpers,
            they are adapted into strict KaisonFinding/KaisonResult objects.
        """
        parser = getattr(self, "parse_output", None)
        if not callable(parser):
            raise NotImplementedError(
                f"{self.__class__.__name__} must implement map_output() or legacy parse_output()"
            )

        parser_input = stdout
        output_recovered = False
        if not parser_input.strip():
            recovered_output = self._recover_output_from_artifacts(command=command, options=options)
            if recovered_output:
                parser_input = recovered_output
                output_recovered = True

        parsed = parser(parser_input, target)
        parsed_items = parsed if isinstance(parsed, list) else []

        signal_items = parsed_items
        noise_items: list[dict[str, Any]] = []
        noise_filter = getattr(self, "filter_noise", None)
        if callable(noise_filter):
            try:
                filtered_signal, filtered_noise = noise_filter(parsed_items)
                if isinstance(filtered_signal, list):
                    signal_items = filtered_signal
                if isinstance(filtered_noise, list):
                    noise_items = filtered_noise
            except Exception:
                signal_items = parsed_items
                noise_items = []

        handoff_payload = self._build_handoff_report_payload(
            target=target,
            signal_items=signal_items,
            noise_items=noise_items,
            options=options,
            started_at=started_at,
        )

        findings = [self._legacy_item_to_finding(item, target) for item in signal_items]
        if status in {"failure", "timeout"} and not findings:
            findings.append(
                KaisonFinding(
                    finding_type=FindingType.CONFIG,
                    value=f"{self.TOOL_NAME}:telemetry:{status}",
                    source_agent=self.TOOL_NAME,
                    confidence=1.0,
                    severity=Severity.INFO,
                    raw_evidence={
                        "target": target,
                        "command": command,
                        "exit_code": exit_code,
                        "stderr": stderr[:4000],
                    },
                )
            )

        target_context: dict[str, Any] = {
            "target": target,
            "command": command,
            "exit_code": exit_code,
            "status": status,
            "stderr": stderr[:4000],
            "legacy_parsed_count": len(parsed_items),
            "legacy_signal_count": len(signal_items),
            "legacy_noise_count": len(noise_items),
            "output_recovered_from_artifact": output_recovered,
            "handoff_report": handoff_payload,
        }
        if options:
            target_context["options"] = options

        return KaisonResult(
            mission_id=mission_id,
            source_agent=self.TOOL_NAME,
            status=status,
            target_context=target_context,
            metadata=KaisonResultMetadata(
                started_at=started_at,
                ended_at=ended_at,
                runtime_ms=runtime_ms,
            ),
            findings=findings,
        )

    def docker_image_available(self) -> bool:
        """Return True when this tool's Docker image is built and the daemon is reachable."""
        executor = _get_docker_executor()
        return executor.image_exists(executor.tool_image(self.TOOL_NAME))

    def execute(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        """
        Execute tool command with timeout/stdio capture and CDS normalization.

        Execution order:
          1. Docker container (``kai-<TOOL_NAME>``), if image is present.
          2. Local subprocess fallback (requires binary on PATH).

        Subclasses that override ``execute()`` and guard on ``fixture_data``
        can opt in to live execution by calling ``super().execute()`` when
        ``fixture_data`` is absent and ``self.docker_image_available()`` is True.

        Hardening:
          - ``shell=False`` enforced on all subprocess calls
          - process-group kill on timeout to avoid zombies
          - resource telemetry emitted into ``target_context.resource_usage``
        """
        opts = options or {}
        timeout_seconds = max(1, int(opts.get("timeout_seconds", self.DEFAULT_TIMEOUT_SECONDS)))
        command = self.build_command(target, opts)

        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(x, str) and x for x in command)
        ):
            raise ValueError("build_command() must return a non-empty list[str]")

        started_at = datetime.now(UTC)
        monitor = ResourceMonitor()

        stdout = ""
        stderr = ""
        exit_code = -1
        status = "failure"
        kill_telemetry: dict[str, Any] = {}

        process: subprocess.Popen[bytes] | None = None
        stealth_context = None
        used_docker = False
        try:
            stealth_context = StealthWrapper.prepare_sync_command(
                command,
                target=target,
                metadata={
                    "tool_name": self.TOOL_NAME,
                    "waf_detected": bool(opts.get("waf_detected", False)),
                    "waf_vendor": opts.get("waf_vendor"),
                },
            )
            command = stealth_context.command

            # --- Docker execution path -------------------------------------------
            # cmd_args strips the binary name: ENTRYPOINT is already set in the
            # Dockerfile, so we only pass the arguments that follow the binary.
            docker_result = self._try_docker(command, timeout_seconds, opts)
            if docker_result is not None:
                used_docker = True
                stdout = docker_result.stdout
                stderr = docker_result.stderr
                exit_code = docker_result.exit_code
                if exit_code == 124:
                    status = "timeout"
                    stderr = f"timeout_exceeded:{timeout_seconds}s {stderr}".strip()
                else:
                    status = "success" if exit_code == 0 else "failure"
            else:
                # --- Local subprocess fallback ------------------------------------
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=False,
                    shell=False,
                    start_new_session=True,
                )

                out_bytes, err_bytes = process.communicate(timeout=timeout_seconds)
                stdout = self._decode_stream(out_bytes)
                stderr = self._decode_stream(err_bytes)
                exit_code = int(process.returncode or 0)
                status = "success" if exit_code == 0 else "failure"

        except subprocess.TimeoutExpired as exc:
            stdout = self._decode_stream(exc.stdout)
            stderr = self._decode_stream(exc.stderr)
            exit_code = 124
            status = "timeout"
            kill_telemetry = self._kill_process_group(process)
            stderr = f"timeout_exceeded:{timeout_seconds}s {stderr}".strip()

        except OSError as exc:
            exit_code = 127
            status = "failure"
            stderr = str(exc)

        finally:
            if not used_docker and process is not None and process.poll() is None:
                kill_telemetry = self._kill_process_group(process)
            StealthWrapper.finalize_context(
                stealth_context,
                stdout=stdout,
                stderr=stderr,
            )

        stdout = stdout[: self.MAX_STDIO_CHARS]
        stderr = stderr[: self.MAX_STDIO_CHARS]

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
        enriched_context["execution_mode"] = "docker" if used_docker else "local"
        if kill_telemetry:
            enriched_context["process_termination"] = kill_telemetry
        result = result.model_copy(update={"target_context": enriched_context})

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
            target=target, findings=deduped_findings, started_at=started_at
        )
        self._persist_memory(target, deduped_findings)
        return result

    def load_memory(self) -> set[str]:
        """
        Load dedupe keys from local JSONL storage.

        Format per line:
          {"dedupe_key": "<target|finding_type|value>", "timestamp": "..."}
        """
        seen: set[str] = set()
        if not self._memory_path.exists():
            return seen

        with self._memory_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                dedupe_key = str(record.get("dedupe_key", "")).strip()
                if dedupe_key:
                    seen.add(dedupe_key)

        return seen

    def _filter_duplicates(self, target: str, findings: list[KaisonFinding]) -> list[KaisonFinding]:
        known = self.load_memory()
        session_seen: set[str] = set()
        filtered: list[KaisonFinding] = []

        for finding in findings:
            key = self._dedupe_key(target, finding)
            if key in known or key in session_seen:
                continue
            session_seen.add(key)
            filtered.append(finding)

        return filtered

    def _persist_memory(self, target: str, findings: list[KaisonFinding]) -> None:
        if not findings:
            return

        now = datetime.now(UTC).isoformat()
        with self._memory_path.open("a", encoding="utf-8") as handle:
            for finding in findings:
                record = {
                    "dedupe_key": self._dedupe_key(target, finding),
                    "timestamp": now,
                    "source_agent": self.TOOL_NAME,
                }
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _record_scan_history(
        self,
        *,
        target: str,
        command: list[str],
        status: str,
        findings: list[KaisonFinding],
        started_at: datetime,
        runtime_ms: int,
        handoff_report: Any,
    ) -> None:
        record = {
            "scan_id": f"{self.TOOL_NAME}-{int(started_at.timestamp() * 1000)}",
            "target": target,
            "timestamp": started_at.isoformat(),
            "command": command,
            "result_count": len(findings),
            "signal_count": len(findings),
            "noise_count": 0,
            "findings": [
                {
                    "finding_type": finding.finding_type.value,
                    "value": finding.value,
                    "severity": finding.severity.value,
                    "confidence": finding.confidence,
                }
                for finding in findings
            ],
            "metadata": {
                "tool": self.TOOL_NAME,
                "status": status,
                "runtime_ms": runtime_ms,
                "handoff_report_present": isinstance(handoff_report, dict),
            },
        }
        with self._scan_history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _record_findings_correlation(
        self, *, target: str, findings: list[KaisonFinding], started_at: datetime
    ) -> None:
        if not findings:
            return
        timestamp = started_at.isoformat()
        with self._findings_correlation_path.open("a", encoding="utf-8") as handle:
            for finding in findings:
                record = {
                    "finding_id": str(finding.finding_id),
                    "tool": self.TOOL_NAME,
                    "target": target,
                    "value": finding.value,
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                    "seen_count": 1,
                    "confirmed": False,
                    "tags": [finding.finding_type.value, finding.severity.value],
                }
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _build_handoff_report_payload(
        self,
        *,
        target: str,
        signal_items: list[dict[str, Any]],
        noise_items: list[dict[str, Any]],
        options: dict[str, Any] | None,
        started_at: datetime,
    ) -> dict[str, Any]:
        generator = getattr(self, "_generate_next_agent_instructions", None)
        next_agent_instructions: dict[str, Any] = {}
        if callable(generator):
            try:
                generated = generator(signal_items, target)
                if isinstance(generated, dict):
                    next_agent_instructions = generated
            except Exception as exc:
                next_agent_instructions = {"generation_error": str(exc)}

        report = HandoffReport(
            tool=self.TOOL_NAME,
            target=target,
            scan_id=f"{self.TOOL_NAME}-{int(started_at.timestamp() * 1000)}",
            signal_findings=signal_items,
            noise_findings=noise_items,
            next_agent_instructions=next_agent_instructions,
            metadata={"options_supplied": bool(options)},
        )
        return report.to_dict()

    def _try_docker(
        self,
        command: list[str],
        timeout: int,
        opts: dict[str, Any],
    ) -> Any | None:
        """
        Attempt Docker execution; return DockerExecutionResult or None.

        Returns None when:
          - Docker daemon is unreachable
          - The ``kai-<TOOL_NAME>`` image does not exist locally
          - Docker execution is explicitly disabled via ``KAI_DOCKER_EXEC=false``
        """
        if os.environ.get("KAI_DOCKER_EXEC", "true").lower() in {"0", "false", "no"}:
            return None

        executor = _get_docker_executor()
        image = executor.tool_image(self.TOOL_NAME)
        if not executor.image_exists(image):
            return None

        # cmd_args: drop command[0] (the binary) because the Dockerfile
        # ENTRYPOINT already names the binary.
        cmd_args = command[1:]

        # Mount the host's tmp dir so tools that write files (e.g. nmap -oX)
        # produce host-readable artifacts at the same path.
        tmp_host_dir: str | None = opts.get("artifact_dir") or opts.get("tmp_dir")
        if tmp_host_dir is None:
            # Detect output file flags and use their parent dir.
            for idx, token in enumerate(command):
                if token in {"-o", "--output", "-oX", "-oN", "-oG"} and idx + 1 < len(command):
                    tmp_host_dir = str(Path(command[idx + 1]).parent)
                    break

        return executor.execute_in_container(
            image,
            cmd_args,
            timeout=timeout,
            tmp_host_dir=tmp_host_dir,
            max_output_chars=self.MAX_STDIO_CHARS,
            tool_name=self.TOOL_NAME,
        )

    def _kill_process_group(self, process: subprocess.Popen[bytes] | None) -> dict[str, Any]:
        if process is None:
            return {}

        pid = process.pid
        telemetry: dict[str, Any] = {
            "pid": pid,
            "signals_sent": [],
            "grace_seconds": self.TERMINATION_GRACE_SECONDS,
        }

        try:
            os.killpg(pid, signal.SIGTERM)
            telemetry["signals_sent"].append("SIGTERM")
        except ProcessLookupError:
            telemetry["already_exited"] = True
            return telemetry
        except Exception as exc:
            telemetry["terminate_error"] = str(exc)
            return telemetry

        deadline = time.monotonic() + self.TERMINATION_GRACE_SECONDS
        while time.monotonic() < deadline:
            if process.poll() is not None:
                telemetry["terminated"] = True
                return telemetry
            time.sleep(0.05)

        try:
            os.killpg(pid, signal.SIGKILL)
            telemetry["signals_sent"].append("SIGKILL")
            telemetry["terminated"] = True
        except ProcessLookupError:
            telemetry["terminated"] = True
        except Exception as exc:
            telemetry["kill_error"] = str(exc)

        return telemetry

    @staticmethod
    def _decode_stream(value: bytes | str | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value

    def _recover_output_from_artifacts(
        self, *, command: list[str], options: dict[str, Any] | None
    ) -> str:
        """
        Recover tool output when commands write primarily to files (quiet/json modes).

        This is a best-effort fallback used only when stdout is empty.
        """
        candidate_paths: list[str] = []
        if options:
            for key in ("output_file", "output_path", "artifact_path"):
                value = options.get(key)
                if isinstance(value, str) and value.strip():
                    candidate_paths.append(value.strip())

        for idx, token in enumerate(command):
            if token in {"-o", "--output", "-oX", "--output-filename", "-l"}:
                if idx + 1 < len(command):
                    candidate_paths.append(command[idx + 1])
            elif token.startswith("--log-json="):
                candidate_paths.append(token.split("=", 1)[1])

        for raw_path in candidate_paths:
            path = Path(raw_path).expanduser()
            if not path.exists() or not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if content.strip():
                return content[: self.MAX_STDIO_CHARS]

        return ""

    @staticmethod
    def _dedupe_key(target: str, finding: KaisonFinding) -> str:
        finding_type = finding.finding_type.value
        normalized_value = finding.value.strip().lower()
        normalized_target = target.strip().lower()
        return f"{normalized_target}|{finding_type}|{normalized_value}"

    def _legacy_item_to_finding(self, item: Any, target: str) -> KaisonFinding:
        payload = dict(item) if isinstance(item, dict) else {"value": str(item)}
        value = self._coerce_value(payload, target)
        finding_type = self._infer_finding_type(payload, value)
        confidence = self._coerce_confidence(payload.get("confidence", 0.8))
        severity = self._coerce_severity(payload.get("severity"))

        return KaisonFinding(
            finding_type=finding_type,
            value=value,
            source_agent=self.TOOL_NAME,
            confidence=confidence,
            severity=severity,
            raw_evidence=payload,
        )

    @staticmethod
    def _coerce_value(payload: dict[str, Any], target: str) -> str:
        for key in (
            "value",
            "subdomain",
            "port",
            "url",
            "endpoint",
            "secret",
            "vulnerability",
            "name",
        ):
            candidate = payload.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()[:2048]
            if isinstance(candidate, (int, float)):
                return str(candidate)

        fallback = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        if not fallback:
            fallback = target
        return fallback[:2048]

    @staticmethod
    def _infer_finding_type(payload: dict[str, Any], value: str) -> FindingType:
        lowered_keys = {str(k).lower() for k in payload.keys()}
        corpus = " ".join(
            [value.lower()]
            + [
                str(payload.get("signal_reason", "")).lower(),
                str(payload.get("noise_reason", "")).lower(),
            ]
        )

        if "subdomain" in lowered_keys:
            return FindingType.SUBDOMAIN
        if "port" in lowered_keys:
            return FindingType.PORT
        if {"vulnerability", "cve", "template_id", "exploit"}.intersection(lowered_keys):
            return FindingType.VULN
        if {"secret", "credential", "password", "token", "api_key"}.intersection(lowered_keys):
            return FindingType.SECRET
        if any(
            token in corpus
            for token in ("cve-", "xss", "sqli", "rce", "ssrf", "lfi", "vuln", "exploit")
        ):
            return FindingType.VULN
        if any(
            token in corpus for token in ("secret", "credential", "password", "token", "apikey")
        ):
            return FindingType.SECRET
        return FindingType.CONFIG

    @staticmethod
    def _coerce_confidence(value: Any) -> float:
        if isinstance(value, bool):
            return 0.8
        if isinstance(value, (int, float)):
            numeric = float(value)
            if numeric < 0.0:
                return 0.0
            if numeric > 1.0:
                return 1.0
            return numeric
        return 0.8

    @staticmethod
    def _coerce_severity(value: Any) -> Severity:
        if isinstance(value, Severity):
            return value
        if isinstance(value, str):
            token = value.strip().lower()
            try:
                return Severity(token)
            except ValueError:
                return Severity.INFO
        return Severity.INFO
