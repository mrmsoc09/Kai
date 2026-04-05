from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, UTC
from typing import Any, Dict, List, Optional

from apps.backend.src.core.trilium.client import TriliumClient

logger = logging.getLogger(__name__)

@dataclass
class APIKey:
    provider: str
    key: str
    daily_limit: int
    used_today: int = 0
    reset_time_utc: time = time(0, 0)
    is_paused: bool = False
    pause_until: Optional[datetime] = None

@dataclass
class ROITask:
    priority: int  # 0: Verified, 1: Fresh Delta, 2: Routine
    task_id: str
    target: str
    tool: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

class K1APIGovernor:
    """
    Intelligent API Governor (Stage 11).
    Manages the 'War Chest' of free-tier keys and ensures 24/7/365 autonomous execution.
    """

    def __init__(self, trilium_client: TriliumClient, protected_root_id: str):
        self.trilium = trilium_client
        self.protected_root_id = protected_root_id
        self.keys: Dict[str, APIKey] = {}
        self.queue: List[ROITask] = []
        self._lock = asyncio.Lock()
        self._running = False

    async def start(self):
        """Starts the Governor service."""
        self._running = True
        # 1. Pull keys from Trilium Protected Vault
        await self._refresh_keys_from_vault()
        
        # 2. Start background worker loops
        asyncio.create_task(self._quota_reset_loop())
        asyncio.create_task(self._queue_processor_loop())
        logger.info("K1 API Governor service started.")

    async def _refresh_keys_from_vault(self):
        """Pulls API keys directly from the Trilium Protected Vault."""
        logger.info("Governor: Refreshing API War Chest from Trilium...")
        try:
            # Search for the 'API_War_Chest' note in the protected subtree
            query = f"parentId={self.protected_root_id} AND note.title='API_War_Chest'"
            results = await self.trilium.search_notes(query)
            
            if not results:
                logger.warning("No 'API_War_Chest' note found in Protected Vault.")
                return

            note = await self.trilium.get_note(results[0]["noteId"])
            # Clean and parse JSON content (excising HTML tags)
            raw_content = note.get("content", "{}")
            clean_json = re.sub(r"<.*?>", "", raw_content).strip()
            key_data = json.loads(clean_json)

            async with self._lock:
                for provider, cfg in key_data.items():
                    self.keys[provider] = APIKey(
                        provider=provider,
                        key=cfg["key"],
                        daily_limit=cfg.get("limit", 100),
                        reset_time_utc=time.fromisoformat(cfg.get("reset_time", "00:00:00"))
                    )
            logger.info(f"Governor: Loaded {len(self.keys)} API keys from vault.")
        except Exception as e:
            logger.error(f"Governor: Failed to refresh keys: {str(e)}")

    async def add_to_queue(self, task: ROITask):
        """Adds a task to the ROI-based priority queue."""
        async with self._lock:
            self.queue.append(task)
            # Sort by Priority (Low number = High priority) then by age
            self.queue.sort(key=lambda x: (x.priority, x.created_at))
        logger.debug(f"Governor: Task {task.task_id} added to queue (Priority {task.priority}).")

    async def request_token(self, provider: str) -> Optional[str]:
        """
        Request an API token. 
        Implements 429 Failover and Quota management.
        """
        async with self._lock:
            key_obj = self.keys.get(provider.lower())
            if not key_obj:
                return None

            now = datetime.now(UTC)
            
            # Check if paused
            if key_obj.is_paused:
                if key_obj.pause_until and now >= key_obj.pause_until:
                    key_obj.is_paused = False
                    key_obj.pause_until = None
                    logger.info(f"Governor: Resuming {provider} - Cooling period expired.")
                else:
                    return None

            # Check daily quota
            if key_obj.used_today >= key_obj.daily_limit:
                logger.warning(f"Governor: {provider} quota exhausted ({key_obj.used_today}/{key_obj.daily_limit}).")
                return None

            # Grant token
            key_obj.used_today += 1
            return key_obj.key

    async def handle_429(self, provider: str, retry_after_seconds: int = 3600):
        """Handles 'Too Many Requests' by pausing the provider."""
        async with self._lock:
            key_obj = self.keys.get(provider.lower())
            if key_obj:
                key_obj.is_paused = True
                key_obj.pause_until = datetime.now(UTC) + timedelta(seconds=retry_after_seconds)
                logger.warning(f"Governor: 429 received for {provider}. Pausing until {key_obj.pause_until}.")

    async def _quota_reset_loop(self):
        """Resets daily quotas at 00:00 UTC."""
        while self._running:
            now = datetime.now(UTC)
            # Calculate seconds until next UTC midnight
            tomorrow = now.date() + timedelta(days=1)
            next_reset = datetime.combine(tomorrow, time(0, 0), tzinfo=UTC)
            wait_seconds = (next_reset - now).total_seconds()
            
            await asyncio.sleep(wait_seconds)
            
            async with self._lock:
                for key_obj in self.keys.values():
                    logger.info(f"Governor: Resetting daily quota for {key_obj.provider}.")
                    key_obj.used_today = 0
                    key_obj.is_paused = False

    async def _queue_processor_loop(self):
        """Drips tasks from the queue based on key availability."""
        while self._running:
            if not self.queue:
                await asyncio.sleep(5)
                continue

            # In Stage 11, the actual task execution is triggered by agents.
            # The Governor acts as the 'Gatekeeper'.
            # A background 'Mission Bootstrapper' (implemented separately)
            # would call `request_token` before firing agents.
            await asyncio.sleep(1)

    def get_quota_status(self) -> Dict[str, Any]:
        """Returns real-time consumption for the dashboard."""
        return {
            provider: {
                "used": k.used_today,
                "limit": k.daily_limit,
                "paused": k.is_paused,
                "reset_in": str(k.pause_until - datetime.now(UTC)) if k.pause_until else "0"
            } for provider, k in self.keys.items()
        }
