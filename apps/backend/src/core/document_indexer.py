"""
Kaison K1 - Document Indexer
Background service to continuously index documents into LlamaIndex RAG
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from ..integrations.llamaindex_rag import get_llamaindex_rag
from .intelligence_engine import get_intelligence_engine

logger = logging.getLogger(__name__)


class DocumentIndexer:
    """Background service to index documents into LlamaIndex"""

    def __init__(self):
        self.rag = None
        self.intelligence_engine = None
        self.rss_indexer_task: Optional[asyncio.Task] = None
        self.reindex_task: Optional[asyncio.Task] = None
        self.rss_interval_hours = 1
        self.reindex_interval_hours = 24

    async def initialize(self):
        """Initialize document indexer"""
        logger.info("Initializing Document Indexer")
        self.rag = await get_llamaindex_rag()
        self.intelligence_engine = await get_intelligence_engine()
        logger.info("Document Indexer initialized successfully")

    async def index_rss_feeds_continuously(self):
        """Run every hour to index new RSS items"""
        logger.info(f"Starting continuous RSS feed indexing (interval: {self.rss_interval_hours}h)")

        while True:
            try:
                logger.info("Indexing RSS feeds...")

                # Trigger intelligence scan (which indexes in RAG)
                await self.intelligence_engine.scan_feeds()

                logger.info(f"RSS feeds indexed successfully. Next run in {self.rss_interval_hours}h")

            except Exception as e:
                logger.error(f"Error indexing RSS feeds: {e}")

            # Wait for next run
            await asyncio.sleep(self.rss_interval_hours * 3600)

    async def index_new_findings(self, finding_data: dict):
        """Index finding as it's created"""
        try:
            if not self.rag:
                await self.initialize()

            logger.info(f"Indexing new finding: {finding_data.get('id', 'unknown')}")
            await self.rag.index_finding(finding_data)

        except Exception as e:
            logger.error(f"Error indexing finding: {e}")

    async def reindex_all(self):
        """Full reindex (run nightly)"""
        logger.info("Starting full reindex of all documents")

        try:
            # Get RAG stats before
            stats_before = await self.rag.get_stats()
            logger.info(f"Index stats before reindex: {stats_before.total_documents} documents")

            # Clear existing index
            # await self.rag.clear_index()  # Commented out - dangerous operation

            # Re-index RSS feeds
            logger.info("Re-indexing RSS feeds...")
            await self.intelligence_engine.scan_feeds()

            # Get RAG stats after
            stats_after = await self.rag.get_stats()
            logger.info(f"Index stats after reindex: {stats_after.total_documents} documents")

            logger.info("Full reindex completed successfully")

        except Exception as e:
            logger.error(f"Error during full reindex: {e}")

    async def start_background_indexing(
        self,
        rss_interval_hours: int = 1,
        reindex_interval_hours: int = 24
    ):
        """Start all background indexing tasks"""
        self.rss_interval_hours = rss_interval_hours
        self.reindex_interval_hours = reindex_interval_hours

        logger.info("Starting background document indexing tasks")

        # Start RSS feed indexer
        self.rss_indexer_task = asyncio.create_task(
            self.index_rss_feeds_continuously()
        )

        # Start nightly reindexer
        async def reindex_loop():
            while True:
                # Wait until next reindex time
                await asyncio.sleep(reindex_interval_hours * 3600)

                try:
                    await self.reindex_all()
                except Exception as e:
                    logger.error(f"Error in reindex loop: {e}")

        self.reindex_task = asyncio.create_task(reindex_loop())

        logger.info("Background document indexing tasks started")

    async def stop_background_indexing(self):
        """Stop all background indexing tasks"""
        logger.info("Stopping background document indexing tasks")

        if self.rss_indexer_task:
            self.rss_indexer_task.cancel()
            try:
                await self.rss_indexer_task
            except asyncio.CancelledError:
                pass

        if self.reindex_task:
            self.reindex_task.cancel()
            try:
                await self.reindex_task
            except asyncio.CancelledError:
                pass

        logger.info("Background document indexing tasks stopped")

    def get_status(self) -> dict:
        """Get indexer status"""
        return {
            "rss_indexer_active": self.rss_indexer_task is not None and not self.rss_indexer_task.done(),
            "reindex_task_active": self.reindex_task is not None and not self.reindex_task.done(),
            "rss_interval_hours": self.rss_interval_hours,
            "reindex_interval_hours": self.reindex_interval_hours
        }


# Singleton pattern
_document_indexer_instance: Optional[DocumentIndexer] = None


async def get_document_indexer() -> DocumentIndexer:
    """Get or create document indexer instance"""
    global _document_indexer_instance
    if _document_indexer_instance is None:
        _document_indexer_instance = DocumentIndexer()
        await _document_indexer_instance.initialize()
    return _document_indexer_instance
