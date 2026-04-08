from __future__ import annotations

import logging
import asyncio
import httpx
import json # NEW: Missing import
from typing import List, Dict, Any
from .trilium.client import TriliumClient

logger = logging.getLogger(__name__)

class OpportunityFetcher:
    """
    K1 Opportunity Fetcher (Stage 25).
    Ingests bug bounty opportunities from HackerOne and Intigriti.
    """

    def __init__(self, trilium_client: TriliumClient, h1_token: str = None, intigriti_token: str = None):
        self.trilium = trilium_client
        self.h1_token = h1_token
        self.intigriti_token = intigriti_token
        self.opportunity_root_id = "opportunities"
        self._sem = asyncio.Semaphore(5) # NEW: Concurrency limit for Trilium writes

    async def fetch_all(self):
        """Fetches from all configured providers."""
        tasks = []
        if self.h1_token:
            tasks.append(self._fetch_h1())
        if self.intigriti_token:
            tasks.append(self._fetch_intigriti())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, list):
                await self._store_opportunities(res)
            elif isinstance(res, Exception):
                logger.error(f"OpportunityFetcher: Error during fetch: {res}")

    async def _fetch_h1(self) -> List[Dict[str, Any]]:
        """Mock HackerOne API call."""
        logger.info("OpportunityFetcher: Fetching from HackerOne...")
        # Simulated API response
        return [
            {"id": "h1-001", "name": "Global Bank", "roi_score": 85, "platform": "h1"},
            {"id": "h1-002", "name": "Social Connect", "roi_score": 92, "platform": "h1"}
        ]

    async def _fetch_intigriti(self) -> List[Dict[str, Any]]:
        """Mock Intigriti API call."""
        logger.info("OpportunityFetcher: Fetching from Intigriti...")
        return [
            {"id": "int-001", "name": "Crypto Exchange", "roi_score": 95, "platform": "intigriti"}
        ]

    async def _store_opportunities(self, opportunities: List[Dict[str, Any]]):
        """Saves opportunities to Trilium with rate-limiting."""
        for opp in opportunities:
            async with self._sem: # Respect concurrency limit
                title = f"{opp['platform'].upper()}: {opp['name']}"
                content = f"<pre><code>{json.dumps(opp, indent=2)}</code></pre>"
                
                # Check for existing
                query = f"note.title='{title}'"
                existing = await self.trilium.search_notes(query)
                
                if not existing:
                    note = await self.trilium.create_note(self.opportunity_root_id, title, content)
                    note_id = note["note"]["noteId"]
                    await self.trilium.create_attribute(note_id, "label", "roi_score", str(opp["roi_score"]))
                    await self.trilium.create_attribute(note_id, "label", "status", "unverified")
                    logger.info(f"OpportunityFetcher: Stored {title}")
                else:
                    logger.debug(f"OpportunityFetcher: {title} already exists.")
                
                await asyncio.sleep(0.1) # NEW: Subtle drip to prevent Trilium API spikes
