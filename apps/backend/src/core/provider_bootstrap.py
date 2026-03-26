from __future__ import annotations

import os
from dataclasses import dataclass
from getpass import getpass
from typing import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ProviderBootstrapStatus:
    provider: str
    key_env: str
    source: str
    available: bool
    validated: bool
    error: str | None = None


PROVIDER_ENV_KEYS: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
}


def _pick_first_env(names: tuple[str, ...]) -> tuple[str, str | None]:
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return name, value
    return names[0], None


def _validate_openrouter(api_key: str, timeout: float) -> tuple[bool, str | None]:
    req = Request(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - controlled HTTPS endpoint
            if int(getattr(resp, "status", 0)) >= 400:
                return False, f"http_status:{getattr(resp, 'status', 'unknown')}"
        return True, None
    except URLError as exc:
        return False, str(exc)
    except Exception as exc:  # pragma: no cover - transport/runtime variance
        return False, str(exc)


def run_zero_touch_provider_bootstrap(
    *,
    interactive_prompt: bool = False,
    validate_calls: bool = False,
    timeout_seconds: float = 4.0,
    logger_fn: Callable[[str], None] | None = None,
) -> dict[str, ProviderBootstrapStatus]:
    """
    Env-first provider bootstrap with optional non-echoing prompt fallback.

    - Checks provider API keys from environment.
    - Optionally prompts with getpass() when key is absent.
    - Validation errors are reported in status but never raised.
    """
    statuses: dict[str, ProviderBootstrapStatus] = {}

    def _log(message: str) -> None:
        if logger_fn:
            logger_fn(message)

    for provider, key_names in PROVIDER_ENV_KEYS.items():
        key_env, value = _pick_first_env(key_names)
        source = "env"
        if not value and interactive_prompt and os.isatty(0):
            try:
                typed = getpass(f"Enter {provider} API key ({key_env}): ").strip()
            except Exception:
                typed = ""
            if typed:
                value = typed
                os.environ[key_env] = typed
                source = "prompt"

        available = bool(value)
        validated = False
        error: str | None = None

        if available and validate_calls:
            if provider == "openrouter":
                validated, error = _validate_openrouter(value or "", timeout_seconds)
            else:
                # For providers without deterministic no-cost probe in this layer,
                # consider the key format present and defer API validation to runtime.
                validated = True
        elif available:
            validated = True

        if not available:
            error = "missing_api_key"

        status = ProviderBootstrapStatus(
            provider=provider,
            key_env=key_env,
            source=source,
            available=available,
            validated=validated,
            error=error,
        )
        statuses[provider] = status
        if status.error:
            _log(f"[provider-bootstrap] {provider}: {status.error}")

    return statuses
