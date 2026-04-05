from __future__ import annotations

import logging
import os
import json
from typing import Any, Dict, Optional
from datetime import datetime, UTC

logger = logging.getLogger(__name__)

class Governor:
    """
    K1 API Governor.
    Manages API key usage, rate limits, and token budgets.
    Ensures no agent fires without a valid, non-exhausted API key.
    """

    def __init__(self, state_file: str | None = None):
        self.state_file = state_file or os.environ.get("K1_GOVERNOR_STATE", "/tmp/k1_governor_state.json")
        self.api_keys = self._load_api_keys()
        self.usage_stats = self._load_usage_stats()
        logger.info("Governor initialized.")

    def _load_api_keys(self) -> Dict[str, Any]:
        """Loads API keys from environment variables."""
        keys = {
            "openai": os.environ.get("OPENAI_API_KEY"),
            "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
            "gemini": os.environ.get("GEMINI_API_KEY"),
            "shodan": os.environ.get("SHODAN_API_KEY"),
            "censys": os.environ.get("CENSYS_API_KEY"),
            "chaos": os.environ.get("CHAOS_KEY"),
            "github": os.environ.get("GITHUB_TOKEN"),
        }
        return {k: v for k, v in keys.items() if v}

    def _load_usage_stats(self) -> Dict[str, Any]:
        """Loads usage statistics from the state file."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    stats = json.load(f)
                    # Reset stats if it's a new day
                    last_reset = stats.get("last_reset")
                    if last_reset:
                        last_reset_dt = datetime.fromisoformat(last_reset)
                        if last_reset_dt.date() < datetime.now(UTC).date():
                            return self._get_default_stats()
                    return stats
            except (json.JSONDecodeError, ValueError):
                pass
        return self._get_default_stats()

    def _get_default_stats(self) -> Dict[str, Any]:
        return {
            "last_reset": datetime.now(UTC).isoformat(),
            "usage": {k: 0 for k in self.api_keys.keys()}
        }

    def _save_usage_stats(self):
        """Saves usage statistics to the state file."""
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.usage_stats, f, indent=2)
        except Exception as e:
            logger.error(f"Governor: Failed to save usage stats: {str(e)}")

    async def request_token(self, agent_id: str) -> bool:
        """
        Requests an API token for a specific agent.
        Returns True if granted, False if budget exceeded or key missing.
        """
        # Determine which key is needed based on agent_id or metadata
        # Simplified: map agent_id prefix to provider
        provider = agent_id.split('_')[0].lower()
        
        if provider not in self.api_keys:
            logger.warning(f"Governor: Denied token for {agent_id}. Provider {provider} not configured.")
            return False

        # Check daily budget (e.g., 500 requests per key per day)
        daily_limit = int(os.environ.get(f"K1_{provider.upper()}_DAILY_LIMIT", 500))
        current_usage = self.usage_stats["usage"].get(provider, 0)

        if current_usage >= daily_limit:
            logger.warning(f"Governor: Denied token for {agent_id}. Daily limit reached for {provider}.")
            return False

        # Grant token and increment usage
        self.usage_stats["usage"][provider] = current_usage + 1
        self._save_usage_stats()
        logger.debug(f"Governor: Granted token for {agent_id} ({provider}). Usage: {current_usage + 1}/{daily_limit}")
        return True

    def get_token(self, provider: str) -> str | None:
        """Retrieves the actual API key for a provider."""
        return self.api_keys.get(provider)
