from __future__ import annotations

import asyncio
import html
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .client import TriliumClient

logger = logging.getLogger(__name__)


@dataclass
class IngestJob:
    parent_id: str
    tool_name: str
    raw_output: str
    timestamp: datetime


class ToolMemoryInterface:
    """
    Ingest layer for automated reconnaissance data.
    Features rate-limiting and automatic note formatting.
    """

    def __init__(self, client: TriliumClient, max_requests_per_second: float = 2.0):
        self.client = client
        self.queue: asyncio.Queue[IngestJob] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._interval = 1.0 / max_requests_per_second
        self._running = False

    def start(self):
        """Starts the background worker for processing ingest jobs."""
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("ToolMemoryInterface ingest worker started.")

    async def stop(self):
        """Stops the background worker and waits for the queue to drain."""
        self._running = False
        if self._worker_task:
            await self.queue.join()
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("ToolMemoryInterface ingest worker stopped.")

    async def log_discovery(self, parent_id: str, tool_name: str, raw_output: str):
        """Queues a discovery log job."""
        job = IngestJob(
            parent_id=parent_id,
            tool_name=tool_name,
            raw_output=raw_output,
            timestamp=datetime.now(UTC),
        )
        await self.queue.put(job)
        if not self._running:
            logger.warning("Ingest job queued but worker is not running. Call start().")

    async def _worker(self):
        """Background worker that processes jobs with rate-limiting."""
        while self._running:
            job = await self.queue.get()
            try:
                await self._process_job(job)
                await asyncio.sleep(self._interval)
            except Exception as e:
                logger.error(f"Error processing ingest job from {job.tool_name}: {str(e)}")
            finally:
                self.queue.task_done()

    async def _process_job(self, job: IngestJob):
        """Formats and writes the discovery note to Trilium."""
        title = f"{job.tool_name} Scan - {job.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Security: Escape raw output to prevent XSS in Trilium UI
        escaped_output = html.escape(job.raw_output)
        formatted_content = f"<pre><code>{escaped_output}</code></pre>"
        
        # Create the note
        note = await self.client.create_note(
            parent_id=job.parent_id,
            title=title,
            content=formatted_content
        )
        note_id = note["note"]["noteId"]
        
        # Add mandatory attributes
        await self.client.create_attribute(
            note_id=note_id,
            type="label",
            name="source",
            value=job.tool_name
        )
        await self.client.create_attribute(
            note_id=note_id,
            type="label",
            name="status",
            value="unverified"
        )
        
        logger.debug(f"Ingested discovery from {job.tool_name} into note {note_id}")
