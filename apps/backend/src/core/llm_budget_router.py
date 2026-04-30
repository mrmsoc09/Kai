"""
LLM Budget Router — Intelligent model selection with hard monthly spend limits.

Tiers (cost ascending):
  0 — Local Ollama:       free  (maximize usage)
  1 — OpenRouter:         $100/mo budget (primary remote)
  2 — HuggingFace:        $50/mo budget  (embeddings + specialized)
  3 — Gemini free tier:   $0/mo (tracked by quota_tracker.py)
  4 — Anthropic / OpenAI: $25/mo each (LAST RESORT)

Task routing is defined in config/registry/llm_task_routing.yaml.
Monthly spend is tracked in Redis, reset on the 1st of each month.

Usage::

    router = get_budget_router()
    model_cfg = await router.select(task_type="osint_parse", complexity="low")
    # model_cfg.provider, model_cfg.model, model_cfg.api_key_env
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_TASK_ROUTING_PATH = Path(__file__).parents[4] / "config" / "registry" / "llm_task_routing.yaml"

# ---------------------------------------------------------------------------
# Budget configuration (monthly $ limits)
# ---------------------------------------------------------------------------

_BUDGETS: dict[str, float] = {
    "anthropic":   25.0,
    "openai":      25.0,
    "openrouter":  100.0,
    "huggingface": 50.0,
    "gemini":      0.0,   # free tier — quota tracked separately
    "ollama":      0.0,   # local — no cost
}

# Approximate cost per 1K tokens (input+output blended) in USD
_COST_PER_1K_TOKENS: dict[str, float] = {
    "anthropic/claude-sonnet-4-6":          0.015,
    "openai/gpt-4.1":                       0.010,
    "openrouter/auto":                      0.002,   # auto-router average estimate
    "openrouter/moonshotai/kimi-k2":        0.0015,
    "openrouter/qwen/qwen3-235b-a22b":      0.0002,
    "openrouter/deepseek/deepseek-r1":      0.0004,
    "openrouter/thudm/glm-4-9b-chat":       0.0001,
    "openrouter/mistralai/mistral-large":   0.003,
    "openrouter/google/gemini-2.5-flash":   0.0002,
    "openrouter/meta-llama/llama-3.3-70b":  0.0004,
    "huggingface/BAAI/bge-m3":             0.0001,
    "gemini/gemini-2.5-flash":              0.0,
    "gemini/gemini-2.5-pro":               0.0,
    "ollama/qwen2.5-coder:7b":             0.0,
    "ollama/llama3.1:8b":                  0.0,
    "ollama/gemma:7b":                     0.0,
}


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    provider: str
    model: str
    api_key_env: str
    tier: int
    supports_tool_calling: bool = True
    supports_structured_output: bool = True
    context_window: int = 32000
    cost_per_1k: float = 0.001


_MODEL_REGISTRY: list[ModelConfig] = [
    # Tier 0 — Local
    ModelConfig("ollama", "qwen2.5-coder:7b",  "",               tier=0, supports_tool_calling=False, cost_per_1k=0.0),
    ModelConfig("ollama", "llama3.1:8b",        "",               tier=0, supports_tool_calling=False, cost_per_1k=0.0),
    ModelConfig("ollama", "gemma:7b",           "",               tier=0, supports_tool_calling=False, cost_per_1k=0.0),
    # Tier 1 — OpenRouter (cheap open-source first)
    ModelConfig("openrouter", "qwen/qwen3-235b-a22b",      "OPENROUTER_API_KEY", tier=1, context_window=131072, cost_per_1k=0.0002),
    ModelConfig("openrouter", "thudm/glm-4-9b-chat",       "OPENROUTER_API_KEY", tier=1, cost_per_1k=0.0001),
    ModelConfig("openrouter", "deepseek/deepseek-r1",       "OPENROUTER_API_KEY", tier=1, context_window=65536, cost_per_1k=0.0004),
    ModelConfig("openrouter", "moonshotai/kimi-k2",         "OPENROUTER_API_KEY", tier=1, context_window=131072, cost_per_1k=0.0015),
    ModelConfig("openrouter", "meta-llama/llama-3.3-70b-instruct", "OPENROUTER_API_KEY", tier=1, cost_per_1k=0.0004),
    ModelConfig("openrouter", "mistralai/mistral-large",    "OPENROUTER_API_KEY", tier=1, cost_per_1k=0.003),
    ModelConfig("openrouter", "auto",                       "OPENROUTER_API_KEY", tier=1, cost_per_1k=0.002),  # OpenRouter auto-router
    # Tier 2 — HuggingFace
    ModelConfig("huggingface", "BAAI/bge-m3",              "HUGGINGFACE_TOKEN", tier=2, supports_tool_calling=False, cost_per_1k=0.0001),
    ModelConfig("huggingface", "sentence-transformers/all-MiniLM-L6-v2", "HUGGINGFACE_TOKEN", tier=2, supports_tool_calling=False, cost_per_1k=0.0),
    # Tier 3 — Gemini free
    ModelConfig("gemini", "gemini-2.5-flash",  "GEMINI_API_KEY", tier=3, context_window=1000000, cost_per_1k=0.0),
    ModelConfig("gemini", "gemini-2.5-pro",    "GEMINI_API_KEY", tier=3, context_window=1000000, cost_per_1k=0.0),
    # Tier 4 — Expensive (last resort)
    ModelConfig("anthropic", "claude-sonnet-4-6",          "ANTHROPIC_API_KEY", tier=4, context_window=200000, cost_per_1k=0.015),
    ModelConfig("openai",    "gpt-4.1",                    "OPENAI_API_KEY",    tier=4, context_window=128000, cost_per_1k=0.010),
]

# Task → (preferred_tier, required_capabilities)
_DEFAULT_TASK_ROUTING: dict[str, dict[str, Any]] = {
    "osint_parse":          {"tier": 0, "fallback": 1, "tool_calling": False},
    "tool_selection":       {"tier": 0, "fallback": 1, "tool_calling": False},
    "log_summarization":    {"tier": 0, "fallback": 1, "tool_calling": False},
    "classification":       {"tier": 0, "fallback": 1, "tool_calling": False},
    "scope_validation":     {"tier": 0, "fallback": 1, "tool_calling": False},
    "mission_planning":     {"tier": 1, "fallback": 3, "tool_calling": True},
    "vuln_correlation":     {"tier": 1, "fallback": 3, "tool_calling": True},
    "report_writing":       {"tier": 1, "fallback": 3, "tool_calling": False},
    "exploit_validation":   {"tier": 1, "fallback": 3, "tool_calling": True},
    "stakeholder_email":    {"tier": 1, "fallback": 4, "tool_calling": False},
    "embedding":            {"tier": 2, "fallback": 3, "tool_calling": False},
    "cve_classification":   {"tier": 2, "fallback": 1, "tool_calling": False},
    "screenshot_analysis":  {"tier": 3, "fallback": 4, "tool_calling": False},
    "large_doc_summary":    {"tier": 3, "fallback": 1, "tool_calling": False},
    "final_report_review":  {"tier": 4, "fallback": None, "tool_calling": False},
    "novel_vuln_analysis":  {"tier": 4, "fallback": 3, "tool_calling": True},
}


# ---------------------------------------------------------------------------
# Budget tracker (Redis-backed, monthly reset)
# ---------------------------------------------------------------------------

class _BudgetTracker:
    def __init__(self) -> None:
        self._redis: Any = None
        self._local_spend: dict[str, float] = {p: 0.0 for p in _BUDGETS}
        self._init_redis()

    def _init_redis(self) -> None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            import redis
            self._redis = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=1)
            self._redis.ping()
        except Exception:
            self._redis = None

    def _month_key(self, provider: str) -> str:
        month = time.strftime("%Y-%m")
        return f"k1:llm_spend:{provider}:{month}"

    def get_spend(self, provider: str) -> float:
        if self._redis:
            try:
                val = self._redis.get(self._month_key(provider))
                return float(val) if val else 0.0
            except Exception:
                pass
        return self._local_spend.get(provider, 0.0)

    def record_spend(self, provider: str, tokens_1k: float, cost_per_1k: float) -> float:
        cost = tokens_1k * cost_per_1k
        new_total: float
        if self._redis:
            try:
                key = self._month_key(provider)
                new_val = self._redis.incrbyfloat(key, cost)
                self._redis.expire(key, 86400 * 35)
                new_total = float(new_val)
            except Exception:
                self._local_spend[provider] = self._local_spend.get(provider, 0.0) + cost
                new_total = self._local_spend[provider]
        else:
            self._local_spend[provider] = self._local_spend.get(provider, 0.0) + cost
            new_total = self._local_spend[provider]

        # Budget alerting — fire after whichever storage branch ran
        budget = _BUDGETS.get(provider, 0.0)
        if budget > 0:
            new_pct = (new_total / budget) * 100
            if new_pct >= 95:
                logger.error(
                    "BUDGET ALERT: %s at %.1f%% of monthly cap ($%.2f/$%.2f)",
                    provider, new_pct, new_total, budget,
                )
            elif new_pct >= 80:
                logger.warning(
                    "BUDGET ALERT: %s at %.1f%% of monthly cap ($%.2f/$%.2f)",
                    provider, new_pct, new_total, budget,
                )

        return new_total

    def can_afford(self, provider: str, estimated_cost: float) -> bool:
        budget = _BUDGETS.get(provider, 0.0)
        if budget == 0.0:
            return True
        spent = self.get_spend(provider)
        return (spent + estimated_cost) < budget * 0.95  # 5% reserve

    def budget_report(self) -> dict[str, dict[str, float]]:
        return {
            p: {"budget": _BUDGETS[p], "spent": self.get_spend(p),
                "remaining": max(0, _BUDGETS[p] - self.get_spend(p))}
            for p in _BUDGETS
        }


# ---------------------------------------------------------------------------
# Budget router
# ---------------------------------------------------------------------------

class LLMBudgetRouter:
    """
    Select the most cost-effective model for a given task type.

    Respects monthly budget caps per provider. Prefers local/cheap models.
    Falls back up tiers only when lower tiers are unavailable or over budget.
    """

    def __init__(self) -> None:
        self._tracker = _BudgetTracker()
        self._task_routing = self._load_task_routing()
        self._ollama_available: bool | None = None

    def _load_task_routing(self) -> dict[str, Any]:
        if _TASK_ROUTING_PATH.exists():
            with _TASK_ROUTING_PATH.open() as f:
                data = yaml.safe_load(f) or {}
                return data.get("task_routing", _DEFAULT_TASK_ROUTING)
        return _DEFAULT_TASK_ROUTING

    async def select(
        self,
        task_type: str,
        complexity: str = "medium",
        require_tool_calling: bool = False,
        estimated_tokens_k: float = 2.0,
    ) -> ModelConfig:
        """
        Return the best ModelConfig for the task.

        Args:
            task_type: Key from task_routing config (e.g. "osint_parse")
            complexity: "low"|"medium"|"high" — bumps tier for high complexity
            require_tool_calling: Force a model that supports tool_calling
            estimated_tokens_k: Expected token usage in thousands (for budget check)
        """
        routing = self._task_routing.get(task_type, {"tier": 1, "fallback": 3, "tool_calling": False})
        base_tier      = routing.get("tier", 1)
        preferred_tier = base_tier
        fallback_tier  = routing.get("fallback", 3)
        needs_tools    = require_tool_calling or routing.get("tool_calling", False)
        strict_task    = fallback_tier is None  # null fallback → no silent escalation

        if complexity == "high":
            preferred_tier = preferred_tier + 1
            # FIX 2: complexity bump must not cross into tier 4 unless the task
            # explicitly targets tier 4 or has an explicit tier-4 fallback
            task_allows_tier4 = (fallback_tier == 4) or (base_tier == 4)
            if preferred_tier == 4 and not task_allows_tier4:
                preferred_tier = 3  # Cap complexity bump at tier 3

        # Check Ollama availability once per session
        if self._ollama_available is None:
            self._ollama_available = await self._check_ollama()

        tiers_to_try: list[int] = [preferred_tier]
        if fallback_tier is not None and fallback_tier != preferred_tier:
            tiers_to_try.append(fallback_tier)

        if not strict_task:
            # Non-strict tasks get universal escalation tiers as safety net
            for t in [1, 2, 3, 4]:
                if t not in tiers_to_try:
                    tiers_to_try.append(t)
        # FIX 3: strict task (null fallback) — only try the designated tier, no escalation

        for tier in tiers_to_try:
            candidates = [
                m for m in _MODEL_REGISTRY
                if m.tier == tier
                and (not needs_tools or m.supports_tool_calling)
                and (tier != 0 or self._ollama_available)
            ]
            if not candidates:
                continue

            for model in candidates:
                est_cost = estimated_tokens_k * model.cost_per_1k
                if self._tracker.can_afford(model.provider, est_cost):
                    logger.debug(
                        "LLMBudgetRouter: task=%s tier=%d model=%s/%s est_cost=$%.4f",
                        task_type, tier, model.provider, model.model, est_cost
                    )
                    return model

            logger.warning("LLMBudgetRouter: tier %d over budget — trying next tier", tier)

        # FIX 3: strict task (null fallback) must raise immediately — do not silently
        # route to Gemini. A task flagged strict requires its designated tier or failure.
        if strict_task:
            raise RuntimeError(
                "LLMBudgetRouter: no available model for task %s (strict task — fallback=null)" % task_type
            )

        # Ultimate fallback — Gemini free tier never runs out of "budget"
        gemini = next((m for m in _MODEL_REGISTRY if m.provider == "gemini"), None)
        if gemini:
            logger.warning("LLMBudgetRouter: all budgets exhausted — falling back to Gemini free tier")
            return gemini

        raise RuntimeError("LLMBudgetRouter: no available model for task %s" % task_type)

    def record_usage(self, model: ModelConfig, tokens_used_k: float) -> None:
        """Call after inference to deduct from monthly budget."""
        self._tracker.record_spend(model.provider, tokens_used_k, model.cost_per_1k)

    def budget_report(self) -> dict[str, dict[str, float]]:
        return self._tracker.budget_report()

    async def _check_ollama(self) -> bool:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get("http://127.0.0.1:11434/api/tags")
                return r.status_code == 200
        except Exception:
            logger.warning("Ollama not reachable — Tier 0 models unavailable")
            return False


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_router: LLMBudgetRouter | None = None


def get_budget_router() -> LLMBudgetRouter:
    global _router
    if _router is None:
        _router = LLMBudgetRouter()
    return _router
