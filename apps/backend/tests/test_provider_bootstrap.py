from __future__ import annotations

import pytest

from apps.backend.src.core.provider_bootstrap import run_zero_touch_provider_bootstrap


def test_provider_bootstrap_env_first(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test-gemini")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anth-test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    status = run_zero_touch_provider_bootstrap(
        interactive_prompt=False,
        validate_calls=False,
    )

    assert status["openai"].available is True
    assert status["openai"].source == "env"
    assert status["gemini"].available is True
    assert status["anthropic"].available is True
    assert status["openrouter"].available is False
    assert status["openrouter"].error == "missing_api_key"
