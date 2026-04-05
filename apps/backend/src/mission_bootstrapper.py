import asyncio
import os
import logging
import json
from datetime import datetime, time, timedelta, UTC
import zoneinfo
from typing import Any

from apps.backend.src.core.trilium.client import TriliumClient
from apps.backend.src.core.trilium.query import OrchestrationQueryLayer
from apps.backend.src.core.praison_topology import MissionOrchestrator

logger = logging.getLogger(__name__)

class MissionBootstrapper:
    """
    K1 Mission Bootstrapper (Stage 11 Readiness).
    Triggers daily at 06:00 MST to populate the mission queue from Trilium BBP_Scope.
    """

    def __init__(self, trilium_client: TriliumClient, orchestrator: MissionOrchestrator):
        self.trilium = trilium_client
        self.orchestrator = orchestrator
        self.scope_note_id = os.environ.get("K1_BBP_SCOPE_NOTE_ID", "bbp_scope")
        self.mst_tz = zoneinfo.ZoneInfo("America/Denver")
        self.daily_limit = 25
        self._running = False

    async def start(self):
        self._running = True
        asyncio.create_task(self._scheduler_loop())
        logger.info("MissionBootstrapper: Scheduler started.")

    async def _scheduler_loop(self):
        while self._running:
            now_mst = datetime.now(self.mst_tz)
            next_run = datetime.combine(now_mst.date(), time(6, 0), tzinfo=self.mst_tz)
            
            if now_mst >= next_run:
                next_run += timedelta(days=1)
            
            wait_seconds = (next_run - now_mst).total_seconds()
            logger.info(f"MissionBootstrapper: Next run at {next_run} ({wait_seconds:.0f}s wait)")
            
            try:
                await asyncio.sleep(wait_seconds)
                await self.bootstrap_daily_mission()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"MissionBootstrapper: Error in scheduler: {str(e)}")
                await asyncio.sleep(60)

    async def bootstrap_daily_mission(self):
        """Parses scope and starts missions."""
        logger.info("MissionBootstrapper: Bootstrapping daily mission...")
        
        try:
            note = await self.trilium.get_note(self.scope_note_id)
            # Robust parsing of scope
            content = note.get("content", "")
            # Remove HTML tags and extract potential JSON
            clean_content = json.loads(content.replace("<pre><code>", "").replace("</code></pre>", "").strip())
            
            targets = clean_content.get("targets", [])[:self.daily_limit]
            
            for target in targets:
                mission_id = f"mission_{datetime.now(UTC).strftime('%Y%m%d')}_{target['id']}"
                await self.orchestrator.start_mission(mission_id, target['id'])
                
        except Exception as e:
            logger.error(f"MissionBootstrapper: Bootstrap failed: {str(e)}")

    def stop(self):
        self._running = False
