"""Celery task for daily 6AM API Keys Orchestrator execution.

Runs daily at 6AM PT to plan API key usage across the scan queue.
Integrates with Vault-loaded API keys and ScanQueueRotator.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def run_api_keys_orchestrator_task() -> None:
    """6AM Celery beat task to orchestrate API key allocation.

    Called by Celery Beat daily at 6AM PT.
    Synchronous wrapper around async orchestrator.
    """
    try:
        import asyncio
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        import os

        from src.core.api_keys_orchestrator import APIKeysOrchestrator

        # Get database URL from environment
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            logger.error("DATABASE_URL not set, cannot run orchestrator")
            return

        # Create async engine and session
        engine = create_async_engine(db_url, echo=False)
        AsyncSessionLocal = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async def _run():
            async with AsyncSessionLocal() as db:
                orchestrator = APIKeysOrchestrator()
                await orchestrator.run(db)
                await db.commit()

        # Run async function
        asyncio.run(_run())

        logger.info("API Keys Orchestrator task completed successfully")

    except Exception as e:
        logger.error("API Keys Orchestrator task failed: %s", e, exc_info=True)
