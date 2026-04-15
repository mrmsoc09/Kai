from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.hil.hil_audit_trail import HiLAuditTrail
from tools.submission.platform_api_submission import PlatformAPISubmissionClient
from tools.submission.report_format_validator import ReportFormatValidator


class SubmissionError(RuntimeError):
    """Raised when a finding fails submission gate checks."""


class FindingSubmissionGateway:
    """
    Multi-gate submission pipeline:
    HiL approval -> recording validation -> report format -> scope -> API submit.
    """

    def __init__(
        self,
        *,
        report_validator: ReportFormatValidator | None = None,
        api_client: PlatformAPISubmissionClient | None = None,
        audit_trail: HiLAuditTrail | None = None,
        submission_log_path: str | Path = "tools/submission/data/submission_log.jsonl",
    ) -> None:
        self.report_validator = report_validator or ReportFormatValidator()
        self.api_client = api_client or PlatformAPISubmissionClient()
        self.audit_trail = audit_trail or HiLAuditTrail()

        self.submission_log_path = Path(submission_log_path)
        self.submission_log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.submission_log_path.exists():
            self.submission_log_path.write_text("", encoding="utf-8")

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _stable_json(obj: dict[str, Any]) -> str:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @staticmethod
    def _sha256(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize(text: str | None) -> str:
        return (text or "").strip().lower()

    def _read_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self.submission_log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    def _previous_hash(self) -> str:
        rows = self._read_rows()
        if not rows:
            return "GENESIS"
        return str(rows[-1].get("record_hash", "GENESIS"))

    def _append_immutable_submission_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = {
            "recorded_at": self._now(),
            "previous_record_hash": self._previous_hash(),
            **payload,
        }
        record["record_hash"] = self._sha256(self._stable_json(record))
        record["immutable"] = True

        with self.submission_log_path.open("a", encoding="utf-8") as f:
            f.write(self._stable_json(record) + "\n")

        return record

    def validate_hil_approval(self, approval_record: dict[str, Any]) -> None:
        if self._normalize(str(approval_record.get("decision", ""))) != "approved":
            raise SubmissionError("Finding not approved by HiL analyst")
        if not approval_record.get("digital_signature"):
            raise SubmissionError("Missing analyst digital signature in approval record")
        if not approval_record.get("non_repudiation_token"):
            raise SubmissionError("Missing non-repudiation token in approval record")

    def validate_screen_recording(self, screen_recording_validation: dict[str, Any]) -> None:
        signal = str(screen_recording_validation.get("exploitability", "")).strip()
        if signal != "+":
            raise SubmissionError("Screen recording validation failed: exploitability signal is not '+'")
        confidence = float(screen_recording_validation.get("confidence", 0.0))
        if confidence < 0.70:
            raise SubmissionError("Screen recording confidence below minimum threshold (0.70)")
        if not screen_recording_validation.get("recording_file"):
            raise SubmissionError("Screen recording path missing from validation payload")

    def validate_scope_confirmation(self, finding: dict[str, Any]) -> None:
        in_scope = bool(
            finding.get("in_scope_confirmed")
            or self._normalize(str(finding.get("scope_status", ""))) == "in_scope"
        )
        if not in_scope:
            raise SubmissionError("Scope not confirmed by analyst")

    def validate_report_format(self, finding: dict[str, Any]) -> dict[str, Any]:
        result = self.report_validator.validate_report_format(finding)
        if not bool(result.get("passed", False)):
            violations = result.get("violations", [])
            raise SubmissionError(f"Report format violations: {violations}")
        return result

    def submit_finding_to_platform(
        self,
        finding: dict[str, Any],
        approval_record: dict[str, Any],
        screen_recording_validation: dict[str, Any],
    ) -> dict[str, Any]:
        # Gate 1: mandatory HiL analyst approval
        self.validate_hil_approval(approval_record)

        # Gate 2: recording validation (+ signal)
        self.validate_screen_recording(screen_recording_validation)

        # Gate 3: report format compliance
        format_validation = self.validate_report_format(finding)

        # Gate 4: scope confirmation
        self.validate_scope_confirmation(finding)

        platform = str(finding.get("platform") or finding.get("program") or "hackerone")
        api_result = self.api_client.submit(
            platform=platform,
            finding=finding,
            screen_recording_path=str(screen_recording_validation.get("recording_file")),
        )

        status = self._normalize(str(api_result.get("status", "")))
        if status not in {"submitted", "queued_dry_run"}:
            raise SubmissionError(
                f"Platform submission failed ({api_result.get('status')}): {api_result.get('error')}"
            )

        submission_record = self._append_immutable_submission_record(
            {
                "finding_id": finding.get("finding_id") or finding.get("id"),
                "platform": platform,
                "submission_status": api_result.get("status"),
                "submission_id": api_result.get("submission_id"),
                "approval_signature": approval_record.get("digital_signature"),
                "screen_recording_validation": screen_recording_validation.get("exploitability"),
                "format_validation": format_validation,
            }
        )

        analyst_id = str(approval_record.get("analyst_id", "unknown"))
        self.audit_trail.record_hil_event(
            event_type="finding_submitted",
            finding_id=str(finding.get("finding_id") or finding.get("id") or "unknown"),
            analyst_id=analyst_id,
            event_data={
                "platform": platform,
                "submission_id": api_result.get("submission_id"),
                "submission_status": api_result.get("status"),
            },
        )

        return {
            "submission_result": api_result,
            "submission_record": submission_record,
        }


__all__ = ["FindingSubmissionGateway", "SubmissionError"]
