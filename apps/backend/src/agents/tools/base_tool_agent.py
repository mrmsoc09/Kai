from __future__ import annotations

import json
import os
import resource
import signal
import subprocess
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

        parsed = parser(stdout, target)
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

    def execute(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        """
        Execute tool command with timeout/stdio capture and CDS normalization.

        Hardening:
          - `shell=False` enforced
          - process-group kill on timeout to avoid zombies
          - resource telemetry emitted into target_context.resource_usage
        """
        opts = options or {}
        timeout_seconds = max(1, int(opts.get("timeout_seconds", self.DEFAULT_TIMEOUT_SECONDS)))
        command = self.build_command(target, opts)

        if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
            raise ValueError("build_command() must return a non-empty list[str]")

        started_at = datetime.now(UTC)
        monitor = ResourceMonitor()

        stdout = ""
        stderr = ""
        exit_code = -1
        status = "failure"
        kill_telemetry: dict[str, Any] = {}

        process: subprocess.Popen[bytes] | None = None
        try:
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
            if process is not None and process.poll() is None:
                kill_telemetry = self._kill_process_group(process)

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
        for key in ("value", "subdomain", "port", "url", "endpoint", "secret", "vulnerability", "name"):
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
            + [str(payload.get("signal_reason", "")).lower(), str(payload.get("noise_reason", "")).lower()]
        )

        if "subdomain" in lowered_keys:
            return FindingType.SUBDOMAIN
        if "port" in lowered_keys:
            return FindingType.PORT
        if {"vulnerability", "cve", "template_id", "exploit"}.intersection(lowered_keys):
            return FindingType.VULN
        if {"secret", "credential", "password", "token", "api_key"}.intersection(lowered_keys):
            return FindingType.SECRET
        if any(token in corpus for token in ("cve-", "xss", "sqli", "rce", "ssrf", "lfi", "vuln", "exploit")):
            return FindingType.VULN
        if any(token in corpus for token in ("secret", "credential", "password", "token", "apikey")):
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
