"""
ModelRouter — task complexity classification and tier dispatch.

Classification strategy:
  Primary:  Gemma3:8b via Ollama (Tier 4 — local, 5-15 t/s on CPU-only hardware).
            This is a first-class Gemini CLI feature: native local model routing.
            NEVER dispatches tool calls.  Text classification ONLY.
  Fallback: Keyword-based classification (instant, no model required).
            Activated when Ollama is unavailable or returns non-JSON output.
            Pipeline is NEVER blocked on local model status.

Routing map:
  LOW    → Flash-Lite (Tier 2)  — high-volume recon, summarisation, simple queries
  MEDIUM → Flash      (Tier 1)  — standard agentic work, tool dispatch, BBP pipeline
  HIGH   → Pro        (Tier 3)  — EXPLICIT only: report gen, CVE triage, complex chains

Result cache:
  Classification results are cached by task-instruction SHA-256 with a 5-minute TTL.
  Identical task signatures avoid redundant classification calls.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import time
from typing import Any, Optional

from .task_schema import ModelTier, TaskComplexity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _routing_model() -> str:
    return os.getenv("GEMINI_LOCAL_ROUTING_MODEL", "gemma3:8b")


def _ollama_host() -> str:
    return os.getenv("OLLAMA_API_URL", "http://localhost:11434")


_CACHE_TTL_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Keyword-based fallback classifier
# ---------------------------------------------------------------------------

_HIGH_KEYWORDS = frozenset({
    "report", "generate report", "final validation", "submit", "cve", "cvss",
    "triage", "multi-hop", "attack chain", "exploit chain", "business impact",
    "proof of concept", "writeup", "disclosure",
})

_LOW_KEYWORDS = frozenset({
    "enumerate", "dns", "subdomain", "discover", "list", "scan", "banner",
    "classify", "categorise", "categorize", "summarise", "summarize",
    "quick", "fast", "bulk", "batch", "recon",
})


def _keyword_classify(instruction: str) -> TaskComplexity:
    """Instant keyword-based classification.  Conservative — defaults to MEDIUM."""
    lower = instruction.lower()
    for kw in _HIGH_KEYWORDS:
        if kw in lower:
            return TaskComplexity.HIGH
    for kw in _LOW_KEYWORDS:
        if kw in lower:
            return TaskComplexity.LOW
    return TaskComplexity.MEDIUM


# ---------------------------------------------------------------------------
# Gemma3 local classifier
# ---------------------------------------------------------------------------

_CLASSIFY_PROMPT = """\
You are a task complexity classifier for a bug-bounty AI pipeline.
Classify the following task into exactly one of: LOW, MEDIUM, HIGH.

Rules:
- LOW: passive/bulk tasks — subdomain enum, banner scan, summarisation, classification
- MEDIUM: standard agentic work — tool dispatch, vulnerability analysis, BBP pipeline steps
- HIGH: complex reasoning ONLY — final report generation, CVE triage, multi-hop exploit chains,
        complex attack-chain construction, vulnerability validation before submission

Respond with ONLY a JSON object: {{"complexity": "LOW"}} or {{"complexity": "MEDIUM"}} or {{"complexity": "HIGH"}}

Task: {instruction}
"""


async def _classify_via_gemma(instruction: str, timeout: float = 8.0) -> Optional[TaskComplexity]:
    """Call Gemma3:8b via Ollama for classification.

    Returns None if Ollama is unavailable or output is malformed — caller
    must fall back to keyword classification.  The pipeline is NEVER blocked
    on local model availability.
    """
    model = _routing_model()
    prompt = _CLASSIFY_PROMPT.format(instruction=instruction[:500])

    # Prompt is delivered via stdin — never as a positional CLI argument —
    # to prevent argument-injection through crafted instruction strings.
    cmd = ["ollama", "run", model]
    prompt_bytes = prompt.encode("utf-8")
    try:
        loop = asyncio.get_event_loop()
        proc = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    input=prompt_bytes,
                    capture_output=True,
                    timeout=timeout,
                ),
            ),
            timeout=timeout + 1.0,
        )
    except (asyncio.TimeoutError, FileNotFoundError, OSError) as exc:
        logger.debug("Gemma3 classification unavailable (%s) — using keyword fallback", exc)
        return None

    stdout = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    if not stdout:
        return None

    # Extract JSON from the response (model may emit surrounding text)
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and "complexity" in line:
            try:
                parsed = json.loads(line)
                raw = str(parsed.get("complexity", "")).upper()
                if raw in ("LOW", "MEDIUM", "HIGH"):
                    return TaskComplexity[raw]
            except json.JSONDecodeError:
                continue

    logger.debug("Gemma3 returned non-JSON: %r — using keyword fallback", stdout[:200])
    return None


# ---------------------------------------------------------------------------
# Classification cache
# ---------------------------------------------------------------------------

class _ClassificationCache:
    """Simple in-memory TTL cache keyed by instruction SHA-256 hex."""

    def __init__(self, ttl_seconds: int = _CACHE_TTL_SECONDS) -> None:
        self._store: dict[str, tuple[TaskComplexity, float]] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[TaskComplexity]:
        entry = self._store.get(key)
        if entry is None:
            return None
        complexity, ts = entry
        if time.monotonic() - ts > self._ttl:
            del self._store[key]
            return None
        return complexity

    def set(self, key: str, complexity: TaskComplexity) -> None:
        self._store[key] = (complexity, time.monotonic())

    def clear(self) -> None:
        self._store.clear()


def _instruction_key(instruction: str) -> str:
    return hashlib.sha256(instruction.encode()).hexdigest()


# ---------------------------------------------------------------------------
# ModelRouter
# ---------------------------------------------------------------------------

class ModelRouter:
    """Classifies tasks and maps them to the appropriate model tier.

    Usage:
        router = ModelRouter()
        tier = await router.route(task)
    """

    def __init__(self) -> None:
        self._cache = _ClassificationCache()

    async def classify(self, instruction: str, *, hint: Optional[TaskComplexity] = None) -> TaskComplexity:
        """Return complexity classification for *instruction*.

        If *hint* is provided it is used directly (explicit override from caller).
        Otherwise: try Gemma3 → fall back to keywords.
        Results are cached by instruction SHA-256 for 5 minutes.
        """
        if hint is not None:
            return hint

        key = _instruction_key(instruction)
        cached = self._cache.get(key)
        if cached is not None:
            logger.debug("ModelRouter: cache hit key=%s complexity=%s", key[:8], cached.value)
            return cached

        # Attempt Gemma3 classification
        complexity = await _classify_via_gemma(instruction)

        if complexity is None:
            # Keyword fallback — guaranteed to return a result
            complexity = _keyword_classify(instruction)
            logger.debug(
                "ModelRouter: keyword fallback → %s for instruction=%r",
                complexity.value,
                instruction[:60],
            )
        else:
            logger.debug(
                "ModelRouter: gemma3 classified → %s for instruction=%r",
                complexity.value,
                instruction[:60],
            )

        self._cache.set(key, complexity)
        return complexity

    async def route(
        self,
        instruction: str,
        *,
        hint: Optional[TaskComplexity] = None,
        quota_status: Optional[Any] = None,
    ) -> ModelTier:
        """Classify *instruction* and return the dispatch ModelTier.

        Routing map:
          LOW    → Flash-Lite (Tier 2)
          MEDIUM → Flash      (Tier 1)
          HIGH   → Pro        (Tier 3)   ← EXPLICIT only

        If quota_status is supplied, automatic demotion rules apply:
          - Flash RPD remaining < flash_daily_alert → MEDIUM routes to Flash-Lite
          - Pro restricted (buffer zone active)     → HIGH routes to Flash
        """
        complexity = await self.classify(instruction, hint=hint)

        if complexity == TaskComplexity.LOW:
            return ModelTier.FLASH_LITE

        if complexity == TaskComplexity.HIGH:
            # Guard: Pro restricted due to near-daily-cap?
            if quota_status is not None and quota_status.pro_restricted:
                logger.warning(
                    "ModelRouter: Pro restricted (buffer zone) — downgrading HIGH→MEDIUM dispatch"
                )
                return ModelTier.FLASH
            return ModelTier.PRO

        # MEDIUM — standard path
        # Demotion: Flash RPD low → spill to Flash-Lite
        if quota_status is not None and quota_status.flash_lite_spillover_active:
            logger.debug(
                "ModelRouter: Flash spillover active — routing MEDIUM→Flash-Lite"
            )
            return ModelTier.FLASH_LITE

        return ModelTier.FLASH

    def clear_cache(self) -> None:
        self._cache.clear()
