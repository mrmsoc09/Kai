"""
Platform Settings Router — LLM provider configuration + runtime API key management.
Saves to artifacts/settings/platform.json and sets env vars so the platform picks them up.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..core.auth import get_current_user, require_roles, ROLE_ADMIN

router = APIRouter(prefix="/settings", tags=["platform-settings"])

_SETTINGS_PATH = Path(
    os.getenv("K1_SETTINGS_PATH", "artifacts/settings/platform.json")
)


def _load() -> Dict[str, Any]:
    if not _SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: Dict[str, Any]) -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ─── LLM Config ──────────────────────────────────────────────────────────────

class LLMConfigRequest(BaseModel):
    provider: str = Field(..., max_length=50)   # anthropic | openai | ollama | custom
    model: str = Field(..., max_length=200)
    api_key: str = Field("", max_length=1000)   # blank = keep existing
    base_url: str = Field("", max_length=500)   # for Ollama / custom endpoints
    temperature: float = Field(0.3, ge=0.0, le=2.0)
    notes: str = Field("", max_length=1000)


@router.get("/llm")
async def get_llm_config(_user=Depends(get_current_user)) -> Dict[str, Any]:
    """Return current LLM config (API key value is never returned)."""
    settings = _load()
    llm = settings.get("llm", {})
    return {
        "provider": llm.get("provider", ""),
        "model": llm.get("model", ""),
        "base_url": llm.get("base_url", ""),
        "temperature": llm.get("temperature", 0.3),
        "has_api_key": bool(llm.get("api_key", "")),
        "notes": llm.get("notes", ""),
        "updated_at": llm.get("updated_at", ""),
        "updated_by": llm.get("updated_by", ""),
    }


@router.post("/llm")
async def save_llm_config(
    body: LLMConfigRequest,
    user=Depends(require_roles(ROLE_ADMIN)),
) -> Dict[str, Any]:
    """Save LLM config and set environment variables for the current process."""
    settings = _load()
    existing_key = settings.get("llm", {}).get("api_key", "")

    # Keep existing key if not supplied (masked in UI)
    resolved_key = body.api_key.strip() or existing_key

    settings["llm"] = {
        "provider": body.provider,
        "model": body.model,
        "api_key": resolved_key,
        "base_url": body.base_url,
        "temperature": body.temperature,
        "notes": body.notes,
        "updated_by": getattr(user, "id", "unknown"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Propagate to live env so agent processes in this worker pick up the key
    if resolved_key:
        if body.provider == "anthropic":
            os.environ["ANTHROPIC_API_KEY"] = resolved_key
        elif body.provider == "openai":
            os.environ["OPENAI_API_KEY"] = resolved_key
        elif body.provider in ("ollama", "custom"):
            os.environ["CUSTOM_LLM_API_KEY"] = resolved_key

    if body.model:
        os.environ["K1_PRIMARY_MODEL"] = body.model

    if body.base_url and body.provider in ("ollama", "custom"):
        os.environ["OLLAMA_BASE_URL"] = body.base_url
        os.environ["CUSTOM_LLM_BASE_URL"] = body.base_url

    if body.provider:
        os.environ["K1_PRIMARY_LLM_PROVIDER"] = body.provider

    _save(settings)
    return {
        "ok": True,
        "provider": body.provider,
        "model": body.model,
        "has_api_key": bool(resolved_key),
    }


@router.get("/llm/providers")
async def list_providers(_user=Depends(get_current_user)) -> Dict[str, Any]:
    """Return supported providers and their available models."""
    return {
        "providers": {
            "anthropic": {
                "label": "Anthropic Claude",
                "requires_key": True,
                "models": [
                    {"id": "claude-opus-4-6", "label": "Claude Opus 4.6 (Most Capable)"},
                    {"id": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6 (Balanced) ★"},
                    {"id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5 (Fast)"},
                ],
            },
            "openai": {
                "label": "OpenAI",
                "requires_key": True,
                "models": [
                    {"id": "gpt-4o", "label": "GPT-4o (Best)"},
                    {"id": "gpt-4o-mini", "label": "GPT-4o Mini (Fast)"},
                    {"id": "gpt-4-turbo", "label": "GPT-4 Turbo"},
                    {"id": "gpt-3.5-turbo", "label": "GPT-3.5 Turbo (Economy)"},
                ],
            },
            "ollama": {
                "label": "Ollama (Local)",
                "requires_key": False,
                "models": [
                    {"id": "llama3.2", "label": "Llama 3.2"},
                    {"id": "mistral", "label": "Mistral"},
                    {"id": "codellama", "label": "CodeLlama"},
                    {"id": "deepseek-coder", "label": "DeepSeek Coder"},
                    {"id": "custom", "label": "Custom model name"},
                ],
            },
            "custom": {
                "label": "Custom / OpenAI-compatible",
                "requires_key": True,
                "models": [],
            },
        }
    }
