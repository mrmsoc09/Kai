from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import subprocess
from typing import Any


RESULT_SIGNAL_RE = re.compile(r"EXPLOITATION_RESULT:\s*([+-])", re.IGNORECASE)
EVIDENCE_RE = re.compile(r"EVIDENCE:\s*(.+)", re.IGNORECASE)
TIMESTAMP_RE = re.compile(r"TIMESTAMP:\s*([0-9T:+.Z-]+)", re.IGNORECASE)


class ScreenRecordingValidationError(ValueError):
    """Raised when a recording cannot be analyzed safely."""


@dataclass(slots=True)
class RecordingAnalysisContext:
    recording_file: str
    total_frames: int
    duration_seconds: float
    frame_rate: float
    extracted_at: str
    evidence_text: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "recording_file": self.recording_file,
            "total_frames": self.total_frames,
            "duration_seconds": self.duration_seconds,
            "frame_rate": self.frame_rate,
            "extracted_at": self.extracted_at,
        }


class ScreenRecordingValidator:
    """
    Screen recording validation for submission gating.

    This validator is deterministic and evidence-first:
    - prefers recorded terminal/event sidecars
    - parses explicit exploitation result signals (+/-)
    - checks timestamp monotonicity and basic anomaly indicators
    - returns analyst-review flags when confidence is low
    """

    def __init__(self, *, min_auto_confidence: float = 0.85) -> None:
        self.min_auto_confidence = min_auto_confidence

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _normalize(text: str | None) -> str:
        return (text or "").strip().lower()

    @staticmethod
    def _parse_rate(rate: str) -> float:
        text = (rate or "").strip()
        if "/" in text:
            left, right = text.split("/", 1)
            try:
                num = float(left)
                den = float(right)
                return round(num / den, 3) if den else 0.0
            except ValueError:
                return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0

    @staticmethod
    def _candidate_sidecars(recording: Path) -> list[Path]:
        stem = recording.stem
        return [
            recording.with_suffix(".log"),
            recording.with_suffix(".txt"),
            recording.with_suffix(".events.json"),
            recording.parent / f"{stem}.terminal.log",
            recording.parent / f"{stem}.events.json",
            recording.parent / f"{stem}.tmux.log",
        ]

    def _read_sidecar_text(self, recording: Path) -> str:
        chunks: list[str] = []
        for candidate in self._candidate_sidecars(recording):
            if not candidate.exists():
                continue
            if candidate.suffix.lower() == ".json":
                try:
                    payload = json.loads(candidate.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                if isinstance(payload, list):
                    for item in payload:
                        if isinstance(item, dict):
                            chunks.append(" ".join(str(v) for v in item.values()))
                        else:
                            chunks.append(str(item))
                elif isinstance(payload, dict):
                    chunks.append(" ".join(str(v) for v in payload.values()))
                else:
                    chunks.append(str(payload))
                continue

            try:
                chunks.append(candidate.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
        return "\n".join(chunks)

    def _run_ffprobe(self, recording: Path) -> dict[str, Any]:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-count_frames",
            "-show_streams",
            "-show_format",
            str(recording),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=12, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return {}

        if proc.returncode != 0:
            return {}

        try:
            payload = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            return {}

        return payload if isinstance(payload, dict) else {}

    def extract_frames_from_recording(self, recording_file: str | Path) -> dict[str, Any]:
        recording = Path(recording_file)
        if not recording.exists() or not recording.is_file():
            raise ScreenRecordingValidationError(f"Recording file not found: {recording}")

        ffprobe = self._run_ffprobe(recording)
        streams = ffprobe.get("streams", []) if isinstance(ffprobe, dict) else []
        video_stream = None
        for stream in streams:
            if isinstance(stream, dict) and stream.get("codec_type") == "video":
                video_stream = stream
                break

        duration = 0.0
        fps = 0.0
        total_frames = 0

        if isinstance(video_stream, dict):
            duration_text = str(
                video_stream.get("duration")
                or ffprobe.get("format", {}).get("duration")
                or "0"
            )
            try:
                duration = float(duration_text)
            except ValueError:
                duration = 0.0
            fps = self._parse_rate(str(video_stream.get("avg_frame_rate", "0/1")))
            frame_text = str(video_stream.get("nb_read_frames") or video_stream.get("nb_frames") or "0")
            try:
                total_frames = int(float(frame_text))
            except ValueError:
                total_frames = 0

        if total_frames <= 0:
            # Conservative fallback when ffprobe is unavailable.
            total_frames = max(1, int(recording.stat().st_size / 16384))
            if duration <= 0:
                duration = round(max(1.0, total_frames / 15.0), 2)
            if fps <= 0:
                fps = round(total_frames / max(duration, 1.0), 2)

        evidence_text = self._read_sidecar_text(recording)
        ctx = RecordingAnalysisContext(
            recording_file=str(recording),
            total_frames=total_frames,
            duration_seconds=round(duration, 3),
            frame_rate=round(fps, 3),
            extracted_at=self._now(),
            evidence_text=evidence_text,
        )
        return {"context": ctx.as_dict(), "evidence_text": evidence_text}

    @staticmethod
    def _step_visible(step: str, evidence_text: str) -> bool:
        tokens = [t for t in re.split(r"[^a-zA-Z0-9]+", step.lower()) if len(t) >= 4]
        if not tokens:
            return False
        matched = sum(1 for tok in tokens[:6] if tok in evidence_text)
        required = 1 if len(tokens) <= 3 else 2
        return matched >= required

    def validate_poc_steps_in_recording(self, frame_data: dict[str, Any], poc_steps: list[str]) -> dict[str, Any]:
        evidence = self._normalize(str(frame_data.get("evidence_text", "")))
        results: list[bool] = []
        for step in poc_steps:
            results.append(self._step_visible(step, evidence))

        all_visible = bool(results) and all(results)
        visible_ratio = round((sum(1 for x in results if x) / len(results)) if results else 0.0, 3)
        return {
            "all_steps_visible": all_visible,
            "most_steps_visible": visible_ratio >= 0.7,
            "visible_ratio": visible_ratio,
            "step_visibility": results,
        }

    def detect_exploitation_in_frames(self, frame_data: dict[str, Any], expected_result: str) -> dict[str, Any]:
        evidence_text = str(frame_data.get("evidence_text", ""))
        signal_match = RESULT_SIGNAL_RE.search(evidence_text)
        signal = signal_match.group(1) if signal_match else ""

        expected_norm = self._normalize(expected_result)
        evidence_norm = self._normalize(evidence_text)
        expected_hit = bool(expected_norm and expected_norm in evidence_norm)

        result_confirmed = signal == "+"
        result_likely = signal == "+" or expected_hit

        ev_match = EVIDENCE_RE.search(evidence_text)
        evidence_line = ev_match.group(1).strip() if ev_match else ""

        return {
            "signal": signal or None,
            "result_confirmed": result_confirmed,
            "result_likely": result_likely,
            "expected_result_matched": expected_hit,
            "evidence_line": evidence_line,
        }

    def validate_timestamps_are_real(self, frame_data: dict[str, Any]) -> bool:
        evidence_text = str(frame_data.get("evidence_text", ""))
        lines = evidence_text.splitlines()
        stamps: list[datetime] = []

        for line in lines:
            match = TIMESTAMP_RE.search(line)
            if not match:
                continue
            raw = match.group(1).replace("Z", "+00:00")
            try:
                stamps.append(datetime.fromisoformat(raw))
            except ValueError:
                continue

        if not stamps:
            return False

        return all(stamps[i] <= stamps[i + 1] for i in range(len(stamps) - 1))

    def detect_editing_anomalies(self, frame_data: dict[str, Any]) -> list[str]:
        ctx = frame_data.get("context", {})
        evidence_text = str(frame_data.get("evidence_text", ""))
        anomalies: list[str] = []

        duration = float(ctx.get("duration_seconds", 0.0))
        frames = int(ctx.get("total_frames", 0))

        if duration < 2.0:
            anomalies.append("recording_duration_too_short")
        if frames < 10:
            anomalies.append("insufficient_frame_count")

        has_plus = "EXPLOITATION_RESULT: +" in evidence_text
        has_minus = "EXPLOITATION_RESULT: -" in evidence_text
        if has_plus and has_minus:
            anomalies.append("conflicting_terminal_signals")

        if "timestamp:" not in evidence_text.lower():
            anomalies.append("missing_terminal_timestamp")

        return anomalies

    def ai_analyze_exploitation_evidence(
        self,
        frame_data: dict[str, Any],
        poc_steps: list[str],
        expected_result: str,
    ) -> dict[str, Any]:
        poc_validation = self.validate_poc_steps_in_recording(frame_data, poc_steps)
        exploit_detection = self.detect_exploitation_in_frames(frame_data, expected_result)
        anomalies = self.detect_editing_anomalies(frame_data)

        score = 0.0
        score += 0.45 if exploit_detection["result_confirmed"] else (0.25 if exploit_detection["result_likely"] else 0.0)
        score += 0.35 * float(poc_validation["visible_ratio"])
        score += 0.15 if not anomalies else 0.0
        score += 0.05 if self.validate_timestamps_are_real(frame_data) else 0.0

        return {
            "confidence_score": round(min(1.0, max(0.0, score)), 3),
            "signal": exploit_detection.get("signal"),
            "poc_visible_ratio": poc_validation["visible_ratio"],
            "anomaly_count": len(anomalies),
        }

    @staticmethod
    def determine_review_reason(validation: dict[str, Any]) -> str:
        if validation.get("anomalies"):
            return "anomalies_detected"
        if not validation.get("timestamps_valid"):
            return "timestamps_missing_or_non_monotonic"
        if not validation.get("poc_steps_validated", {}).get("all_steps_visible"):
            return "poc_steps_not_fully_visible"
        if not validation.get("exploitation_detected", {}).get("result_confirmed"):
            return "exploitation_signal_not_confirmed"
        return "none"

    def analyze_screen_recording(
        self,
        recording_file: str | Path,
        poc_steps: list[str],
        expected_result: str,
    ) -> dict[str, Any]:
        frame_data = self.extract_frames_from_recording(recording_file)
        poc_validation = self.validate_poc_steps_in_recording(frame_data, poc_steps)
        exploitation_detected = self.detect_exploitation_in_frames(frame_data, expected_result)
        timestamps_valid = self.validate_timestamps_are_real(frame_data)
        anomalies = self.detect_editing_anomalies(frame_data)
        ai_analysis = self.ai_analyze_exploitation_evidence(frame_data, poc_steps, expected_result)

        if (
            poc_validation["all_steps_visible"]
            and exploitation_detected["result_confirmed"]
            and timestamps_valid
            and len(anomalies) == 0
        ):
            exploitability = "+"
            confidence = 0.95
        elif (
            poc_validation["most_steps_visible"]
            and exploitation_detected["result_likely"]
            and len(anomalies) <= 1
        ):
            exploitability = "+"
            confidence = max(0.78, ai_analysis["confidence_score"])
        else:
            exploitability = "-"
            confidence = min(0.40, ai_analysis["confidence_score"])

        validation = {
            "recording_file": str(recording_file),
            "analysis_steps": [
                "extract_frames",
                "validate_poc_steps",
                "detect_exploitation",
                "validate_timestamps",
                "detect_anomalies",
                "ai_assisted_analysis",
            ],
            "context": frame_data.get("context", {}),
            "poc_steps_validated": poc_validation,
            "exploitation_detected": exploitation_detected,
            "timestamps_valid": timestamps_valid,
            "anomalies": anomalies,
            "ai_analysis": ai_analysis,
        }

        analyst_review_needed = confidence < self.min_auto_confidence

        return {
            "exploitability": exploitability,
            "confidence": round(confidence, 3),
            "validation_steps_completed": poc_validation["step_visibility"],
            "anomalies_detected": anomalies,
            "validation_details": validation,
            "ai_analysis": ai_analysis,
            "analyst_review_needed": analyst_review_needed,
            "analyst_review_reason": self.determine_review_reason(validation) if analyst_review_needed else "none",
        }


__all__ = ["ScreenRecordingValidator", "ScreenRecordingValidationError", "RecordingAnalysisContext"]
