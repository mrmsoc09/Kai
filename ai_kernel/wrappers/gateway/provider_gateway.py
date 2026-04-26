"""Provider gateway abstraction."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .capability_registry import find_models


@dataclass
class ProviderRequest:
    task: str
    prompt: str
    tools: Optional[list] = None
    privacy_tier: int = 1


class ProviderGateway:
    def __init__(self, client_factory):
        self.client_factory = client_factory

    def route(self, request: ProviderRequest) -> Dict[str, Any]:
        candidates = find_models(task=request.task, min_privacy=request.privacy_tier)
        if not candidates:
            return {"status": "error", "reason": "no providers available"}
        model = candidates[0]["model"]
        provider = candidates[0]["provider"]
        client = self.client_factory(provider)
        return {
            "status": "ok",
            "provider": provider,
            "model": model,
            "client": client,
        }
