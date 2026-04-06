from __future__ import annotations

import logging
import os
import httpx
from datetime import UTC, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

class SovereignAlerter:
    """
    K1 Sovereign Alerter.
    Provides real-time notifications via Telegram for critical mission events.
    """

    def __init__(self):
        self.bot_token = os.environ.get("K1_TELEGRAM_TOKEN")
        self.chat_id = os.environ.get("K1_TELEGRAM_CHAT_ID")
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            logger.warning("SovereignAlerter: Telegram credentials missing. Alerting disabled.")

    async def send_alert(self, message: str, level: str = "INFO"):
        """Sends a formatted alert to the designated Telegram chat."""
        if not self.enabled:
            return

        emoji = "ℹ️"
        if level == "CRITICAL": emoji = "🚨"
        elif level == "SUCCESS": emoji = "✅"
        elif level == "WARNING": emoji = "⚠️"

        timestamp = datetime.now(UTC).strftime("%H:%M:%S UTC")
        formatted_msg = f"{emoji} <b>K1 {level}</b> [{timestamp}]\n\n{message}"

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = {
            "chat_id": self.chat_id,
            "text": formatted_msg,
            "parse_mode": "HTML"
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=data, timeout=10.0)
                if resp.status_code != 200:
                    logger.error(f"SovereignAlerter: Telegram API returned {resp.status_code}")
        except Exception as e:
            logger.error(f"SovereignAlerter: Failed to send Telegram alert: {str(e)}")

    async def notify_exhaustion(self, provider: str):
        """Specific alert for API key exhaustion."""
        await self.send_alert(
            f"API Provider <b>{provider.upper()}</b> has reached its daily quota limit. "
            "Governor has engaged failover/cooling mode.",
            level="WARNING"
        )

    async def notify_verified_poc(self, target: str, note_id: str):
        """Specific alert for a verified exploit."""
        await self.send_alert(
            f"<b>Vulnerability Verified!</b>\nTarget: <code>{target}</code>\n"
            f"Evidence: <pre>{note_id}</pre>\n"
            "Mission status updated to #status=verified_poc.",
            level="SUCCESS"
        )
