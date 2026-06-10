"""Tests for Kai's role-based model router."""
from __future__ import annotations

import logging

import pytest

from apps.backend.src.core.llm_budget_router import (
    AuthenticationError,
    CostCeilingExceededError,
    LLMBudgetRouter,
    ModelConfig,
    ModelUnavailableError,
    ProviderConfigurationError,
    ProviderResponse,
)


class DummyProvider:
    def __init__(self, responses):
        self._responses = list(responses)

    async def chat(self, model, request):
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def router(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-secret")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("KAI_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("KAI_LOCAL_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("KAI_LOCAL_BULK_MODEL", raising=False)
    monkeypatch.delenv("KAI_LOCAL_CODING_MODEL", raising=False)
    monkeypatch.delenv("KAI_LOCAL_PREMIUM_MODEL", raising=False)
    router = LLMBudgetRouter()
    router._tracker._redis = None
    return router


@pytest.mark.asyncio
async def test_role_selection_by_alias(router):
    model = await router.select("report_drafting")
    assert model.route_role == "bulk_reasoning"
    assert model.model == "deepseek/deepseek-v4-flash"


@pytest.mark.asyncio
async def test_openrouter_key_required_only_when_needed(monkeypatch):
    monkeypatch.setenv("KAI_MODEL_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    router = LLMBudgetRouter()
    router._tracker._redis = None
    with pytest.raises(ProviderConfigurationError):
        await router.select("bulk_reasoning")


@pytest.mark.asyncio
async def test_local_provider_does_not_require_openrouter_key(monkeypatch):
    monkeypatch.setenv("KAI_MODEL_PROVIDER", "local")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("KAI_LOCAL_LLM_BASE_URL", "http://127.0.0.1:9000/v1")
    monkeypatch.setenv("KAI_LOCAL_BULK_MODEL", "Qwen/Qwen3-32B")
    router = LLMBudgetRouter()
    router._tracker._redis = None
    router._local_available = True
    model = await router.select("bulk_reasoning")
    assert model.provider == "local"
    assert model.model == "Qwen/Qwen3-32B"


@pytest.mark.asyncio
async def test_auto_prefers_local_when_healthy(monkeypatch):
    monkeypatch.setenv("KAI_MODEL_PROVIDER", "auto")
    monkeypatch.setenv("KAI_LOCAL_LLM_BASE_URL", "http://127.0.0.1:9000/v1")
    monkeypatch.setenv("KAI_LOCAL_BULK_MODEL", "local-bulk-model")
    router = LLMBudgetRouter()
    router._tracker._redis = None
    router._local_available = True
    model = await router.select("bulk_reasoning")
    assert model.provider == "local"
    assert model.model == "local-bulk-model"


@pytest.mark.asyncio
async def test_kimi_free_selected_when_available(router, monkeypatch):
    async def _available(model_id, api_key):
        return model_id == "moonshotai/kimi-k2.6:free"

    monkeypatch.setattr(router._discovery, "is_model_available", _available)
    model = await router.select("free_premium")
    assert model.model == "moonshotai/kimi-k2.6:free"


@pytest.mark.asyncio
async def test_kimi_free_skipped_when_unavailable(router, monkeypatch):
    async def _unavailable(model_id, api_key):
        return False

    monkeypatch.setattr(router._discovery, "is_model_available", _unavailable)
    model = await router.select("free_premium")
    assert model.model == "moonshotai/kimi-k2.5"


@pytest.mark.asyncio
async def test_fallback_from_kimi_free_to_kimi_paid(router, monkeypatch):
    async def _available(model_id, api_key):
        return model_id == "moonshotai/kimi-k2.6:free"

    monkeypatch.setattr(router._discovery, "is_model_available", _available)
    provider = DummyProvider([
        ModelUnavailableError("free unavailable", retryable=True),
        ProviderResponse(provider="openrouter", model="moonshotai/kimi-k2.5", text="ok", usage={"total_tokens": 1000}),
    ])
    router._provider_for = lambda model: provider
    response = await router.complete("free_premium", [{"role": "user", "content": "hello"}])
    assert response.model == "moonshotai/kimi-k2.5"


@pytest.mark.asyncio
async def test_fallback_from_flash_to_pro(router):
    providers = {
        "deepseek/deepseek-v4-flash": DummyProvider([ModelUnavailableError("flash unavailable", retryable=True)]),
        "deepseek/deepseek-v4-pro": DummyProvider([ProviderResponse(provider="openrouter", model="deepseek/deepseek-v4-pro", text="ok", usage={"total_tokens": 1000})]),
    }
    router._provider_for = lambda model: providers[model.model]
    response = await router.complete("bulk_reasoning", [{"role": "user", "content": "reason"}])
    assert response.model == "deepseek/deepseek-v4-pro"


@pytest.mark.asyncio
async def test_qwen_selected_for_coding(router):
    model = await router.select("coding")
    assert model.model == "qwen/qwen3.5-27b"


@pytest.mark.asyncio
async def test_cost_guardrail_blocks_excessive_request(router):
    with pytest.raises(CostCeilingExceededError):
        await router.select("premium_escalation", estimated_tokens_k=5000)


@pytest.mark.asyncio
async def test_failed_discovery_does_not_break_startup(router, monkeypatch):
    async def _empty(model_id, api_key):
        return False

    monkeypatch.setattr(router._discovery, "is_model_available", _empty)
    model = await router.select("free_premium")
    assert model.model == "moonshotai/kimi-k2.5"


@pytest.mark.asyncio
async def test_no_secret_leakage_in_logs(router, monkeypatch, caplog):
    secret = "or-secret"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    router._provider_for = lambda model: DummyProvider([AuthenticationError("bad auth", retryable=False)])
    caplog.set_level(logging.WARNING)
    with pytest.raises(AuthenticationError):
        await router.complete("bulk_reasoning", [{"role": "user", "content": "hi"}])
    assert secret not in caplog.text


@pytest.mark.asyncio
async def test_record_usage_decrements_budget(router):
    model = ModelConfig(
        "openrouter",
        "qwen/qwen3.5-27b",
        "OPENROUTER_API_KEY",
        tier=1,
        cost_per_1k=0.0003,
    )
    before = router.budget_report()["openrouter"]["spent"]
    router.record_usage(model, tokens_used_k=10.0)
    after = router.budget_report()["openrouter"]["spent"]
    assert round(after - before, 6) == 0.003
