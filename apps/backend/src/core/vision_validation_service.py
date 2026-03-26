from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from pydantic import BaseModel, Field

from .helpers import artifacts_root


def _sanitize_text(value: str, max_chars: int = 4000) -> str:
    text = value or ""
    # Redact likely key/token-like sequences.
    text = re.sub(r"\b[a-zA-Z0-9_\-]{24,}\b", "[REDACTED]", text)
    text = re.sub(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    return text[:max_chars]


def _sha256_file(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    digest = hashlib.sha256()
    with p.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _url_from_finding(row: dict[str, Any]) -> str | None:
    for key in ("url", "evidence_ref", "target"):
        value = str(row.get(key) or "").strip()
        if not value:
            continue
        if value.startswith(("http://", "https://")):
            return value
        if key == "target":
            return f"https://{value}"
    return None


def _inject_query_param(url: str, param: str | None, payload: str | None) -> str:
    if not param or not payload:
        return url
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query[param] = [payload]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


class VisionRecordingMetadata(BaseModel):
    recording_path: str | None = None
    duration: str
    trigger_reason: str
    timestamp: str
    sha256: str | None = None


class VisionAnalysisResult(BaseModel):
    """Result from the LLM vision analysis pass comparing baseline and exploit screenshots."""

    verdict: str  # 'confirmed' | 'false_positive' | 'inconclusive'
    confidence: float
    visual_delta: str
    indicators: list[str] = Field(default_factory=list)
    finding_type_detected: str | None = None
    error: str | None = None
    sha256: str | None = None  # hash of the serialised result for evidence chain

    def compute_sha256(self) -> "VisionAnalysisResult":
        """Return a copy of this result with the sha256 field populated."""
        payload = self.model_dump_json(exclude={"sha256"})
        digest = hashlib.sha256(payload.encode()).hexdigest()
        return self.model_copy(update={"sha256": digest})


class VisionValidationResult(BaseModel):
    status: str
    finding_key: str
    screenshots: list[str] = Field(default_factory=list)
    metadata: VisionRecordingMetadata
    dom_snapshot: str | None = None
    error: str | None = None
    analysis: VisionAnalysisResult | None = None

    def persistence_record(self, *, run_id: str) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "finding_key": self.finding_key,
            "status": self.status,
            "screenshots": self.screenshots,
            "recording_path": self.metadata.recording_path,
            "duration": self.metadata.duration,
            "trigger_reason": self.metadata.trigger_reason,
            "timestamp": self.metadata.timestamp,
            "sha256": self.metadata.sha256,
            "error": self.error,
            "analysis": self.analysis.model_dump() if self.analysis else None,
        }


@dataclass
class VisionRunnerOutput:
    screenshots: list[str]
    recording_path: str | None
    dom_snapshot: str | None
    duration_seconds: float
    error: str | None = None


class VisionRunner(Protocol):
    async def capture(
        self,
        *,
        finding_key: str,
        url: str,
        exploit_url: str,
        recording_dir: Path,
        screenshot_dir: Path,
        include_dom_snapshot: bool,
    ) -> VisionRunnerOutput:
        ...


class VisionAnalyzer(Protocol):
    """Protocol for LLM-backed screenshot comparison analyzers."""

    async def analyze(
        self,
        *,
        baseline_path: str,
        exploit_path: str,
        finding_context: dict[str, Any],
    ) -> VisionAnalysisResult:
        ...


# System prompt for the Claude vision analysis pass.
_VISION_ANALYSIS_SYSTEM_PROMPT = (
    "You are a vulnerability validation agent embedded in a bug bounty hunting platform. "
    "You will receive two screenshots: a baseline state and an exploit-injected state. "
    "Analyze both and return a JSON object with these fields:\n"
    "- verdict: 'confirmed' | 'false_positive' | 'inconclusive'\n"
    "- confidence: float 0.0-1.0\n"
    "- visual_delta: description of what changed between baseline and exploit state\n"
    "- indicators: list of specific visual evidence supporting the verdict "
    "(e.g., 'alert dialog visible', 'reflected payload in DOM', 'redirect to attacker domain')\n"
    "- finding_type_detected: best guess at vulnerability class from visual evidence alone\n"
    "Return only valid JSON. No markdown, no preamble."
)


class ClaudeVisionAnalyzer:
    """
    Sends baseline and exploit screenshots to Claude for visual vulnerability analysis.
    Falls back to an inconclusive result on any error so the pipeline remains non-blocking.
    """

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key
        self._model = model or os.getenv("K1_VISION_MODEL", "claude-sonnet-4-6")

    def _get_api_key(self) -> str:
        """Resolve the Anthropic API key from constructor arg or secret manager."""
        if self._api_key:
            return self._api_key
        from .secret_manager import get_secret_manager  # type: ignore

        key = (get_secret_manager().get_optional("ANTHROPIC_API_KEY") or "").strip()
        if not key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        return key

    @staticmethod
    def _encode_image(path: str) -> str:
        """Base64-encode an image file for the Anthropic multimodal API."""
        with open(path, "rb") as f:
            return __import__("base64").b64encode(f.read()).decode()

    async def analyze(
        self,
        *,
        baseline_path: str,
        exploit_path: str,
        finding_context: dict[str, Any],
    ) -> VisionAnalysisResult:
        """
        Compare baseline and exploit screenshots via Claude vision.
        Always returns a VisionAnalysisResult; errors are surfaced in the `error` field.
        """
        try:
            import anthropic  # type: ignore

            api_key = self._get_api_key()
            client = anthropic.AsyncAnthropic(api_key=api_key)

            baseline_b64 = await asyncio.get_event_loop().run_in_executor(
                None, self._encode_image, baseline_path
            )
            exploit_b64 = await asyncio.get_event_loop().run_in_executor(
                None, self._encode_image, exploit_path
            )

            # Build multimodal message: baseline screenshot → exploit screenshot → context.
            user_content: list[dict[str, Any]] = [
                {"type": "text", "text": "Baseline screenshot (before exploit injection):"},
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": baseline_b64},
                },
                {"type": "text", "text": "Exploit-injected screenshot (after payload delivery):"},
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": exploit_b64},
                },
                {
                    "type": "text",
                    "text": (
                        "Finding context: "
                        + json.dumps(
                            {
                                k: str(v)[:200]
                                for k, v in finding_context.items()
                                if k
                                in (
                                    "title",
                                    "target",
                                    "parameter_name",
                                    "payload",
                                    "severity",
                                )
                            }
                        )
                    ),
                },
            ]

            response = await client.messages.create(
                model=self._model,
                max_tokens=512,
                system=_VISION_ANALYSIS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            raw = response.content[0].text.strip()

            # Strip markdown code fences if the model wraps the JSON.
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            parsed = json.loads(raw)
            result = VisionAnalysisResult(
                verdict=str(parsed.get("verdict", "inconclusive")),
                confidence=float(parsed.get("confidence", 0.0)),
                visual_delta=str(parsed.get("visual_delta", "")),
                indicators=[str(i) for i in parsed.get("indicators", [])],
                finding_type_detected=parsed.get("finding_type_detected"),
            )
            return result.compute_sha256()

        except Exception as exc:
            return VisionAnalysisResult(
                verdict="inconclusive",
                confidence=0.0,
                visual_delta="",
                indicators=[],
                error=f"vision_analysis_failed:{type(exc).__name__}:{exc}",
            )


class PlaywrightVisionRunner:
    async def capture(
        self,
        *,
        finding_key: str,
        url: str,
        exploit_url: str,
        recording_dir: Path,
        screenshot_dir: Path,
        include_dom_snapshot: bool,
    ) -> VisionRunnerOutput:
        started = time.time()
        try:
            from playwright.async_api import async_playwright  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on local install
            return VisionRunnerOutput(
                screenshots=[],
                recording_path=None,
                dom_snapshot=None,
                duration_seconds=0.0,
                error=f"playwright_unavailable:{exc}",
            )

        screenshots: list[str] = []
        recording_path: str | None = None
        dom_snapshot: str | None = None
        page = None
        context = None
        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                # Recording starts before exploit execution as soon as context/page are created.
                context = await browser.new_context(
                    record_video_dir=str(recording_dir),
                    record_video_size={"width": 1280, "height": 720},
                )
                page = await context.new_page()

                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                initial_path = screenshot_dir / f"{finding_key}_initial.png"
                await page.screenshot(path=str(initial_path), full_page=True)
                screenshots.append(str(initial_path))

                if exploit_url != url:
                    await page.goto(exploit_url, wait_until="domcontentloaded", timeout=30000)
                else:
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(700)

                impact_path = screenshot_dir / f"{finding_key}_impact.png"
                await page.screenshot(path=str(impact_path), full_page=True)
                screenshots.append(str(impact_path))

                if include_dom_snapshot:
                    dom_snapshot = _sanitize_text(await page.content(), max_chars=12000)

                video = page.video
                await context.close()
                context = None
                if video is not None:
                    recording_path = await video.path()
        except Exception as exc:
            return VisionRunnerOutput(
                screenshots=screenshots,
                recording_path=recording_path,
                dom_snapshot=dom_snapshot,
                duration_seconds=max(0.0, time.time() - started),
                error=f"vision_capture_failed:{exc}",
            )
        finally:
            try:
                if context is not None:
                    await context.close()
            except Exception:
                pass
            try:
                if browser is not None:
                    await browser.close()
            except Exception:
                pass

        return VisionRunnerOutput(
            screenshots=screenshots,
            recording_path=recording_path,
            dom_snapshot=dom_snapshot,
            duration_seconds=max(0.0, time.time() - started),
            error=None,
        )


class VisionValidationService:
    """
    Triggered vision validation with mandatory screen recording.
    Runs only when trigger decision requires validation.
    """

    def __init__(
        self,
        *,
        runner: VisionRunner | None = None,
        analyzer: VisionAnalyzer | None = None,
        enabled: bool | None = None,
        include_dom_snapshot: bool | None = None,
    ) -> None:
        self._runner = runner or PlaywrightVisionRunner()
        # analyzer=None means lazy-init ClaudeVisionAnalyzer on first use.
        self._analyzer: VisionAnalyzer | None = analyzer
        self._analysis_enabled = (
            os.getenv("K1_VISION_ANALYSIS_ENABLED", "true").strip().lower()
            not in {"0", "false", "no"}
        )
        self._enabled = (
            enabled
            if enabled is not None
            else os.getenv("K1_VISION_VALIDATION_ENABLED", "true").strip().lower()
            not in {"0", "false", "no"}
        )
        self._include_dom_snapshot = (
            include_dom_snapshot
            if include_dom_snapshot is not None
            else os.getenv("K1_VISION_INCLUDE_DOM_SNAPSHOT", "false").strip().lower()
            in {"1", "true", "yes"}
        )

    def _get_analyzer(self) -> VisionAnalyzer:
        """Return the configured analyzer, falling back to ClaudeVisionAnalyzer."""
        if self._analyzer is not None:
            return self._analyzer
        return ClaudeVisionAnalyzer()

    @staticmethod
    def _finding_key(row: dict[str, Any], index: int) -> str:
        base = f"{row.get('title','finding')}-{row.get('target','target')}-{index}"
        return re.sub(r"[^a-zA-Z0-9._-]+", "_", base).strip("._-")[:96] or f"finding_{index}"

    def _is_triggered(self, row: dict[str, Any]) -> tuple[bool, str]:
        trigger = row.get("trigger_decision")
        if isinstance(trigger, dict):
            if bool(trigger.get("requires_validation")):
                return True, str(trigger.get("reason") or "trigger_requires_validation")
            return False, str(trigger.get("reason") or "not_triggered")
        if bool(row.get("requires_validation")):
            return True, str(row.get("validation_reason") or "requires_validation")
        return False, "not_triggered"

    async def validate_triggered_findings(
        self,
        *,
        run_id: str,
        findings: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if not findings:
            return [], []

        enriched: list[dict[str, Any]] = []
        validation_records: list[dict[str, Any]] = []
        recordings_dir = artifacts_root() / "recordings" / run_id
        screenshots_dir = artifacts_root() / "screenshots" / run_id
        recordings_dir.mkdir(parents=True, exist_ok=True)
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        for idx, raw in enumerate(findings, start=1):
            row = dict(raw)
            triggered, trigger_reason = self._is_triggered(row)
            if not triggered:
                enriched.append(row)
                continue

            finding_key = self._finding_key(row, idx)
            url = _url_from_finding(row)
            payload = str(row.get("payload") or row.get("original_payload") or "").strip() or None
            param = str(row.get("parameter_name") or row.get("parameter") or "").strip() or None

            timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            if not self._enabled:
                result = VisionValidationResult(
                    status="skipped",
                    finding_key=finding_key,
                    screenshots=[],
                    metadata=VisionRecordingMetadata(
                        recording_path=None,
                        duration="0.0s",
                        trigger_reason=trigger_reason,
                        timestamp=timestamp,
                        sha256=None,
                    ),
                    dom_snapshot=None,
                    error="vision_validation_disabled",
                )
            elif not url:
                result = VisionValidationResult(
                    status="failed",
                    finding_key=finding_key,
                    screenshots=[],
                    metadata=VisionRecordingMetadata(
                        recording_path=None,
                        duration="0.0s",
                        trigger_reason=trigger_reason,
                        timestamp=timestamp,
                        sha256=None,
                    ),
                    dom_snapshot=None,
                    error="no_target_url_for_vision_validation",
                )
            else:
                exploit_url = _inject_query_param(url, param, payload)
                run_out = await self._runner.capture(
                    finding_key=finding_key,
                    url=url,
                    exploit_url=exploit_url,
                    recording_dir=recordings_dir,
                    screenshot_dir=screenshots_dir,
                    include_dom_snapshot=self._include_dom_snapshot,
                )
                sha256 = _sha256_file(run_out.recording_path)
                # Status is "completed" when screenshots were captured without error.
                # Recording is treated as optional supplementary evidence.
                status = "completed" if run_out.screenshots and not run_out.error else "failed"
                result = VisionValidationResult(
                    status=status,
                    finding_key=finding_key,
                    screenshots=run_out.screenshots,
                    metadata=VisionRecordingMetadata(
                        recording_path=run_out.recording_path,
                        duration=f"{run_out.duration_seconds:.3f}s",
                        trigger_reason=trigger_reason,
                        timestamp=timestamp,
                        sha256=sha256,
                    ),
                    dom_snapshot=run_out.dom_snapshot,
                    error=run_out.error,
                )

            # --- LLM vision analysis pass ---
            analysis: VisionAnalysisResult | None = None
            if (
                self._analysis_enabled
                and result.status == "completed"
                and len(result.screenshots) >= 2
            ):
                try:
                    analysis = await self._get_analyzer().analyze(
                        baseline_path=result.screenshots[0],
                        exploit_path=result.screenshots[1],
                        finding_context=row,
                    )
                except Exception as exc:
                    # Analyzer failure must never block the pipeline; degrade gracefully.
                    analysis = VisionAnalysisResult(
                        verdict="inconclusive",
                        confidence=0.0,
                        visual_delta="",
                        indicators=[],
                        error=f"vision_analysis_failed:{type(exc).__name__}:{exc}",
                    )
                result = result.model_copy(update={"analysis": analysis})

            # Apply verdict-based state promotion derived from the analysis result.
            if analysis is not None and analysis.error is not None:
                # Analyzer failed (API error, timeout, etc.) — degrade to human review queue.
                row["requires_validation"] = True
            elif analysis is not None and analysis.error is None:
                if analysis.verdict == "confirmed" and analysis.confidence >= 0.85:
                    row["validated"] = True
                    row["vision_evidence_ready"] = True
                    # Auto-promote severity one step if currently below high.
                    _sev = str(row.get("severity", "")).lower()
                    if _sev in ("info", "low"):
                        row["severity"] = "medium"
                    elif _sev == "medium":
                        row["severity"] = "high"
                elif analysis.verdict == "false_positive" and analysis.confidence >= 0.85:
                    row["suppressed"] = True
                    row["requires_human_review"] = True
                    row["suppression_reason"] = "vision_analysis_false_positive"
                else:
                    row["requires_validation"] = True

            row["vision_validation"] = result.model_dump()
            row["recording_path"] = result.metadata.recording_path
            row["screenshots"] = result.screenshots
            row["vision_status"] = result.status
            row["vision_sha256"] = result.metadata.sha256
            row["vision_duration"] = result.metadata.duration
            if result.status != "completed":
                row["requires_validation"] = True
                row["state_uncertain"] = True
                row["validation_reason"] = "vision_evidence_missing_or_failed"
            else:
                row["vision_evidence_ready"] = True

            enriched.append(row)
            validation_records.append(result.persistence_record(run_id=run_id))

        return enriched, validation_records

