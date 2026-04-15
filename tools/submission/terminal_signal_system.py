from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
from typing import Any


RESULT_RE = re.compile(r"EXPLOITATION_RESULT:\s*([+-])", re.IGNORECASE)
EVIDENCE_RE = re.compile(r"EVIDENCE:\s*(.+)", re.IGNORECASE)
REASON_RE = re.compile(r"REASON:\s*(.+)", re.IGNORECASE)
TIMESTAMP_RE = re.compile(r"TIMESTAMP:\s*([0-9T:+.Z-]+)", re.IGNORECASE)


@dataclass(slots=True)
class TerminalSignalParseResult:
    exploitation_signal: str | None
    exploitability: str
    evidence: str | None
    reason: str | None
    timestamp: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "exploitation_signal": self.exploitation_signal,
            "exploitability": self.exploitability,
            "evidence": self.evidence,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class TerminalSignalSystem:
    """Parses and formats explicit exploitation result terminal signals."""

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def format_signal_output(
        self,
        *,
        vulnerability_exploitable: bool,
        evidence: str | None = None,
        reason: str | None = None,
        timestamp: str | None = None,
    ) -> str:
        signal = "+" if vulnerability_exploitable else "-"
        lines = [f"EXPLOITATION_RESULT: {signal}"]
        if vulnerability_exploitable and evidence:
            lines.append(f"EVIDENCE: {evidence}")
        if not vulnerability_exploitable and reason:
            lines.append(f"REASON: {reason}")
        lines.append(f"TIMESTAMP: {timestamp or self._now()}")
        return "\n".join(lines)

    def parse_exploitation_signal(self, terminal_output: str) -> dict[str, Any]:
        result_match = RESULT_RE.search(terminal_output or "")
        signal = result_match.group(1) if result_match else None

        evidence_match = EVIDENCE_RE.search(terminal_output or "")
        reason_match = REASON_RE.search(terminal_output or "")
        timestamp_match = TIMESTAMP_RE.search(terminal_output or "")

        if signal == "+":
            exploitability = "POSITIVE"
        elif signal == "-":
            exploitability = "NEGATIVE"
        else:
            exploitability = "UNCLEAR"

        parsed = TerminalSignalParseResult(
            exploitation_signal=signal,
            exploitability=exploitability,
            evidence=evidence_match.group(1).strip() if evidence_match else None,
            reason=reason_match.group(1).strip() if reason_match else None,
            timestamp=timestamp_match.group(1).strip() if timestamp_match else None,
        )
        return parsed.as_dict()

    def parse_output_file(self, output_file: str | Path) -> dict[str, Any]:
        output_path = Path(output_file)
        if not output_path.exists() or not output_path.is_file():
            return {
                "exploitation_signal": None,
                "exploitability": "UNCLEAR",
                "error": f"Output file not found: {output_file}",
            }
        text = output_path.read_text(encoding="utf-8", errors="replace")
        parsed = self.parse_exploitation_signal(text)
        parsed["output_file"] = str(output_path)
        return parsed


class TmuxScreenRecordingIntegration:
    """
    Executes PoC scripts in tmux and captures terminal output as review evidence.

    Note: this integration captures terminal transcript and metadata sidecars used by
    screen recording validation. It does not attempt to bypass scope or safety gates.
    """

    def __init__(
        self,
        *,
        output_dir: str | Path = "artifacts/recordings/tmux",
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.poll_interval_seconds = max(0.2, poll_interval_seconds)
        self.signal_parser = TerminalSignalSystem()

    @staticmethod
    def _run(cmd: list[str], *, timeout: int = 10) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)

    def _tmux_available(self) -> bool:
        probe = self._run(["tmux", "-V"], timeout=5)
        return probe.returncode == 0

    def _tmux_session_exists(self, session: str) -> bool:
        probe = self._run(["tmux", "has-session", "-t", session], timeout=5)
        return probe.returncode == 0

    def _capture_pane(self, session: str) -> str:
        capture = self._run(["tmux", "capture-pane", "-pt", session, "-S", "-2000"], timeout=6)
        return capture.stdout if capture.returncode == 0 else ""

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _recording_paths(self, session: str, script: Path) -> tuple[Path, Path, Path]:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        base = self.output_dir / f"{session}_{script.stem}_{stamp}"
        recording_file = base.with_suffix(".log")
        terminal_output_file = base.with_suffix(".terminal.log")
        metadata_file = base.with_suffix(".events.json")
        return recording_file, terminal_output_file, metadata_file

    def run_poc_with_recording(
        self,
        poc_script: str | Path,
        tmux_session: str,
        *,
        timeout_seconds: int = 180,
    ) -> dict[str, Any]:
        script_path = Path(poc_script)
        if not script_path.exists() or not script_path.is_file():
            return {
                "status": "FAILED",
                "reason": f"PoC script not found: {script_path}",
                "exploitation_signal": None,
                "exploitability": "UNCLEAR",
            }

        if not self._tmux_available():
            return {
                "status": "FAILED",
                "reason": "tmux is not available in runtime",
                "exploitation_signal": None,
                "exploitability": "UNCLEAR",
            }

        if not self._tmux_session_exists(tmux_session):
            return {
                "status": "FAILED",
                "reason": f"tmux session not found: {tmux_session}",
                "exploitation_signal": None,
                "exploitability": "UNCLEAR",
            }

        recording_file, terminal_output_file, metadata_file = self._recording_paths(tmux_session, script_path)
        start_ts = self._now()

        command = f"bash {shlex.quote(str(script_path))}"
        send = self._run(["tmux", "send-keys", "-t", tmux_session, command, "C-m"], timeout=5)
        if send.returncode != 0:
            return {
                "status": "FAILED",
                "reason": "failed to dispatch script into tmux session",
                "stderr": send.stderr.strip(),
                "exploitation_signal": None,
                "exploitability": "UNCLEAR",
            }

        final_output = ""
        parsed = {
            "exploitation_signal": None,
            "exploitability": "UNCLEAR",
            "evidence": None,
            "reason": None,
            "timestamp": None,
        }

        deadline = time.time() + max(15, timeout_seconds)
        while time.time() < deadline:
            pane_output = self._capture_pane(tmux_session)
            if pane_output:
                final_output = pane_output
                parsed = self.signal_parser.parse_exploitation_signal(pane_output)
                if parsed.get("exploitation_signal") in {"+", "-"}:
                    break
            time.sleep(self.poll_interval_seconds)

        end_ts = self._now()

        terminal_output_file.write_text(final_output, encoding="utf-8")
        recording_file.write_text(final_output, encoding="utf-8")
        metadata = {
            "tmux_session": tmux_session,
            "script": str(script_path),
            "start_time": start_ts,
            "end_time": end_ts,
            "recording_file": str(recording_file),
            "terminal_output_file": str(terminal_output_file),
            "exploitation_signal": parsed.get("exploitation_signal"),
            "exploitability": parsed.get("exploitability"),
        }
        metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return {
            "status": "COMPLETED" if parsed.get("exploitation_signal") in {"+", "-"} else "COMPLETED_UNCLEAR",
            "recording_file": str(recording_file),
            "terminal_output_file": str(terminal_output_file),
            "metadata_file": str(metadata_file),
            "terminal_output": final_output,
            "exploitation_signal": parsed.get("exploitation_signal"),
            "exploitability": parsed.get("exploitability"),
            "evidence": parsed.get("evidence"),
            "reason": parsed.get("reason"),
            "timestamp": parsed.get("timestamp"),
        }


__all__ = ["TerminalSignalSystem", "TmuxScreenRecordingIntegration", "TerminalSignalParseResult"]
