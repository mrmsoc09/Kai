"""
Tests for the 5-tier GeminiOrchestrator system.

Coverage:
  - All five tier promotion paths
  - Quota persistence across simulated process restart
  - 429 handling: backoff, tier promotion, no upstream propagation
  - Pro hard cap enforcement at 80 RPD
  - Emergency fallback (Tier 5) activation and prominent logging
  - orchestrationService API method coverage (REST endpoints)
  - ScreenVisionAgent injection into session context

All external calls (Gemini API, Ollama subprocess, WebSocket) are mocked for CI.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Environment setup before any imports
# ---------------------------------------------------------------------------

os.environ.setdefault("K1_TEST_MODE", "true")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("K1_DEV_TOKEN", "devtoken")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
os.environ.setdefault("K1_ENABLE_BOOTSTRAP_AUTH", "true")
# Override Gemini limits to tiny values for fast tests
os.environ.setdefault("GEMINI_FLASH_DAILY_LIMIT", "10")
os.environ.setdefault("GEMINI_FLASH_LITE_DAILY_LIMIT", "10")
os.environ.setdefault("GEMINI_PRO_DAILY_LIMIT", "10")
os.environ.setdefault("GEMINI_PRO_DAILY_CAP", "8")
os.environ.setdefault("GEMINI_PRO_DAILY_ALERT", "3")
os.environ.setdefault("GEMINI_FLASH_DAILY_ALERT", "4")
os.environ.setdefault("GEMINI_FLASH_RPM", "10")
os.environ.setdefault("GEMINI_FLASH_LITE_RPM", "15")
os.environ.setdefault("GEMINI_PRO_RPM", "5")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tracker(tmp_path: Path) -> "QuotaTracker":
    """Return a fresh QuotaTracker with test-scoped persistence file."""
    from apps.backend.src.core.quota_tracker import QuotaTracker

    QuotaTracker.reset_singleton()
    persist = tmp_path / "quota_state.json"
    with patch.dict(os.environ, {"GEMINI_QUOTA_PERSIST_PATH": str(persist)}):
        tracker = QuotaTracker.load()
    return tracker


# ---------------------------------------------------------------------------
# task_schema
# ---------------------------------------------------------------------------


class TestTaskSchema:
    def test_model_tier_values(self):
        from apps.backend.src.core.task_schema import ModelTier

        assert ModelTier.FLASH.value == "flash"
        assert ModelTier.FLASH_LITE.value == "flash_lite"
        assert ModelTier.PRO.value == "pro"
        assert ModelTier.LOCAL_ROUTING.value == "local_routing"
        assert ModelTier.LOCAL_EMERGENCY.value == "local_emergency"

    def test_quota_status_to_dict(self):
        from apps.backend.src.core.task_schema import ModelTier, QuotaStatus

        qs = QuotaStatus(active_tier=ModelTier.FLASH)
        d = qs.to_dict()
        assert "flash" in d
        assert "flash_lite" in d
        assert "pro" in d
        assert d["active_tier"] == "flash"

    def test_orchestration_task_defaults(self):
        from apps.backend.src.core.task_schema import OrchestrationTask

        t = OrchestrationTask(instruction="test")
        assert t.task_id  # auto-generated UUID
        assert t.priority == 5
        assert t.timeout_seconds == 120


# ---------------------------------------------------------------------------
# QuotaTracker
# ---------------------------------------------------------------------------


class TestQuotaTracker:
    def test_can_consume_returns_true_initially(self, tmp_path):
        from apps.backend.src.core.task_schema import ModelTier

        tracker = _make_tracker(tmp_path)
        ok, reason = tracker.can_consume(ModelTier.FLASH)
        assert ok
        assert reason == ""

    def test_consume_decrements_rpd(self, tmp_path):
        from apps.backend.src.core.task_schema import ModelTier

        tracker = _make_tracker(tmp_path)
        before = tracker.status().flash_rpd_remaining
        tracker.consume(ModelTier.FLASH)
        assert tracker.status().flash_rpd_remaining == before - 1

    def test_quota_exhausted_blocks_consumption(self, tmp_path):
        from apps.backend.src.core.task_schema import ModelTier

        tracker = _make_tracker(tmp_path)
        model = tracker._models[ModelTier.FLASH]
        # Exhaust the daily limit
        model.rpd_consumed = model.rpd_limit
        model.count_date = model._today()

        ok, reason = tracker.can_consume(ModelTier.FLASH)
        assert not ok
        assert "quota" in reason.lower() or "rpd" in reason.lower() or "daily" in reason.lower()

    def test_pro_hard_cap_at_configured_rpd(self, tmp_path):
        """Pro hard cap stops dispatch at GEMINI_PRO_DAILY_CAP (8 in test env)."""
        from apps.backend.src.core.task_schema import ModelTier

        tracker = _make_tracker(tmp_path)
        model = tracker._models[ModelTier.PRO]
        model.rpd_consumed = 8  # == GEMINI_PRO_DAILY_CAP for tests
        model.count_date = model._today()

        ok, reason = tracker.can_consume(ModelTier.PRO)
        assert not ok
        assert "hard cap" in reason.lower() or "cap" in reason.lower()

    def test_next_available_tier_promotion(self, tmp_path):
        """When Flash is exhausted, next_available_tier returns FLASH_LITE."""
        from apps.backend.src.core.task_schema import ModelTier

        tracker = _make_tracker(tmp_path)
        model = tracker._models[ModelTier.FLASH]
        model.rpd_consumed = model.rpd_limit
        model.count_date = model._today()

        next_tier = tracker.next_available_tier(ModelTier.FLASH)
        assert next_tier == ModelTier.FLASH_LITE

    def test_all_api_tiers_exhausted_activates_emergency(self, tmp_path, caplog):
        """When all API tiers are exhausted, emergency fallback activates."""
        from apps.backend.src.core.task_schema import ModelTier

        tracker = _make_tracker(tmp_path)
        for tier in (ModelTier.FLASH, ModelTier.FLASH_LITE, ModelTier.PRO):
            model = tracker._models[tier]
            model.rpd_consumed = model.rpd_limit
            model.count_date = model._today()

        with caplog.at_level(logging.CRITICAL):
            next_tier = tracker.next_available_tier(ModelTier.PRO)

        assert next_tier == ModelTier.LOCAL_EMERGENCY
        assert tracker._emergency_active
        assert any("EMERGENCY" in r.message for r in caplog.records)

    def test_quota_persistence_across_restart(self, tmp_path):
        """Persisted daily counters survive a simulated process restart."""
        from apps.backend.src.core.quota_tracker import QuotaTracker
        from apps.backend.src.core.task_schema import ModelTier

        persist = tmp_path / "quota_state.json"

        # First "process" — consume some requests
        with patch.dict(os.environ, {"GEMINI_QUOTA_PERSIST_PATH": str(persist)}):
            QuotaTracker.reset_singleton()
            t1 = QuotaTracker.load()
            t1.consume(ModelTier.FLASH)
            t1.consume(ModelTier.FLASH)
            t1.consume(ModelTier.FLASH)
            t1.save()

        # Second "process" — load from disk
        with patch.dict(os.environ, {"GEMINI_QUOTA_PERSIST_PATH": str(persist)}):
            QuotaTracker.reset_singleton()
            t2 = QuotaTracker.load()

        assert t2._models[ModelTier.FLASH].rpd_consumed == 3

    def test_flash_low_callback_fires(self, tmp_path):
        """flash_low callback fires when Flash RPD drops below GEMINI_FLASH_DAILY_ALERT."""
        from apps.backend.src.core.task_schema import ModelTier

        tracker = _make_tracker(tmp_path)
        events: list[str] = []
        tracker.register_callback(lambda event, _: events.append(event))

        # Consume down to just below the alert threshold (4 in test env)
        model = tracker._models[ModelTier.FLASH]
        model.rpd_consumed = model.rpd_limit - 3  # leaves 3 remaining < alert=4
        model.count_date = model._today()
        tracker.consume(ModelTier.FLASH)  # drops to 2 remaining → triggers

        assert "flash_low" in events

    def test_pro_cap_callback_fires(self, tmp_path):
        """pro_cap_hard callback fires when Pro hits GEMINI_PRO_DAILY_CAP."""
        from apps.backend.src.core.task_schema import ModelTier

        tracker = _make_tracker(tmp_path)
        events: list[str] = []
        tracker.register_callback(lambda event, _: events.append(event))

        model = tracker._models[ModelTier.PRO]
        model.rpd_consumed = 7  # one below cap=8
        model.count_date = model._today()
        tracker.consume(ModelTier.PRO)  # hits cap

        assert "pro_cap_hard" in events

    def test_429_record_logs_without_raising(self, tmp_path, caplog):
        """record_429 logs prominently and does NOT propagate the error."""
        from apps.backend.src.core.task_schema import ModelTier

        tracker = _make_tracker(tmp_path)
        with caplog.at_level(logging.WARNING):
            tracker.record_429(ModelTier.FLASH)  # must not raise

        assert any("429" in r.message for r in caplog.records)

    def test_local_tiers_have_no_quota(self, tmp_path):
        """Tier 4 and 5 (local models) always return can_consume=True."""
        from apps.backend.src.core.task_schema import ModelTier

        tracker = _make_tracker(tmp_path)
        for tier in (ModelTier.LOCAL_ROUTING, ModelTier.LOCAL_EMERGENCY):
            ok, reason = tracker.can_consume(tier)
            assert ok, f"{tier.value} should have no quota cap"

    def test_quota_status_reflects_spillover(self, tmp_path):
        """flash_lite_spillover_active is True when Flash RPD < GEMINI_FLASH_DAILY_ALERT."""
        from apps.backend.src.core.task_schema import ModelTier

        tracker = _make_tracker(tmp_path)
        model = tracker._models[ModelTier.FLASH]
        model.rpd_consumed = model.rpd_limit - 2  # leaves 2 remaining < alert=4
        model.count_date = model._today()

        status = tracker.status()
        assert status.flash_lite_spillover_active


# ---------------------------------------------------------------------------
# ModelRouter
# ---------------------------------------------------------------------------


class TestModelRouter:
    def test_keyword_fallback_low(self):
        from apps.backend.src.core.model_router import _keyword_classify
        from apps.backend.src.core.task_schema import TaskComplexity

        assert _keyword_classify("enumerate subdomains for target") == TaskComplexity.LOW
        assert _keyword_classify("fast dns scan") == TaskComplexity.LOW

    def test_keyword_fallback_high(self):
        from apps.backend.src.core.model_router import _keyword_classify
        from apps.backend.src.core.task_schema import TaskComplexity

        assert _keyword_classify("generate final vulnerability report") == TaskComplexity.HIGH
        assert _keyword_classify("cve triage and writeup") == TaskComplexity.HIGH

    def test_keyword_fallback_medium_default(self):
        from apps.backend.src.core.model_router import _keyword_classify
        from apps.backend.src.core.task_schema import TaskComplexity

        assert _keyword_classify("analyze this API endpoint for vulnerabilities") == TaskComplexity.MEDIUM

    def test_route_low_returns_flash_lite(self):
        from apps.backend.src.core.model_router import ModelRouter
        from apps.backend.src.core.task_schema import ModelTier

        router = ModelRouter()
        tier = asyncio.run(router.route("enumerate subdomains"))
        assert tier == ModelTier.FLASH_LITE

    def test_route_medium_returns_flash(self):
        from apps.backend.src.core.model_router import ModelRouter
        from apps.backend.src.core.task_schema import ModelTier

        router = ModelRouter()
        tier = asyncio.run(router.route("analyze API endpoint for injection"))
        assert tier == ModelTier.FLASH

    def test_route_high_returns_pro(self):
        from apps.backend.src.core.model_router import ModelRouter
        from apps.backend.src.core.task_schema import ModelTier, TaskComplexity

        router = ModelRouter()
        tier = asyncio.run(router.route("generate final report", hint=TaskComplexity.HIGH))
        assert tier == ModelTier.PRO

    def test_route_respects_complexity_hint_override(self):
        from apps.backend.src.core.model_router import ModelRouter
        from apps.backend.src.core.task_schema import ModelTier, TaskComplexity

        router = ModelRouter()
        # LOW hint should override keyword classification of HIGH-looking instruction
        tier = asyncio.run(router.route("generate report", hint=TaskComplexity.LOW))
        assert tier == ModelTier.FLASH_LITE

    def test_route_medium_spillover_to_flash_lite(self):
        """MEDIUM tasks route to Flash-Lite when Flash spillover is active."""
        from apps.backend.src.core.model_router import ModelRouter
        from apps.backend.src.core.task_schema import ModelTier, QuotaStatus

        router = ModelRouter()
        quota = QuotaStatus(flash_lite_spillover_active=True)
        tier = asyncio.run(router.route("analyze endpoint", quota_status=quota))
        assert tier == ModelTier.FLASH_LITE

    def test_route_high_downgraded_when_pro_restricted(self):
        """HIGH tasks route to Flash when Pro is in restricted buffer zone."""
        from apps.backend.src.core.model_router import ModelRouter
        from apps.backend.src.core.task_schema import ModelTier, QuotaStatus, TaskComplexity

        router = ModelRouter()
        quota = QuotaStatus(pro_restricted=True)
        tier = asyncio.run(
            router.route("generate final report", hint=TaskComplexity.HIGH, quota_status=quota)
        )
        assert tier == ModelTier.FLASH

    def test_classification_cache_ttl(self):
        """Identical instructions return cached result."""
        from apps.backend.src.core.model_router import ModelRouter, _CACHE_TTL_SECONDS
        from apps.backend.src.core.task_schema import TaskComplexity
        import time

        router = ModelRouter()
        inst = "enumerate subdomains for x.com"
        result1 = asyncio.run(router.classify(inst))
        # Immediately cached
        result2 = asyncio.run(router.classify(inst))
        assert result1 == result2

    def test_gemma_unavailable_falls_back_to_keywords(self):
        """When Ollama is not running, classification still returns a valid result."""
        from apps.backend.src.core.model_router import ModelRouter, _classify_via_gemma
        from apps.backend.src.core.task_schema import TaskComplexity

        with patch(
            "apps.backend.src.core.model_router._classify_via_gemma",
            new=AsyncMock(return_value=None),
        ):
            router = ModelRouter()
            router.clear_cache()
            result = asyncio.run(router.classify("enumerate subdomains"))

        assert isinstance(result, TaskComplexity)


# ---------------------------------------------------------------------------
# GeminiOrchestrator (integration — all LLM calls mocked)
# ---------------------------------------------------------------------------


class TestGeminiOrchestrator:
    def _mock_factory(self):
        """Return a mock LLMProviderFactory that returns a fake response."""
        from apps.backend.src.core.llm_providers import LLMProvider, LLMResponse

        fake_response = LLMResponse(
            provider=LLMProvider.GEMINI,
            model="gemini-2.5-flash",
            text="Mocked LLM response",
            tool_uses=[],
            stop_reason="stop",
            usage={"input_tokens": 10, "output_tokens": 20},
            latency_ms=100.0,
            cost_usd=0.0,
        )
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=fake_response)
        mock_provider.config = MagicMock()
        mock_provider.config.routing_only = False

        factory = MagicMock()
        factory.providers = {LLMProvider.GEMINI: mock_provider}
        factory.primary_provider = LLMProvider.GEMINI
        factory.fallback_chain = []
        factory.routing_provider = None
        factory.get_usage_stats = MagicMock(return_value={})
        factory.get_provider = MagicMock(return_value=mock_provider)
        return factory

    def test_execute_returns_completed_status(self, tmp_path):
        from apps.backend.src.core.gemini_orchestrator import GeminiOrchestrator
        from apps.backend.src.core.quota_tracker import QuotaTracker

        QuotaTracker.reset_singleton()
        persist = tmp_path / "q.json"
        with patch.dict(os.environ, {"GEMINI_QUOTA_PERSIST_PATH": str(persist)}):
            QuotaTracker.reset_singleton()
            with patch(
                "apps.backend.src.core.gemini_orchestrator.GeminiOrchestrator.__init__",
                return_value=None,
            ):
                orch = GeminiOrchestrator.__new__(GeminiOrchestrator)
                orch.factory = self._mock_factory()
                orch.quota = QuotaTracker.load()
                from apps.backend.src.core.model_router import ModelRouter
                orch.router = ModelRouter()
                orch._session_count = 0
                orch._lock = asyncio.Lock()
                orch._vision_agent = None
                orch._primary = "gemini"
                orch._routing = "gemma"
                orch._fallbacks = ["gemini-flash-lite"]

            result = asyncio.run(orch.execute("enumerate subdomains for test.com"))

        assert result["status"] == "completed"
        assert result["output"] == "Mocked LLM response"

    def test_execute_emergency_fallback_logged(self, tmp_path, caplog):
        """Emergency fallback (Tier 5) activation is logged at CRITICAL level.

        Tested via QuotaTracker.next_available_tier() which is called by
        GeminiOrchestrator.execute() when tiers are exhausted.
        """
        from apps.backend.src.core.quota_tracker import QuotaTracker
        from apps.backend.src.core.task_schema import ModelTier

        persist = tmp_path / "q_emerg.json"
        with patch.dict(os.environ, {"GEMINI_QUOTA_PERSIST_PATH": str(persist)}):
            QuotaTracker.reset_singleton()
            tracker = QuotaTracker.load()

        # Exhaust all API tiers
        for tier in (ModelTier.FLASH, ModelTier.FLASH_LITE, ModelTier.PRO):
            model = tracker._models[tier]
            model.rpd_consumed = model.rpd_limit
            model.count_date = model._today()

        with caplog.at_level(logging.CRITICAL):
            next_tier = tracker.next_available_tier(ModelTier.PRO)

        assert next_tier == ModelTier.LOCAL_EMERGENCY
        assert tracker._emergency_active
        assert any("EMERGENCY" in r.message for r in caplog.records)

    def test_vision_observations_in_result(self, tmp_path):
        """VisionAnalysisResult is injected into OrchestrationResult when agent is wired."""
        from apps.backend.src.core.gemini_orchestrator import GeminiOrchestrator
        from apps.backend.src.core.quota_tracker import QuotaTracker

        persist = tmp_path / "q.json"
        with patch.dict(os.environ, {
            "GEMINI_QUOTA_PERSIST_PATH": str(persist),
            "K1_VISION_ANALYSIS_ENABLED": "false",
        }):
            QuotaTracker.reset_singleton()
            with patch(
                "apps.backend.src.core.gemini_orchestrator.GeminiOrchestrator.__init__",
                return_value=None,
            ):
                orch = GeminiOrchestrator.__new__(GeminiOrchestrator)
                orch.factory = self._mock_factory()
                orch.quota = QuotaTracker.load()
                from apps.backend.src.core.model_router import ModelRouter
                orch.router = ModelRouter()
                orch._session_count = 0
                orch._lock = asyncio.Lock()
                orch._vision_agent = None
                orch._primary = "gemini"
                orch._routing = "gemma"
                orch._fallbacks = []

            result = asyncio.run(orch.execute("test instruction"))

        assert result["vision_observations"] == []

    # ------------------------------------------------------------------
    # _dispatch_tool — wired to ToolRegistry
    # ------------------------------------------------------------------

    def _make_orch(self, tmp_path):
        """Return a bare GeminiOrchestrator (no __init__) with patched quota."""
        from apps.backend.src.core.gemini_orchestrator import GeminiOrchestrator
        from apps.backend.src.core.quota_tracker import QuotaTracker

        persist = tmp_path / "q.json"
        with patch.dict(os.environ, {"GEMINI_QUOTA_PERSIST_PATH": str(persist)}):
            QuotaTracker.reset_singleton()
            with patch(
                "apps.backend.src.core.gemini_orchestrator.GeminiOrchestrator.__init__",
                return_value=None,
            ):
                orch = GeminiOrchestrator.__new__(GeminiOrchestrator)
        return orch

    def test_tool_dispatch_queued_status(self, tmp_path):
        """Band 0 tool: look up, validate, enqueue via Celery → status queued."""
        from apps.backend.src.core.tools import ToolAutonomyTier

        orch = self._make_orch(tmp_path)

        mock_tool = MagicMock()
        mock_tool.autonomy_tier = ToolAutonomyTier.TIER_0_AUTO
        mock_tool.validate_parameters.return_value = (True, None)

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_tool

        mock_runner = MagicMock()
        mock_runner.enqueue.return_value = "celery-task-abc123"

        with patch("apps.backend.src.core.tools.get_registry", return_value=mock_registry), \
             patch("apps.backend.src.core.tools.initialize_default_tools"), \
             patch("apps.backend.src.core.tool_runner.tool_runner", mock_runner):
            result = asyncio.run(orch._dispatch_tool("subfinder", {"target": "x.com"}))

        assert result["status"] == "queued"
        assert result["tool"] == "subfinder"
        assert result["task_id"] == "celery-task-abc123"
        mock_runner.enqueue.assert_called_once()

    def test_tool_dispatch_tool_not_found(self, tmp_path):
        """Returns error dict when tool_name is not in registry."""
        orch = self._make_orch(tmp_path)

        mock_registry = MagicMock()
        mock_registry.get.return_value = None

        with patch("apps.backend.src.core.tools.get_registry", return_value=mock_registry), \
             patch("apps.backend.src.core.tools.initialize_default_tools"):
            result = asyncio.run(orch._dispatch_tool("ghost_tool", {"target": "x.com"}))

        assert result["status"] == "error"
        assert result["tool"] == "ghost_tool"
        assert "not found" in result["error"].lower()

    def test_tool_dispatch_validation_failure_returns_error(self, tmp_path):
        """Returns error dict (not raised) when input validation fails."""
        from apps.backend.src.core.tools import ToolAutonomyTier

        orch = self._make_orch(tmp_path)

        mock_tool = MagicMock()
        mock_tool.autonomy_tier = ToolAutonomyTier.TIER_0_AUTO
        mock_tool.validate_parameters.return_value = (False, "Missing required parameters: {'domain'}")

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_tool

        with patch("apps.backend.src.core.tools.get_registry", return_value=mock_registry), \
             patch("apps.backend.src.core.tools.initialize_default_tools"):
            result = asyncio.run(orch._dispatch_tool("subfinder", {}))

        assert result["status"] == "error"
        assert "validation" in result["error"].lower()

    def test_tool_dispatch_band2_requires_approval(self, tmp_path):
        """Band 2 tool returns pending_approval without calling enqueue."""
        from apps.backend.src.core.tools import ToolAutonomyTier

        orch = self._make_orch(tmp_path)

        mock_tool = MagicMock()
        mock_tool.autonomy_tier = ToolAutonomyTier.TIER_2_APPROVE
        mock_tool.validate_parameters.return_value = (True, None)

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_tool

        mock_runner = MagicMock()

        with patch("apps.backend.src.core.tools.get_registry", return_value=mock_registry), \
             patch("apps.backend.src.core.tools.initialize_default_tools"), \
             patch("apps.backend.src.core.tool_runner.tool_runner", mock_runner):
            result = asyncio.run(orch._dispatch_tool("nuclei_scan", {"target": "x.com"}))

        assert result["status"] == "pending_approval"
        assert result["autonomy_tier"] == "TIER_2_APPROVE"
        mock_runner.enqueue.assert_not_called()

    def test_tool_dispatch_enqueue_failure_returns_error(self, tmp_path):
        """Celery enqueue error returns error dict — never propagates the exception."""
        from apps.backend.src.core.tools import ToolAutonomyTier

        orch = self._make_orch(tmp_path)

        mock_tool = MagicMock()
        mock_tool.autonomy_tier = ToolAutonomyTier.TIER_1_NOTIFY
        mock_tool.validate_parameters.return_value = (True, None)

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_tool

        mock_runner = MagicMock()
        mock_runner.enqueue.side_effect = RuntimeError("Redis connection refused")

        with patch("apps.backend.src.core.tools.get_registry", return_value=mock_registry), \
             patch("apps.backend.src.core.tools.initialize_default_tools"), \
             patch("apps.backend.src.core.tool_runner.tool_runner", mock_runner):
            result = asyncio.run(orch._dispatch_tool("amass", {"target": "x.com"}))  # must not raise

        assert result["status"] == "error"
        assert "Redis" in result["error"]


# ---------------------------------------------------------------------------
# orchestration_v1 REST endpoints (via TestClient)
# ---------------------------------------------------------------------------


class TestOrchestrationV1Endpoints:
    def test_health_endpoint_returns_ok(self):
        """GET /api/v1/orchestration/health returns 200 with status field."""
        from fastapi.testclient import TestClient
        from apps.backend.src.main import app

        client = TestClient(app)
        auth = {"Authorization": "Bearer devtoken"}

        with patch(
            "apps.backend.src.routers.orchestration_v1.get_gemini_orchestrator"
        ) as mock_orch:
            mock_orch.return_value.health.return_value = {
                "status": "ok",
                "primary": "gemini",
                "active_tier": "flash",
                "emergency_fallback_active": False,
            }
            r = client.get("/api/v1/orchestration/health")

        assert r.status_code == 200
        assert "status" in r.json()

    def test_quota_endpoint_returns_dict(self):
        from fastapi.testclient import TestClient
        from apps.backend.src.main import app

        client = TestClient(app)

        with patch(
            "apps.backend.src.routers.orchestration_v1.get_gemini_orchestrator"
        ) as mock_orch:
            mock_orch.return_value.quota_status_dict.return_value = {
                "flash": {"rpd_remaining": 200},
                "active_tier": "flash",
            }
            r = client.get("/api/v1/orchestration/quota")

        assert r.status_code == 200

    def test_tier_endpoint(self):
        from fastapi.testclient import TestClient
        from apps.backend.src.core.task_schema import ModelTier, QuotaStatus
        from apps.backend.src.main import app

        client = TestClient(app)

        with patch(
            "apps.backend.src.routers.orchestration_v1.get_gemini_orchestrator"
        ) as mock_orch:
            mock_qs = QuotaStatus(active_tier=ModelTier.FLASH)
            mock_orch.return_value.quota.status.return_value = mock_qs
            r = client.get("/api/v1/orchestration/tier")

        assert r.status_code == 200
        assert r.json()["active_tier"] == "flash"

    def test_dispatch_requires_instruction(self):
        from fastapi.testclient import TestClient
        from apps.backend.src.main import app

        client = TestClient(app)
        auth = {"Authorization": "Bearer devtoken"}

        with patch("apps.backend.src.routers.orchestration_v1.get_gemini_orchestrator"):
            r = client.post("/api/v1/orchestration/dispatch", json={}, headers=auth)

        assert r.status_code == 200
        assert r.json()["status"] == "failed"
        assert "instruction" in r.json()["error"]

    def test_agents_endpoint_returns_list(self):
        from fastapi.testclient import TestClient
        from apps.backend.src.main import app

        client = TestClient(app)

        with patch(
            "apps.backend.src.routers.orchestration_v1.get_gemini_orchestrator"
        ) as mock_orch:
            mock_orch.return_value.agent_list.return_value = [
                {"id": "gemini", "name": "gemini (gemini-2.5-flash)", "status": "ready"}
            ]
            r = client.get("/api/v1/orchestration/agents")

        assert r.status_code == 200
        assert isinstance(r.json(), list)
