"""Tests for llm_budget_router — tier selection, budget gates, Ollama fallback."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from apps.backend.src.core.llm_budget_router import (
    LLMBudgetRouter,
    ModelConfig,
    _BUDGETS,
    _MODEL_REGISTRY,
    _DEFAULT_TASK_ROUTING,
)


@pytest.fixture
def router():
    r = LLMBudgetRouter()
    r._ollama_available = True  # assume Ollama up for most tests
    r._tracker._redis = None    # force in-process spend tracking
    return r


# 1. Tier 0 selected for osint_parse when Ollama available
@pytest.mark.asyncio
async def test_tier0_selected_for_osint_parse(router):
    model = await router.select("osint_parse")
    assert model.tier == 0
    assert model.provider == "ollama"


# 2. Falls back to tier 1 when Ollama unavailable
@pytest.mark.asyncio
async def test_fallback_to_tier1_when_ollama_down(router):
    router._ollama_available = False
    model = await router.select("osint_parse")
    assert model.tier >= 1


# 3. Tier 4 selected for final_report_review
@pytest.mark.asyncio
async def test_tier4_for_final_report(router):
    model = await router.select("final_report_review")
    assert model.tier == 4
    assert model.provider in ("anthropic", "openai")


# 4. Budget gate blocks expensive provider over limit
@pytest.mark.asyncio
async def test_budget_gate_blocks_overspent_provider(router):
    # Simulate Anthropic over budget
    router._tracker._local_spend["anthropic"] = 24.99  # > $25 * 0.95 = $23.75
    model = await router.select("final_report_review")
    # Should NOT be anthropic (over budget)
    assert model.provider != "anthropic"


# 5. record_usage decrements budget
def test_record_usage_decrements_budget(router):
    model = ModelConfig("openrouter", "qwen/qwen3-235b-a22b", "OPENROUTER_API_KEY",
                        tier=1, cost_per_1k=0.0002)
    before = router._tracker.get_spend("openrouter")
    router.record_usage(model, tokens_used_k=10.0)
    after = router._tracker.get_spend("openrouter")
    assert abs((after - before) - 0.002) < 1e-6


# 6. require_tool_calling excludes ollama (tool_calling=False)
@pytest.mark.asyncio
async def test_tool_calling_excludes_ollama(router):
    model = await router.select("mission_planning", require_tool_calling=True)
    assert model.supports_tool_calling is True
    assert model.provider != "ollama"


# 7. high complexity bumps tier
@pytest.mark.asyncio
async def test_high_complexity_bumps_tier(router):
    model_low  = await router.select("osint_parse", complexity="low")
    model_high = await router.select("osint_parse", complexity="high")
    assert model_high.tier >= model_low.tier


# 8. budget_report returns all providers
def test_budget_report_completeness(router):
    report = router.budget_report()
    for provider in _BUDGETS:
        assert provider in report
        assert "budget" in report[provider]
        assert "spent" in report[provider]
        assert "remaining" in report[provider]


# 9. All task types in _DEFAULT_TASK_ROUTING have valid tiers
def test_all_default_tasks_have_valid_tiers():
    for task, config in _DEFAULT_TASK_ROUTING.items():
        tier = config["tier"]
        assert 0 <= tier <= 4, f"Task {task} has invalid tier {tier}"


# 10. Model registry has at least one model per tier 0-3
def test_model_registry_coverage():
    tiers_covered = {m.tier for m in _MODEL_REGISTRY}
    for required_tier in [0, 1, 2, 3]:
        assert required_tier in tiers_covered, f"Tier {required_tier} missing from model registry"
