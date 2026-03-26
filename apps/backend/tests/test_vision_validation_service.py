from __future__ import annotations

import asyncio
from pathlib import Path

from apps.backend.src.core.vision_validation_service import (
    VisionRunnerOutput,
    VisionValidationService,
)


class _FakeRunner:
    def __init__(self, *, output: VisionRunnerOutput):
        self.output = output

    async def capture(self, **kwargs):  # noqa: ANN003
        return self.output


def test_vision_validation_skips_when_not_triggered(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    service = VisionValidationService(
        runner=_FakeRunner(
            output=VisionRunnerOutput(
                screenshots=[],
                recording_path=None,
                dom_snapshot=None,
                duration_seconds=0.0,
                error=None,
            )
        ),
        enabled=True,
    )

    enriched, records = asyncio.run(
        service.validate_triggered_findings(
            run_id="run-skip",
            findings=[
                {
                    "title": "candidate",
                    "target": "example.com",
                    "requires_validation": False,
                }
            ],
        )
    )
    assert len(enriched) == 1
    assert records == []
    assert "vision_validation" not in enriched[0]


def test_vision_validation_records_artifacts_when_triggered(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    rec_file = tmp_path / "recordings" / "run-ok" / "capture.webm"
    rec_file.parent.mkdir(parents=True, exist_ok=True)
    rec_file.write_bytes(b"video-bytes")

    shot1 = tmp_path / "screenshots" / "run-ok" / "a.png"
    shot2 = tmp_path / "screenshots" / "run-ok" / "b.png"
    shot1.parent.mkdir(parents=True, exist_ok=True)
    shot1.write_bytes(b"png-a")
    shot2.write_bytes(b"png-b")

    service = VisionValidationService(
        runner=_FakeRunner(
            output=VisionRunnerOutput(
                screenshots=[str(shot1), str(shot2)],
                recording_path=str(rec_file),
                dom_snapshot="<html>ok</html>",
                duration_seconds=1.25,
                error=None,
            )
        ),
        enabled=True,
    )

    enriched, records = asyncio.run(
        service.validate_triggered_findings(
            run_id="run-ok",
            findings=[
                {
                    "title": "xss",
                    "target": "example.com",
                    "url": "https://example.com/search?q=1",
                    "trigger_decision": {"requires_validation": True, "reason": "confidence_below_threshold"},
                }
            ],
        )
    )

    assert len(enriched) == 1
    row = enriched[0]
    assert row["vision_status"] == "completed"
    assert row["recording_path"] == str(rec_file)
    assert len(row["screenshots"]) == 2
    assert row["vision_evidence_ready"] is True
    assert len(records) == 1
    assert records[0]["status"] == "completed"
    assert records[0]["recording_path"] == str(rec_file)
    assert records[0]["sha256"]


def test_vision_validation_marks_finding_uncertain_on_failure(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    service = VisionValidationService(
        runner=_FakeRunner(
            output=VisionRunnerOutput(
                screenshots=[],
                recording_path=None,
                dom_snapshot=None,
                duration_seconds=0.4,
                error="capture_failed",
            )
        ),
        enabled=True,
    )

    enriched, records = asyncio.run(
        service.validate_triggered_findings(
            run_id="run-fail",
            findings=[
                {
                    "title": "sqli",
                    "target": "example.com",
                    "url": "https://example.com/item?id=1",
                    "trigger_decision": {"requires_validation": True, "reason": "state_uncertain"},
                }
            ],
        )
    )

    assert len(enriched) == 1
    row = enriched[0]
    assert row["vision_status"] == "failed"
    assert row["requires_validation"] is True
    assert row["state_uncertain"] is True
    assert row["validation_reason"] == "vision_evidence_missing_or_failed"
    assert len(records) == 1
    assert records[0]["status"] == "failed"


def test_vision_analysis_confirmed_promotes_finding(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    # Create two fake screenshot files
    shot1 = tmp_path / "screenshots" / "run-confirmed" / "baseline.png"
    shot2 = tmp_path / "screenshots" / "run-confirmed" / "exploit.png"
    shot1.parent.mkdir(parents=True, exist_ok=True)
    shot1.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    shot2.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    from apps.backend.src.core.vision_validation_service import VisionAnalysisResult

    class _FakeAnalyzer:
        async def analyze(self, *, baseline_path, exploit_path, finding_context):
            return VisionAnalysisResult(
                verdict="confirmed",
                confidence=0.92,
                visual_delta="alert dialog appeared",
                indicators=["alert dialog visible", "reflected payload in page title"],
                finding_type_detected="xss",
            ).compute_sha256()

    service = VisionValidationService(
        runner=_FakeRunner(
            output=VisionRunnerOutput(
                screenshots=[str(shot1), str(shot2)],
                recording_path=None,
                dom_snapshot=None,
                duration_seconds=1.0,
                error=None,
            )
        ),
        analyzer=_FakeAnalyzer(),
        enabled=True,
    )
    enriched, records = asyncio.run(
        service.validate_triggered_findings(
            run_id="run-confirmed",
            findings=[{
                "title": "xss",
                "target": "example.com",
                "url": "https://example.com/search?q=1",
                "severity": "low",
                "trigger_decision": {"requires_validation": True, "reason": "test"},
            }],
        )
    )
    row = enriched[0]
    assert row["validated"] is True
    assert row["vision_evidence_ready"] is True
    assert row.get("suppressed") is not True
    assert row["vision_status"] == "completed"
    # severity auto-promoted from low → medium
    assert row["severity"] == "medium"
    # analysis attached and hashed
    analysis = row["vision_validation"]["analysis"]
    assert analysis["verdict"] == "confirmed"
    assert analysis["confidence"] == 0.92
    assert analysis["sha256"]  # evidence chain hash present


def test_vision_analysis_false_positive_suppresses_finding(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    shot1 = tmp_path / "screenshots" / "run-fp" / "baseline.png"
    shot2 = tmp_path / "screenshots" / "run-fp" / "exploit.png"
    shot1.parent.mkdir(parents=True, exist_ok=True)
    shot1.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    shot2.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    from apps.backend.src.core.vision_validation_service import VisionAnalysisResult

    class _FakeFPAnalyzer:
        async def analyze(self, **kwargs):
            return VisionAnalysisResult(
                verdict="false_positive",
                confidence=0.91,
                visual_delta="no visible change",
                indicators=["pages appear identical"],
            ).compute_sha256()

    service = VisionValidationService(
        runner=_FakeRunner(
            output=VisionRunnerOutput(
                screenshots=[str(shot1), str(shot2)],
                recording_path=None,
                dom_snapshot=None,
                duration_seconds=0.8,
                error=None,
            )
        ),
        analyzer=_FakeFPAnalyzer(),
        enabled=True,
    )
    enriched, _ = asyncio.run(
        service.validate_triggered_findings(
            run_id="run-fp",
            findings=[{
                "title": "sqli",
                "target": "example.com",
                "url": "https://example.com/item?id=1",
                "trigger_decision": {"requires_validation": True, "reason": "test"},
            }],
        )
    )
    row = enriched[0]
    assert row["suppressed"] is True
    assert row["requires_human_review"] is True
    assert row["suppression_reason"] == "vision_analysis_false_positive"
    assert row.get("validated") is not True


def test_vision_analysis_inconclusive_requires_validation(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    shot1 = tmp_path / "screenshots" / "run-inconc" / "baseline.png"
    shot2 = tmp_path / "screenshots" / "run-inconc" / "exploit.png"
    shot1.parent.mkdir(parents=True, exist_ok=True)
    shot1.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    shot2.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    from apps.backend.src.core.vision_validation_service import VisionAnalysisResult

    class _FakeInconcAnalyzer:
        async def analyze(self, **kwargs):
            return VisionAnalysisResult(
                verdict="inconclusive",
                confidence=0.45,
                visual_delta="minor layout shift, unclear cause",
                indicators=[],
            ).compute_sha256()

    service = VisionValidationService(
        runner=_FakeRunner(
            output=VisionRunnerOutput(
                screenshots=[str(shot1), str(shot2)],
                recording_path=None,
                dom_snapshot=None,
                duration_seconds=0.9,
                error=None,
            )
        ),
        analyzer=_FakeInconcAnalyzer(),
        enabled=True,
    )
    enriched, _ = asyncio.run(
        service.validate_triggered_findings(
            run_id="run-inconc",
            findings=[{
                "title": "ssrf",
                "target": "example.com",
                "url": "https://example.com/fetch?url=1",
                "trigger_decision": {"requires_validation": True, "reason": "test"},
            }],
        )
    )
    row = enriched[0]
    assert row["requires_validation"] is True
    assert row.get("validated") is not True
    assert row.get("suppressed") is not True


def test_vision_analysis_degradation_never_blocks_pipeline(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    shot1 = tmp_path / "screenshots" / "run-degrade" / "baseline.png"
    shot2 = tmp_path / "screenshots" / "run-degrade" / "exploit.png"
    shot1.parent.mkdir(parents=True, exist_ok=True)
    shot1.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    shot2.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    from apps.backend.src.core.vision_validation_service import VisionAnalysisResult  # noqa: F401

    class _CrashingAnalyzer:
        async def analyze(self, **kwargs):
            # Simulate API timeout / network error — must not propagate
            raise RuntimeError("Anthropic API unreachable")

    service = VisionValidationService(
        runner=_FakeRunner(
            output=VisionRunnerOutput(
                screenshots=[str(shot1), str(shot2)],
                recording_path=None,
                dom_snapshot=None,
                duration_seconds=0.5,
                error=None,
            )
        ),
        analyzer=_CrashingAnalyzer(),
        enabled=True,
    )
    enriched, records = asyncio.run(
        service.validate_triggered_findings(
            run_id="run-degrade",
            findings=[{
                "title": "rce",
                "target": "example.com",
                "url": "https://example.com/exec?cmd=id",
                "trigger_decision": {"requires_validation": True, "reason": "test"},
            }],
        )
    )
    # pipeline must complete — no exception raised
    assert len(enriched) == 1
    row = enriched[0]
    assert row["vision_status"] == "completed"  # capture itself succeeded
    assert row["requires_validation"] is True    # degraded to human queue

