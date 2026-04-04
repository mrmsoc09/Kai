from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any

from .client import TriliumClient

logger = logging.getLogger(__name__)


class StateHandoffSystem:
    """
    Monitors Trilium for status changes and triggers agentic handoffs.
    Automates the transition from discovery to exploitation and reporting.
    """

    def __init__(
        self,
        client: TriliumClient,
        bounty_ready_id: str | None = None,
        system_log_id: str | None = None,
    ):
        self.client = client
        self.bounty_ready_id = bounty_ready_id or os.environ.get("BOUNTY_READY_ID", "bounty_ready")
        self.system_log_id = system_log_id or os.environ.get("SYSTEM_LOG_ID", "system_log")
        self._running = False
        self._watcher_task: asyncio.Task | None = None

    def start(self, interval_seconds: float = 10.0):
        """Starts the watcher loop."""
        if not self._running:
            self._running = True
            self._watcher_task = asyncio.create_task(self._watcher(interval_seconds))
            logger.info("StateHandoffSystem watcher started.")

    async def stop(self):
        """Stops the watcher loop."""
        self._running = False
        if self._watcher_task:
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
            logger.info("StateHandoffSystem watcher stopped.")

    async def _watcher(self, interval: float):
        """Polls for notes with status changes that need processing."""
        while self._running:
            try:
                # Search for notes with relevant statuses that haven't been handoff-processed
                # Syntax: status label present, but handoff_processed label absent
                query = "note.labels.status AND !note.labels.handoff_processed"
                pending_notes = await self.client.search_notes(query)
                
                for note_summary in pending_notes:
                    note_id = note_summary["noteId"]
                    # Get full attributes to find the current status
                    attrs = await self.client.get_attributes(note_id)
                    current_status = next(
                        (a["value"] for a in attrs if a["name"] == "status"), 
                        None
                    )
                    
                    if current_status:
                        await self.trigger_handoff(note_id, current_status)
                        # Mark as processed to avoid duplicate triggers
                        await self.client.create_attribute(note_id, "label", "handoff_processed", "true")

            except Exception as e:
                logger.error(f"Error in handoff watcher: {str(e)}")
            
            await asyncio.sleep(interval)

    async def trigger_handoff(self, note_id: str, current_status: str):
        """Executes logic based on the status of a note."""
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] Handoff triggered for {note_id} (Status: {current_status})"
        logger.info(log_entry)
        
        # Log to system.log note
        try:
            # Append to system log (this is a simplified append)
            # In a real app, you'd fetch the content and concatenate
            await self._append_to_system_log(log_entry)
        except Exception:
            logger.warning("Could not write to system log note.")

        if current_status == "exploitable":
            await self._handle_exploitable(note_id)
        elif current_status == "verified":
            await self._handle_verified(note_id)

    async def _handle_exploitable(self, note_id: str):
        """Triggers exploitation agents (simulated)."""
        logger.info(f"Triggering Exploit Agent for note {note_id}")
        # In implementation, this would call an external agent service
        msg = "<h3>Exploit Agent Status</h3><p>Payload generation initiated...</p>"
        await self.client.update_note(note_id, msg)

    async def _handle_verified(self, note_id: str):
        """Moves note to Bounty folder and generates report template."""
        logger.info(f"Moving {note_id} to Bounty Ready folder and drafting report.")
        
        # Move the note
        await self.client.move_note(note_id, self.bounty_ready_id)
        
        # Generate report template
        report_template = (
            "<h1>Bounty Draft Report</h1>"
            "<h2>Vulnerability Summary</h2>"
            "<p>[Describe the finding here]</p>"
            "<h2>Reproduction Steps</h2>"
            "<ol><li>Navigate to target</li><li>Inject payload</li><li>Observe result</li></ol>"
            "<h2>Impact</h2>"
            "<p>[Describe business impact]</p>"
        )
        await self.client.update_note(note_id, report_template)

    async def _append_to_system_log(self, text: str):
        """Appends a line to the central system log note."""
        # Note: ETAPI doesn't have a direct 'append' for content.
        # This is a stub for getting content, adding line, and patching.
        pass
