"""
Kai role-based model router with provider fallbacks and cost guardrails.

Preserves the existing ``LLMBudgetRouter.select()`` surface while replacing the
internal routing strategy with role-based provider/model selection.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import yaml

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parents[4]
_MODEL_ROUTING_PATH = _REPO_ROOT / "config" / "model_routing.yaml"
_DISCOVERY_CACHE_PATH = _REPO_ROOT / "runtime" / "cache" / "openrouter_models.json"

_PROVIDER_BUDGETS: dict[str, float] = {
    "local": 0.0,
    "openrouter": 100.0,
    "openai": 25.0,
}
_BUDGETS = _PROVIDER_BUDGETS

_PROVIDER_API_KEYS: dict[str, str] = {
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
}

_LOCAL_ALIAS_ENVS: dict[str, str] = {
    "local.bulk_reasoning": "KAI_LOCAL_BULK_MODEL",
    "local.coding": "KAI_LOCAL_CODING_MODEL",
    "local.premium": "KAI_LOCAL_PREMIUM_MODEL",
}

_ROUTE_OVERRIDE_ENVS: dict[str, str] = {
    "bulk_reasoning": "KAI_MODEL_ROUTE_BULK",
    "coding": "KAI_MODEL_ROUTE_CODING",
    "premium_escalation": "KAI_MODEL_ROUTE_PREMIUM",
    "free_premium": "KAI_MODEL_ROUTE_FREE_PREMIUM",
}

_MODEL_COSTS_PER_1K: dict[str, float] = {
    "openrouter/deepseek/deepseek-v4-flash": 0.0002,
    "openrouter/deepseek/deepseek-v4-pro": 0.0008,
    "openrouter/qwen/qwen3.5-27b": 0.0003,
    "openrouter/moonshotai/kimi-k2.5": 0.0015,
    "openrouter/moonshotai/kimi-k2.6:free": 0.0,
    "openai/gpt-4.1": 0.0100,
}

_PROVIDER_TIER: dict[str, int] = {
    "local": 0,
    "openrouter": 1,
    "openai": 4,
}

_DEFAULT_MODEL_ROUTING: dict[str, Any] = {
    "provider_mode": "auto",
    "discovery": {"openrouter_enabled": True, "ttl_seconds": 3600},
    "roles": {
        "bulk_reasoning": {
            "preferred": [
                {"provider": "openrouter", "model": "deepseek/deepseek-v4-flash"},
                {"provider": "openrouter", "model": "deepseek/deepseek-v4-pro"},
                {"provider": "local", "alias": "local.bulk_reasoning"},
            ],
            "max_input_tokens": 32768,
            "max_output_tokens": 4096,
            "temperature": 0.2,
            "top_p": 0.9,
            "cost_ceiling_usd": 0.25,
        },
        "coding": {
            "preferred": [
                {"provider": "openrouter", "model": "qwen/qwen3.5-27b"},
                {"provider": "openrouter", "model": "deepseek/deepseek-v4-pro"},
                {"provider": "local", "alias": "local.coding"},
            ],
            "max_input_tokens": 65536,
            "max_output_tokens": 8192,
            "temperature": 0.15,
            "top_p": 0.9,
            "cost_ceiling_usd": 0.50,
        },
        "free_premium": {
            "preferred": [
                {
                    "provider": "openrouter",
                    "model": "moonshotai/kimi-k2.6:free",
                    "require_discovery_available": True,
                },
                {"provider": "openrouter", "model": "moonshotai/kimi-k2.5"},
                {"provider": "openrouter", "model": "deepseek/deepseek-v4-pro"},
                {"provider": "local", "alias": "local.premium"},
            ],
            "max_input_tokens": 65536,
            "max_output_tokens": 8192,
            "temperature": 0.2,
            "top_p": 0.9,
            "cost_ceiling_usd": 0.75,
        },
        "premium_escalation": {
            "preferred": [
                {"provider": "openrouter", "model": "moonshotai/kimi-k2.5"},
                {"provider": "openrouter", "model": "deepseek/deepseek-v4-pro"},
                {"provider": "local", "alias": "local.premium"},
                {"provider": "openai", "model": "gpt-4.1"},
            ],
            "max_input_tokens": 65536,
            "max_output_tokens": 12288,
            "temperature": 0.2,
            "top_p": 0.9,
            "cost_ceiling_usd": 1.50,
        },
    },
    "aliases": {
        "report_drafting": "bulk_reasoning",
        "triage": "bulk_reasoning",
        "scheduler": "bulk_reasoning",
        "recon_synthesis": "bulk_reasoning",
        "case_analysis": "bulk_reasoning",
        "code_generation": "coding",
        "test_generation": "coding",
        "refactor": "coding",
        "docker_generation": "coding",
        "kubernetes_generation": "coding",
        "parser_generation": "coding",
        "hard_failure_escalation": "premium_escalation",
        "architecture_redesign": "premium_escalation",
        "osint_parse": "bulk_reasoning",
        "tool_selection": "bulk_reasoning",
        "log_summarization": "bulk_reasoning",
        "classification": "bulk_reasoning",
        "scope_validation": "bulk_reasoning",
        "mission_planning": "bulk_reasoning",
        "vuln_correlation": "bulk_reasoning",
        "report_writing": "report_drafting",
        "exploit_validation": "premium_escalation",
        "stakeholder_email": "report_drafting",
        "script_generation": "coding",
        "cve_lookup": "bulk_reasoning",
        "port_scan_analysis": "bulk_reasoning",
        "dns_analysis": "bulk_reasoning",
        "certificate_analysis": "bulk_reasoning",
        "credentials_analysis": "bulk_reasoning",
        "subdomain_analysis": "bulk_reasoning",
        "web_tech_fingerprinting": "bulk_reasoning",
        "embedding": "bulk_reasoning",
        "cve_classification": "bulk_reasoning",
        "code_patch_analysis": "coding",
        "screenshot_analysis": "premium_escalation",
        "large_doc_summary": "premium_escalation",
        "final_report_review": "premium_escalation",
        "novel_vuln_analysis": "premium_escalation",
    },
}

_DEFAULT_TASK_ROUTING: dict[str, dict[str, Any]] = {
    task: {"role": role, "tier": 1 if role == "bulk_reasoning" else 3 if role == "premium_escalation" else 1}
    for task, role in _DEFAULT_MODEL_ROUTING["aliases"].items()
}


class ModelRoutingError(RuntimeError):
    """Base error for routing/provider failures."""


class ProviderConfigurationError(ModelRoutingError):
    """Raised when a provider is selected without required configuration."""


class CostCeilingExceededError(ModelRoutingError):
    """Raised when every route candidate exceeds the configured ceiling."""


class ProviderRequestError(ModelRoutingError):
    """Structured provider request error."""

    def __init__(self, message: str, *, retryable: bool, status_code: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


class ModelUnavailableError(ProviderRequestError):
    """Model is unavailable."""


class RateLimitError(ProviderRequestError):
    """Provider returned a rate-limit response."""


class AuthenticationError(ProviderRequestError):
    """Provider authentication failed."""


class RequestTimeoutError(ProviderRequestError):
    """Provider request timed out."""


@dataclass(frozen=True)
class RouteTarget:
    provider: str
    model: str | None = None
    alias: str | None = None
    require_discovery_available: bool = False
    enabled: bool = True


@dataclass(frozen=True)
class RoutePolicy:
    role: str
    preferred: list[RouteTarget]
    max_input_tokens: int = 32768
    max_output_tokens: int = 4096
    temperature: float = 0.2
    top_p: float = 0.9
    reasoning_effort: str | None = None
    cost_ceiling_usd: float | None = None
    enabled: bool = True


@dataclass
class ModelConfig:
    provider: str
    model: str
    api_key_env: str
    tier: int
    supports_tool_calling: bool = True
    supports_structured_output: bool = True
    context_window: int = 32768
    cost_per_1k: float = 0.0
    route_role: str = ""
    fallback_index: int = 0
    max_input_tokens: int = 32768
    max_output_tokens: int = 4096
    temperature: float = 0.2
    top_p: float = 0.9
    reasoning_effort: str | None = None
    cost_ceiling_usd: float | None = None
    local_base_url: str | None = None
    local_alias: str | None = None
    require_discovery_available: bool = False
    estimated_cost_usd: float | None = None


@dataclass(frozen=True)
class ProviderRequest:
    messages: list[dict[str, Any]]
    role: str
    max_output_tokens: int
    temperature: float
    top_p: float
    reasoning_effort: str | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 2


@dataclass
class ProviderResponse:
    provider: str
    model: str
    text: str
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    estimated_cost_usd: float | None = None


_MODEL_REGISTRY: list[ModelConfig] = [
    ModelConfig("local", "local.bulk_reasoning", "", tier=0, route_role="bulk_reasoning"),
    ModelConfig("openrouter", "deepseek/deepseek-v4-flash", "OPENROUTER_API_KEY", tier=1, route_role="bulk_reasoning", cost_per_1k=_MODEL_COSTS_PER_1K["openrouter/deepseek/deepseek-v4-flash"]),
    ModelConfig("openrouter", "qwen/qwen3.5-27b", "OPENROUTER_API_KEY", tier=1, route_role="coding", cost_per_1k=_MODEL_COSTS_PER_1K["openrouter/qwen/qwen3.5-27b"]),
    ModelConfig("openrouter", "moonshotai/kimi-k2.6:free", "OPENROUTER_API_KEY", tier=2, route_role="free_premium", cost_per_1k=_MODEL_COSTS_PER_1K["openrouter/moonshotai/kimi-k2.6:free"]),
    ModelConfig("openrouter", "moonshotai/kimi-k2.5", "OPENROUTER_API_KEY", tier=3, route_role="premium_escalation", cost_per_1k=_MODEL_COSTS_PER_1K["openrouter/moonshotai/kimi-k2.5"]),
    ModelConfig("openai", "gpt-4.1", "OPENAI_API_KEY", tier=4, route_role="premium_escalation", cost_per_1k=_MODEL_COSTS_PER_1K["openai/gpt-4.1"]),
]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _trimmed_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _provider_key(provider: str, model: str) -> str:
    return f"{provider}/{model}" if provider != "local" else f"local/{model}"


class _BudgetTracker:
    def __init__(self) -> None:
        self._redis: Any = None
        self._local_spend: dict[str, float] = {p: 0.0 for p in _PROVIDER_BUDGETS}
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
        return f"k1:llm_spend:{provider}:{time.strftime('%Y-%m')}"

    def get_spend(self, provider: str) -> float:
        if self._redis is not None:
            try:
                value = self._redis.get(self._month_key(provider))
                return float(value) if value else 0.0
            except Exception:
                pass
        return self._local_spend.get(provider, 0.0)

    def record_spend(self, provider: str, tokens_1k: float, cost_per_1k: float) -> float:
        cost = tokens_1k * cost_per_1k
        if self._redis is not None:
            try:
                key = self._month_key(provider)
                value = self._redis.incrbyfloat(key, cost)
                self._redis.expire(key, 86400 * 35)
                return float(value)
            except Exception:
                pass
        self._local_spend[provider] = self._local_spend.get(provider, 0.0) + cost
        return self._local_spend[provider]

    def can_afford(self, provider: str, estimated_cost: float) -> bool:
        budget = _PROVIDER_BUDGETS.get(provider, 0.0)
        if budget == 0.0:
            return True
        return (self.get_spend(provider) + estimated_cost) < budget * 0.95

    def budget_report(self) -> dict[str, dict[str, float]]:
        report: dict[str, dict[str, float]] = {}
        for provider, budget in _PROVIDER_BUDGETS.items():
            spent = self.get_spend(provider)
            report[provider] = {
                "budget": budget,
                "spent": spent,
                "remaining": max(0.0, budget - spent),
            }
        return report


class OpenRouterDiscovery:
    def __init__(self, *, enabled: bool, ttl_seconds: int, cache_path: Path | None = None) -> None:
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds
        self.cache_path = cache_path or _DISCOVERY_CACHE_PATH

    def _read_cache(self) -> tuple[float, set[str]]:
        if not self.cache_path.exists():
            return 0.0, set()
        try:
            payload = json.loads(self.cache_path.read_text())
            fetched_at = float(payload.get("fetched_at", 0.0))
            model_ids = {str(item) for item in payload.get("model_ids", [])}
            return fetched_at, model_ids
        except Exception:
            return 0.0, set()

    def _write_cache(self, model_ids: set[str]) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps({
                "fetched_at": time.time(),
                "model_ids": sorted(model_ids),
            }))
        except Exception:
            logger.debug("OpenRouter discovery cache write failed", exc_info=True)

    async def available_models(self, api_key: str | None) -> set[str]:
        fetched_at, cached = self._read_cache()
        if cached and (time.time() - fetched_at) < self.ttl_seconds:
            return cached
        if not self.enabled:
            return cached

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
            response.raise_for_status()
            data = response.json().get("data", [])
            model_ids = {str(item.get("id", "")).strip() for item in data if item.get("id")}
            self._write_cache(model_ids)
            return model_ids
        except Exception as exc:
            logger.warning("OpenRouter model discovery failed; static routing remains active: %s", exc)
            return cached

    async def is_model_available(self, model_id: str, api_key: str | None) -> bool:
        return model_id in await self.available_models(api_key)


class OpenAICompatibleProvider:
    provider_name = "openai-compatible"

    def __init__(self, *, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def chat(self, model: ModelConfig, request: ProviderRequest) -> ProviderResponse:
        payload: dict[str, Any] = {
            "model": model.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_output_tokens,
        }
        if request.reasoning_effort:
            payload["reasoning_effort"] = request.reasoning_effort

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}/chat/completions"
        last_error: ProviderRequestError | None = None
        for attempt in range(request.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=payload)
                if response.status_code in {401, 403}:
                    raise AuthenticationError("provider authentication failed", retryable=False, status_code=response.status_code)
                if response.status_code == 404:
                    raise ModelUnavailableError("model unavailable", retryable=True, status_code=404)
                if response.status_code == 429:
                    raise RateLimitError("rate limited", retryable=True, status_code=429)
                if response.status_code >= 500:
                    raise ProviderRequestError("provider internal error", retryable=True, status_code=response.status_code)
                response.raise_for_status()
                raw = response.json()
                usage = raw.get("usage") or {}
                choices = raw.get("choices") or []
                message = choices[0].get("message", {}) if choices else {}
                content = message.get("content", "")
                if isinstance(content, list):
                    content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
                usage_dict = {
                    "input_tokens": int(usage.get("prompt_tokens", 0) or 0),
                    "output_tokens": int(usage.get("completion_tokens", 0) or 0),
                    "total_tokens": int(usage.get("total_tokens", 0) or 0),
                }
                total_tokens_k = (usage_dict["total_tokens"] / 1000.0) if usage_dict["total_tokens"] else 0.0
                estimated_cost = round(total_tokens_k * model.cost_per_1k, 6) if model.cost_per_1k else 0.0
                return ProviderResponse(
                    provider=model.provider,
                    model=model.model,
                    text=str(content),
                    usage=usage_dict,
                    raw=raw,
                    estimated_cost_usd=estimated_cost,
                )
            except httpx.TimeoutException as exc:
                last_error = RequestTimeoutError(str(exc), retryable=True)
            except ProviderRequestError as exc:
                last_error = exc
            except Exception as exc:  # pragma: no cover - transport variance
                last_error = ProviderRequestError(str(exc), retryable=True)
            if last_error is not None and not last_error.retryable:
                break
            if attempt < request.max_retries:
                await asyncio.sleep(min(0.25 * (attempt + 1), 1.0))

        assert last_error is not None
        raise last_error


class OpenRouterProvider(OpenAICompatibleProvider):
    provider_name = "openrouter"

    def __init__(self, api_key: str) -> None:
        super().__init__(base_url="https://openrouter.ai/api/v1", api_key=api_key)


class LocalOpenAICompatibleProvider(OpenAICompatibleProvider):
    provider_name = "local"

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        super().__init__(base_url=base_url, api_key=api_key)


class DirectOpenAIProvider(OpenAICompatibleProvider):
    provider_name = "openai"

    def __init__(self, api_key: str) -> None:
        super().__init__(base_url="https://api.openai.com/v1", api_key=api_key)


class LLMBudgetRouter:
    """Role-based router with provider fallback and budget tracking."""

    def __init__(self, *, config_path: Path | None = None) -> None:
        self.config_path = config_path or _MODEL_ROUTING_PATH
        self._tracker = _BudgetTracker()
        self._local_available: bool | None = None
        self._providers: dict[str, Any] = {}
        self._config = self._load_config()
        self._roles = self._parse_roles(self._config.get("roles", {}))
        self._aliases = {k.lower(): v for k, v in self._config.get("aliases", {}).items()}
        discovery = self._config.get("discovery", {})
        self._discovery = OpenRouterDiscovery(
            enabled=bool(discovery.get("openrouter_enabled", True)),
            ttl_seconds=int(discovery.get("ttl_seconds", 3600)),
        )
        self._task_routing = self._build_task_routing()

    def _load_config(self) -> dict[str, Any]:
        if self.config_path.exists():
            with self.config_path.open() as handle:
                raw = yaml.safe_load(handle) or {}
            loaded = raw.get("model_routing", raw)
        else:
            loaded = _DEFAULT_MODEL_ROUTING
        merged = json.loads(json.dumps(_DEFAULT_MODEL_ROUTING))
        merged.update({k: v for k, v in loaded.items() if k != "roles" and k != "aliases"})
        merged["roles"] = {**_DEFAULT_MODEL_ROUTING["roles"], **loaded.get("roles", {})}
        merged["aliases"] = {**_DEFAULT_MODEL_ROUTING["aliases"], **loaded.get("aliases", {})}
        return merged

    def _parse_roles(self, raw_roles: dict[str, Any]) -> dict[str, RoutePolicy]:
        parsed: dict[str, RoutePolicy] = {}
        for role, raw in raw_roles.items():
            preferred = [
                RouteTarget(
                    provider=str(item["provider"]).strip().lower(),
                    model=item.get("model"),
                    alias=item.get("alias"),
                    require_discovery_available=bool(item.get("require_discovery_available", False)),
                    enabled=bool(item.get("enabled", True)),
                )
                for item in raw.get("preferred", [])
            ]
            parsed[role] = RoutePolicy(
                role=role,
                preferred=preferred,
                max_input_tokens=int(raw.get("max_input_tokens", 32768)),
                max_output_tokens=int(raw.get("max_output_tokens", 4096)),
                temperature=float(raw.get("temperature", 0.2)),
                top_p=float(raw.get("top_p", 0.9)),
                reasoning_effort=raw.get("reasoning_effort"),
                cost_ceiling_usd=float(raw.get("cost_ceiling_usd")) if raw.get("cost_ceiling_usd") is not None else None,
                enabled=bool(raw.get("enabled", True)),
            )
        return parsed

    def _build_task_routing(self) -> dict[str, dict[str, Any]]:
        task_routing = dict(_DEFAULT_TASK_ROUTING)
        for task, role in self._aliases.items():
            tier = 1
            if role == "free_premium":
                tier = 2
            elif role == "premium_escalation":
                tier = 3
            elif role == "coding":
                tier = 1
            task_routing[task] = {"role": role, "tier": tier}
        return task_routing

    def _provider_mode(self) -> str:
        configured = _trimmed_env("KAI_MODEL_PROVIDER") or str(self._config.get("provider_mode", "auto"))
        configured = configured.lower()
        return configured if configured in {"auto", "openrouter", "local"} else "auto"

    def _normalize_role(self, task_type: str) -> str:
        normalized = task_type.strip().lower()
        if normalized in self._roles:
            return normalized
        if normalized in self._aliases:
            return self._aliases[normalized]
        coding_hints = ("code", "patch", "test", "refactor", "docker", "kubernetes", "parser", "frontend", "backend", "cli")
        if any(hint in normalized for hint in coding_hints):
            return "coding"
        premium_hints = ("architecture", "multimodal", "hard", "complex", "failure")
        if any(hint in normalized for hint in premium_hints):
            return "premium_escalation"
        return "bulk_reasoning"

    def _resolve_local_model(self, alias: str | None) -> str | None:
        if not alias:
            return None
        env_name = _LOCAL_ALIAS_ENVS.get(alias)
        if not env_name:
            return None
        return _trimmed_env(env_name) or None

    def _route_override(self, role: str) -> str | None:
        env_name = _ROUTE_OVERRIDE_ENVS.get(role)
        return _trimmed_env(env_name) if env_name else None

    async def _check_local_endpoint(self) -> bool:
        base_url = _trimmed_env("KAI_LOCAL_LLM_BASE_URL")
        if not base_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{base_url.rstrip('/')}/models")
            return response.status_code < 500
        except Exception:
            logger.info("Local OpenAI-compatible endpoint unavailable at %s", base_url)
            return False

    async def _ensure_local_availability(self) -> bool:
        if self._local_available is None:
            self._local_available = await self._check_local_endpoint()
        return self._local_available

    def _estimated_cost(self, provider: str, model: str, estimated_tokens_k: float, max_output_tokens: int) -> float | None:
        unit_cost = _MODEL_COSTS_PER_1K.get(_provider_key(provider, model))
        if unit_cost is None:
            return None
        total_k = max(estimated_tokens_k, 0.0) + (max_output_tokens / 1000.0)
        return round(total_k * unit_cost, 6)

    async def _route_candidates(
        self,
        role: str,
        *,
        complexity: str,
        estimated_tokens_k: float,
        allow_cost_override: bool,
    ) -> list[ModelConfig]:
        policy = self._roles[role]
        if not policy.enabled:
            raise ProviderConfigurationError(f"route '{role}' is disabled")

        provider_mode = self._provider_mode()
        local_available = await self._ensure_local_availability() if provider_mode in {"auto", "local"} else False
        openrouter_key = _trimmed_env("OPENROUTER_API_KEY")
        openai_key = _trimmed_env("OPENAI_API_KEY")

        candidates: list[ModelConfig] = []
        skipped_for_ceiling = 0
        targets = list(policy.preferred)
        if role == "bulk_reasoning" and complexity == "high" and len(targets) > 1:
            targets = [targets[1], targets[0], *targets[2:]]

        for fallback_index, target in enumerate(targets):
            if not target.enabled:
                continue
            provider = target.provider
            if provider_mode == "local" and provider != "local":
                continue
            if provider_mode == "openrouter" and provider == "local":
                continue

            if provider == "local":
                model_name = self._resolve_local_model(target.alias)
                base_url = _trimmed_env("KAI_LOCAL_LLM_BASE_URL")
                if not model_name or not base_url:
                    continue
                if provider_mode == "auto" and local_available:
                    pass
                elif provider_mode == "local":
                    pass
                elif provider_mode == "auto":
                    continue
                api_key_env = ""
            else:
                if provider == "openrouter" and not openrouter_key:
                    continue
                if provider == "openai" and not openai_key:
                    continue
                model_name = self._route_override(role) if fallback_index == 0 else None
                model_name = model_name or target.model
                base_url = None
                api_key_env = _PROVIDER_API_KEYS.get(provider, "")
                if provider == "openrouter" and target.require_discovery_available:
                    if not await self._discovery.is_model_available(model_name or "", openrouter_key or None):
                        continue

            if not model_name:
                continue

            estimated_cost = self._estimated_cost(provider, model_name, estimated_tokens_k, policy.max_output_tokens)
            if policy.cost_ceiling_usd is not None and estimated_cost is not None and estimated_cost > policy.cost_ceiling_usd and not allow_cost_override:
                skipped_for_ceiling += 1
                continue
            if estimated_cost is not None and not self._tracker.can_afford(provider, estimated_cost):
                continue

            cost_per_1k = _MODEL_COSTS_PER_1K.get(_provider_key(provider, model_name), 0.0)
            tier = _PROVIDER_TIER.get(provider, 1)
            if role == "free_premium":
                tier = 2
            elif role == "premium_escalation":
                tier = 3 if provider != "openai" else 4

            candidates.append(
                ModelConfig(
                    provider=provider,
                    model=model_name,
                    api_key_env=api_key_env,
                    tier=tier,
                    context_window=policy.max_input_tokens,
                    cost_per_1k=cost_per_1k,
                    route_role=role,
                    fallback_index=fallback_index,
                    max_input_tokens=policy.max_input_tokens,
                    max_output_tokens=policy.max_output_tokens,
                    temperature=policy.temperature,
                    top_p=policy.top_p,
                    reasoning_effort=policy.reasoning_effort,
                    cost_ceiling_usd=policy.cost_ceiling_usd,
                    local_base_url=base_url,
                    local_alias=target.alias,
                    require_discovery_available=target.require_discovery_available,
                    estimated_cost_usd=estimated_cost,
                )
            )

        if candidates:
            if provider_mode == "auto" and local_available:
                local_first = [cfg for cfg in candidates if cfg.provider == "local"]
                remote = [cfg for cfg in candidates if cfg.provider != "local"]
                return [*local_first, *remote]
            return candidates

        if skipped_for_ceiling:
            raise CostCeilingExceededError(f"all routes for role '{role}' exceed the configured cost ceiling")
        if provider_mode == "openrouter" and not openrouter_key:
            raise ProviderConfigurationError("OPENROUTER_API_KEY is required when KAI_MODEL_PROVIDER=openrouter")
        if provider_mode == "local" and not _trimmed_env("KAI_LOCAL_LLM_BASE_URL"):
            raise ProviderConfigurationError("KAI_LOCAL_LLM_BASE_URL is required when KAI_MODEL_PROVIDER=local")
        raise ProviderConfigurationError(f"no available route candidates for role '{role}'")

    def _provider_for(self, model: ModelConfig) -> Any:
        if model.provider == "openrouter":
            provider = self._providers.get("openrouter")
            key = _trimmed_env("OPENROUTER_API_KEY")
            if provider is None or provider.api_key != key:
                provider = OpenRouterProvider(key)
                self._providers["openrouter"] = provider
            return provider
        if model.provider == "openai":
            provider = self._providers.get("openai")
            key = _trimmed_env("OPENAI_API_KEY")
            if provider is None or provider.api_key != key:
                provider = DirectOpenAIProvider(key)
                self._providers["openai"] = provider
            return provider
        base_url = model.local_base_url or _trimmed_env("KAI_LOCAL_LLM_BASE_URL")
        provider = self._providers.get("local")
        if provider is None or provider.base_url != base_url.rstrip("/"):
            provider = LocalOpenAICompatibleProvider(base_url)
            self._providers["local"] = provider
        return provider

    async def select(
        self,
        task_type: str,
        complexity: str = "medium",
        require_tool_calling: bool = False,
        estimated_tokens_k: float = 2.0,
        allow_cost_override: bool = False,
    ) -> ModelConfig:
        del require_tool_calling  # OpenAI-compatible routes here support tool calls uniformly.
        role = self._normalize_role(task_type)
        candidates = await self._route_candidates(
            role,
            complexity=complexity,
            estimated_tokens_k=estimated_tokens_k,
            allow_cost_override=allow_cost_override,
        )
        return candidates[0]

    async def complete(
        self,
        task_type: str,
        messages: list[dict[str, Any]],
        *,
        complexity: str = "medium",
        estimated_tokens_k: float = 2.0,
        allow_cost_override: bool = False,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> ProviderResponse:
        role = self._normalize_role(task_type)
        candidates = await self._route_candidates(
            role,
            complexity=complexity,
            estimated_tokens_k=estimated_tokens_k,
            allow_cost_override=allow_cost_override,
        )
        last_error: Exception | None = None
        for attempt_number, model in enumerate(candidates, start=1):
            provider = self._provider_for(model)
            request = ProviderRequest(
                messages=messages,
                role=role,
                max_output_tokens=model.max_output_tokens,
                temperature=model.temperature,
                top_p=model.top_p,
                reasoning_effort=model.reasoning_effort,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
            started = time.perf_counter()
            try:
                response = await provider.chat(model, request)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                total_tokens = int(response.usage.get("total_tokens", 0) or 0)
                if total_tokens and model.cost_per_1k:
                    self.record_usage(model, total_tokens / 1000.0)
                logger.info(
                    "model_route_success role=%s provider=%s model=%s attempt=%d latency_ms=%d input_tokens=%s output_tokens=%s estimated_cost_usd=%s",
                    role,
                    model.provider,
                    model.model,
                    attempt_number,
                    elapsed_ms,
                    response.usage.get("input_tokens", 0),
                    response.usage.get("output_tokens", 0),
                    response.estimated_cost_usd if response.estimated_cost_usd is not None else "unknown",
                )
                return response
            except ProviderRequestError as exc:
                last_error = exc
                logger.warning(
                    "model_route_failure role=%s provider=%s model=%s attempt=%d reason=%s retryable=%s",
                    role,
                    model.provider,
                    model.model,
                    attempt_number,
                    exc,
                    exc.retryable,
                )
                if not exc.retryable and not isinstance(exc, (AuthenticationError,)):
                    break
                continue
        if last_error:
            raise last_error
        raise ModelRoutingError(f"no providers succeeded for role '{role}'")

    def record_usage(self, model: ModelConfig, tokens_used_k: float) -> None:
        self._tracker.record_spend(model.provider, tokens_used_k, model.cost_per_1k)

    def budget_report(self) -> dict[str, dict[str, float]]:
        return self._tracker.budget_report()


_router: LLMBudgetRouter | None = None


def get_budget_router() -> LLMBudgetRouter:
    global _router
    if _router is None:
        _router = LLMBudgetRouter()
    return _router
