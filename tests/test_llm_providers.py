from __future__ import annotations

import types

from apps.backend.src.core import llm_providers as llm_providers_mod
from apps.backend.src.core import secret_manager as secret_manager_mod


class _FakeVaultSecretProvider(secret_manager_mod.BaseSecretProvider):
    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def get_secret(self, name: str) -> str | None:
        return self._values.get(name)


def _build_secret_manager(
    monkeypatch,
    vault_values: dict[str, str],
    *,
    environment: str = "production",
    allow_env_fallback: bool = False,
) -> secret_manager_mod.SecretManager:
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("K1_SECRET_BACKEND", "vault")
    monkeypatch.setenv(
        "K1_ALLOW_ENV_SECRETS", "true" if allow_env_fallback else "false"
    )
    monkeypatch.setattr(
        secret_manager_mod,
        "VaultSecretProvider",
        lambda: _FakeVaultSecretProvider(vault_values),
    )
    return secret_manager_mod.SecretManager()


def _build_genai_stub(calls: dict[str, str]):
    def configure(*, api_key: str) -> None:
        calls["api_key"] = api_key

    def generative_model(model: str):
        calls["model"] = model
        return types.SimpleNamespace(model=model)

    return types.SimpleNamespace(
        configure=configure,
        GenerativeModel=generative_model,
    )


def _initialize_vertex_ai_client(
    manager: secret_manager_mod.SecretManager,
    vertex_ai_module,
):
    """Minimal key-to-client plumbing for Vertex AI-style initialization."""
    api_key = manager.get_required("VERTEX_API_KEY")
    project_id = manager.get_required("VERTEX_PROJECT_ID")
    location = manager.get_optional("VERTEX_LOCATION") or "us-central1"

    vertex_ai_module.init(project=project_id, location=location, api_key=api_key)
    return vertex_ai_module.GenerativeModel("gemini-1.5-pro")


def test_gemini_initialization(monkeypatch) -> None:
    """Verifies Gemini client pulls its key from Vault."""
    manager = _build_secret_manager(
        monkeypatch,
        {"GOOGLE_API_KEY": "vault-gemini-key"},
        environment="production",
        allow_env_fallback=False,
    )

    calls: dict[str, str] = {}
    monkeypatch.setattr(llm_providers_mod, "genai", _build_genai_stub(calls))
    monkeypatch.setattr(llm_providers_mod, "get_secret_manager", lambda: manager)

    provider = llm_providers_mod.GeminiProvider(
        llm_providers_mod.ProviderConfig(provider=llm_providers_mod.LLMProvider.GEMINI)
    )

    assert calls["api_key"] == "vault-gemini-key"
    assert calls["model"] == provider.model
    assert provider.client.model == provider.model


def test_vertex_ai_initialization(monkeypatch) -> None:
    """Verifies Vertex AI credentials are retrieved and used to initialize client plumbing."""
    manager = _build_secret_manager(
        monkeypatch,
        {
            "VERTEX_API_KEY": "vault-vertex-key",
            "VERTEX_PROJECT_ID": "vault-project-id",
            "VERTEX_LOCATION": "us-east4",
        },
        environment="production",
        allow_env_fallback=False,
    )

    calls: dict[str, object] = {}

    def _init(**kwargs):
        calls["init"] = kwargs

    def _generative_model(model: str):
        calls["model"] = model
        return types.SimpleNamespace(model=model)

    vertex_ai_stub = types.SimpleNamespace(
        init=_init,
        GenerativeModel=_generative_model,
    )

    client = _initialize_vertex_ai_client(manager, vertex_ai_stub)

    assert calls["init"] == {
        "project": "vault-project-id",
        "location": "us-east4",
        "api_key": "vault-vertex-key",
    }
    assert calls["model"] == "gemini-1.5-pro"
    assert client.model == "gemini-1.5-pro"


def test_vault_key_fallback(monkeypatch) -> None:
    """Ensures missing Vault key gracefully falls back to env-backed secret in allowed mode."""
    monkeypatch.setenv("GOOGLE_API_KEY", "env-fallback-key")

    manager = _build_secret_manager(
        monkeypatch,
        {},  # Simulate missing key in Vault.
        environment="development",
        allow_env_fallback=True,
    )

    calls: dict[str, str] = {}
    monkeypatch.setattr(llm_providers_mod, "genai", _build_genai_stub(calls))
    monkeypatch.setattr(llm_providers_mod, "get_secret_manager", lambda: manager)

    provider = llm_providers_mod.GeminiProvider(
        llm_providers_mod.ProviderConfig(provider=llm_providers_mod.LLMProvider.GEMINI)
    )

    assert calls["api_key"] == "env-fallback-key"
    assert provider.client.model == provider.model
