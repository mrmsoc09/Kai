from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .evidence_integrity_service import EvidenceIntegrityService
from .helpers import artifacts_root
from .recordings import has_recording, list_recordings


_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv"}


class ReportState:
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    FINALIZED = "FINALIZED"


class ReportReadiness(BaseModel):
    report_ready: bool
    report_state: str
    requires_human_validation: bool = True
    missing_requirements: list[str] = Field(default_factory=list)
    reason: str


class ReportArtifacts(BaseModel):
    report_json_path: str
    report_markdown_path: str
    state_path: str


class ReportGateResult(BaseModel):
    run_id: str
    stakeholder: str
    readiness: ReportReadiness
    artifacts: ReportArtifacts
    report: dict[str, Any]


class ReportHiLGateService:
    """Phase 5 additive gate for BBP-ready report packaging and immutable finalization."""

    def _run_dir(self, run_id: str) -> Path:
        rid = str(run_id or "unknown").strip() or "unknown"
        path = artifacts_root() / "reports" / "bbp_ready" / rid
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _state_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "report_state.json"

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _safe_float(value: Any, default: float | None = None) -> float | None:
        if value is None:
            return default
        try:
            num = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, num))

    @staticmethod
    def _sha256_file(path: Path) -> str | None:
        if not path.exists() or not path.is_file():
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _stable_hash(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8", errors="replace")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _normalize_lines(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(row).strip() for row in value if str(row).strip()]
        if isinstance(value, str) and value.strip():
            rows = [row.strip() for row in value.splitlines() if row.strip()]
            return rows
        return []

    def _recording_path(self, run_id: str, payload: dict[str, Any]) -> str | None:
        finding = payload.get("finding") if isinstance(payload.get("finding"), dict) else {}
        evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}

        candidates = [
            payload.get("recording_path"),
            evidence.get("recording_path"),
            finding.get("recording_path"),
        ]
        for raw in candidates:
            path = str(raw or "").strip()
            if not path:
                continue
            p = Path(path)
            if p.exists() and p.is_file() and p.suffix.lower() in _VIDEO_EXTENSIONS:
                return str(p.resolve())

        for row in list_recordings(run_id):
            p = Path(row)
            if p.exists() and p.is_file() and p.suffix.lower() in _VIDEO_EXTENSIONS:
                return str(p.resolve())

        return None

    @staticmethod
    def _screenshots(payload: dict[str, Any]) -> list[str]:
        finding = payload.get("finding") if isinstance(payload.get("finding"), dict) else {}
        evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}

        rows: list[str] = []
        for source in (finding.get("screenshots"), evidence.get("screenshots"), payload.get("screenshots")):
            if isinstance(source, list):
                rows.extend([str(row).strip() for row in source if str(row).strip()])

        artifacts = evidence.get("artifacts")
        if isinstance(artifacts, dict):
            for key, value in artifacts.items():
                if "screenshot" not in str(key).lower():
                    continue
                text = str(value).strip()
                if text:
                    rows.append(text)

        deduped: list[str] = []
        seen: set[str] = set()
        for row in rows:
            if row in seen:
                continue
            seen.add(row)
            deduped.append(row)
        return deduped

    def _confidence_score(self, payload: dict[str, Any]) -> float | None:
        finding = payload.get("finding") if isinstance(payload.get("finding"), dict) else {}
        arbitration = self._arbitration_summary(payload)

        for raw in (
            payload.get("confidence_score"),
            finding.get("confidence_score"),
            finding.get("final_confidence"),
            arbitration.get("final_confidence"),
            finding.get("confidence"),
        ):
            num = self._safe_float(raw, default=None)
            if num is not None:
                return num
        return None

    def _arbitration_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        finding = payload.get("finding") if isinstance(payload.get("finding"), dict) else {}

        source = payload.get("arbitration")
        if not isinstance(source, dict):
            source = finding.get("arbitration")
        if not isinstance(source, dict):
            source = {}

        verdict = str(
            source.get("final_verdict")
            or payload.get("final_verdict")
            or finding.get("final_verdict")
            or ""
        ).strip()
        reason = str(
            source.get("arbitration_reason")
            or payload.get("arbitration_reason")
            or finding.get("arbitration_reason")
            or ""
        ).strip()
        final_confidence = self._safe_float(
            source.get("final_confidence")
            or payload.get("final_confidence")
            or finding.get("final_confidence"),
            default=None,
        )
        conflict_detected = bool(source.get("conflict_detected"))

        return {
            "final_verdict": verdict,
            "final_confidence": final_confidence,
            "arbitration_reason": reason,
            "conflict_detected": conflict_detected,
        }

    @staticmethod
    def _attack_chain_context(payload: dict[str, Any]) -> dict[str, Any]:
        finding = payload.get("finding") if isinstance(payload.get("finding"), dict) else {}

        for candidate in (
            payload.get("attack_chain_context"),
            payload.get("attack_graph"),
            finding.get("exploit_chain"),
            payload.get("exploit_chain"),
        ):
            if isinstance(candidate, dict):
                return candidate
        return {}

    def _validated_exploit_evidence(self, payload: dict[str, Any], *, recording_path: str | None, screenshots: list[str], arbitration: dict[str, Any]) -> bool:
        finding = payload.get("finding") if isinstance(payload.get("finding"), dict) else {}
        evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}

        for key in ("validated", "validated_vulnerability", "exploit_confirmed", "reproducible"):
            if bool(finding.get(key)):
                return True

        if str(arbitration.get("final_verdict") or "").lower() == "confirmed":
            return True

        repro = self._normalize_lines(finding.get("reproduction_steps"))
        if not repro:
            repro = self._normalize_lines(evidence.get("repro"))

        has_artifact_evidence = bool(recording_path or screenshots)
        return bool(repro and has_artifact_evidence)

    def _markdown_report(self, report: dict[str, Any]) -> str:
        steps = report.get("reproduction_steps") if isinstance(report.get("reproduction_steps"), list) else []
        screenshots = report.get("screenshots") if isinstance(report.get("screenshots"), list) else []
        chain_of_custody = report.get("chain_of_custody") if isinstance(report.get("chain_of_custody"), dict) else {}
        artifacts = chain_of_custody.get("artifacts") if isinstance(chain_of_custody.get("artifacts"), list) else []
        arbitration = report.get("arbitration_summary") if isinstance(report.get("arbitration_summary"), dict) else {}

        lines = [
            f"# {report.get('title') or 'Kai BBP Report'}",
            "",
            f"- Run ID: `{report.get('run_id')}`",
            f"- Stakeholder: `{report.get('stakeholder')}`",
            f"- Report State: `{report.get('report_state')}`",
            f"- Confidence Score: `{report.get('confidence_score')}`",
            "",
            "## Vulnerability Description",
            str(report.get("vulnerability_description") or "").strip(),
            "",
            "## Reproduction Steps",
        ]
        if steps:
            for idx, step in enumerate(steps, start=1):
                lines.append(f"{idx}. {step}")
        else:
            lines.append("1. Reproduction steps unavailable.")

        lines.extend(
            [
                "",
                "## Evidence",
                f"- Video Recording: `{report.get('video_recording') or 'missing'}`",
                f"- Screenshots: `{len(screenshots)}`",
                "",
                "## Impact Analysis",
                str(report.get("impact_analysis") or "").strip(),
                "",
                "## Arbitration Summary",
                f"- Verdict: `{arbitration.get('final_verdict') or 'unknown'}`",
                f"- Confidence: `{arbitration.get('final_confidence')}`",
                f"- Reason: {arbitration.get('arbitration_reason') or 'n/a'}",
                "",
                "## Attack Chain Context",
                json.dumps(report.get("attack_chain_context") or {}, indent=2, sort_keys=True),
                "",
                "## Chain Of Custody",
            ]
        )
        if artifacts:
            for row in artifacts:
                if not isinstance(row, dict):
                    continue
                lines.append(
                    f"- `{row.get('artifact_type')}` path=`{row.get('artifact_path')}` sha256=`{row.get('sha256')}`"
                )
        else:
            lines.append("- No artifacts hashed.")

        return "\n".join(lines).strip() + "\n"

    def _load_state(self, run_id: str) -> dict[str, Any]:
        path = self._state_path(run_id)
        if not path.exists():
            return {
                "run_id": run_id,
                "report_state": ReportState.DRAFT,
                "immutable": False,
                "finalized_at": None,
                "final_report_hash": None,
            }
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
        return {
            "run_id": run_id,
            "report_state": ReportState.DRAFT,
            "immutable": False,
            "finalized_at": None,
            "final_report_hash": None,
        }

    def _save_state(self, run_id: str, payload: dict[str, Any]) -> None:
        path = self._state_path(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _build_report_payload(self, *, run_id: str, stakeholder: str, payload: dict[str, Any], report_state: str, missing: list[str]) -> dict[str, Any]:
        finding = payload.get("finding") if isinstance(payload.get("finding"), dict) else {}
        evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}

        recording_path = self._recording_path(run_id, payload)
        screenshots = self._screenshots(payload)
        arbitration = self._arbitration_summary(payload)
        confidence = self._confidence_score(payload)

        repro_steps = self._normalize_lines(finding.get("reproduction_steps"))
        if not repro_steps:
            repro_steps = self._normalize_lines(evidence.get("repro"))

        title = str(finding.get("title") or payload.get("title") or f"Kai report {run_id}").strip()
        vulnerability_description = str(
            finding.get("summary")
            or finding.get("description")
            or payload.get("vulnerability_description")
            or ""
        ).strip()
        impact_analysis = str(finding.get("impact") or payload.get("impact_analysis") or "").strip()

        chain_artifacts: list[dict[str, Any]] = []
        artifact_paths: list[tuple[str, str]] = []
        if recording_path:
            artifact_paths.append(("screen_recording", recording_path))
        for shot in screenshots:
            artifact_paths.append(("screenshot", shot))

        for artifact_type, raw_path in artifact_paths:
            p = Path(raw_path)
            chain_artifacts.append(
                {
                    "artifact_type": artifact_type,
                    "artifact_path": str(p),
                    "exists": p.exists() and p.is_file(),
                    "sha256": self._sha256_file(p),
                }
            )

        report_payload: dict[str, Any] = {
            "run_id": run_id,
            "stakeholder": stakeholder,
            "title": title,
            "report_state": report_state,
            "missing_requirements": missing,
            "requires_human_validation": True,
            "vulnerability_description": vulnerability_description,
            "reproduction_steps": repro_steps,
            "screenshots": screenshots,
            "video_recording": recording_path,
            "impact_analysis": impact_analysis,
            "confidence_score": confidence,
            "arbitration_summary": arbitration,
            "attack_chain_context": self._attack_chain_context(payload),
            "chain_of_custody": {
                "artifacts": chain_artifacts,
                "generated_at": self._now_iso(),
            },
            "metadata": {
                "source": "report_hil_gate",
                "report_ready": len(missing) == 0,
            },
        }
        report_payload["report_sha256"] = self._stable_hash(report_payload)
        return report_payload

    def evaluate_report(self, *, run_id: str, stakeholder: str, payload: dict[str, Any]) -> ReportGateResult:
        run_id = str(run_id or "unknown")
        stakeholder = str(stakeholder or "generic")

        recording_path = self._recording_path(run_id, payload)
        screenshots = self._screenshots(payload)
        arbitration = self._arbitration_summary(payload)
        confidence = self._confidence_score(payload)

        missing: list[str] = []
        if not recording_path and not has_recording(run_id):
            missing.append("full_screen_recording_required")

        if not self._validated_exploit_evidence(payload, recording_path=recording_path, screenshots=screenshots, arbitration=arbitration):
            missing.append("validated_exploit_evidence_required")

        if confidence is None:
            missing.append("confidence_score_required")

        if not arbitration.get("final_verdict") or arbitration.get("final_confidence") is None or not arbitration.get("arbitration_reason"):
            missing.append("arbitration_summary_required")

        report_state = ReportState.VALIDATED if not missing else ReportState.DRAFT
        reason = "report_ready" if not missing else ",".join(missing)

        report_payload = self._build_report_payload(
            run_id=run_id,
            stakeholder=stakeholder,
            payload=payload,
            report_state=report_state,
            missing=missing,
        )
        readiness = ReportReadiness(
            report_ready=not missing,
            report_state=report_state,
            requires_human_validation=True,
            missing_requirements=missing,
            reason=reason,
        )

        run_dir = self._run_dir(run_id)
        report_json_path = run_dir / "report.json"
        report_markdown_path = run_dir / "report.md"
        report_json_path.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        report_markdown_path.write_text(self._markdown_report(report_payload), encoding="utf-8")

        current_state = self._load_state(run_id)
        if current_state.get("report_state") != ReportState.FINALIZED:
            next_state = {
                **current_state,
                "run_id": run_id,
                "report_state": report_state,
                "immutable": bool(current_state.get("immutable")),
                "updated_at": self._now_iso(),
                "latest_report_sha256": report_payload.get("report_sha256"),
                "missing_requirements": missing,
            }
            self._save_state(run_id, next_state)

        return ReportGateResult(
            run_id=run_id,
            stakeholder=stakeholder,
            readiness=readiness,
            artifacts=ReportArtifacts(
                report_json_path=str(report_json_path),
                report_markdown_path=str(report_markdown_path),
                state_path=str(self._state_path(run_id)),
            ),
            report=report_payload,
        )

    def finalize_after_hil(
        self,
        *,
        run_id: str,
        stakeholder: str,
        payload: dict[str, Any],
        actor: str = "reports.submit_hil",
    ) -> ReportGateResult:
        result = self.evaluate_report(run_id=run_id, stakeholder=stakeholder, payload=payload)
        state = self._load_state(run_id)

        if state.get("report_state") == ReportState.FINALIZED and bool(state.get("immutable")):
            frozen_hash = str(state.get("final_report_hash") or "")
            current_hash = str(result.report.get("report_sha256") or "")
            if frozen_hash and current_hash and frozen_hash != current_hash:
                result.readiness.report_ready = False
                result.readiness.reason = "report_finalized_immutable"
                result.readiness.missing_requirements = ["immutable_finalization_lock"]
                return result
            return result

        if not result.readiness.report_ready:
            return result

        if not bool(payload.get("hil_approved")):
            result.readiness.report_ready = False
            result.readiness.reason = "hil_approval_required"
            result.readiness.missing_requirements = ["human_validation_required"]
            return result

        EvidenceIntegrityService().finalize_run_evidence(
            run_id=run_id,
            actor=actor,
            reason="report_finalized",
        )

        finalized_state = {
            **state,
            "run_id": run_id,
            "report_state": ReportState.FINALIZED,
            "immutable": True,
            "finalized_at": self._now_iso(),
            "finalized_by": actor,
            "final_report_hash": result.report.get("report_sha256"),
            "updated_at": self._now_iso(),
        }
        self._save_state(run_id, finalized_state)

        result.readiness.report_state = ReportState.FINALIZED
        result.report["report_state"] = ReportState.FINALIZED
        result.report["finalized_at"] = finalized_state["finalized_at"]
        result.report["immutable"] = True

        report_md_path = Path(result.artifacts.report_markdown_path)
        report_md_path.write_text(self._markdown_report(result.report), encoding="utf-8")
        report_json_path = Path(result.artifacts.report_json_path)
        report_json_path.write_text(json.dumps(result.report, indent=2, ensure_ascii=False), encoding="utf-8")

        return result


def get_report_hil_gate_service() -> ReportHiLGateService:
    return ReportHiLGateService()
