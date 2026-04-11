"""
Background Evidence Dispatcher — Non-Blocking Evidence Generation.

Implements async task forking to dispatch evidence collection (recording,
script generation, bundling) as independent background tasks.

The scanner loop is NOT blocked waiting for evidence generation to complete.
Instead, findings are moved to AWAITING_REVIEW queue and evidence is
collected in parallel background tasks.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BackgroundEvidenceDispatcher:
    """
    Dispatcher for non-blocking evidence generation tasks.

    Spawns evidence collection as independent asyncio tasks, allowing
    the main scanner loop to continue unblocked.
    """

    def __init__(self):
        """Initialize dispatcher."""
        self._active_tasks: Dict[str, asyncio.Task[Any]] = {}
        self._task_lock = asyncio.Lock()
        logger.info("BackgroundEvidenceDispatcher initialized")

    async def dispatch_evidence_collection(
        self,
        finding_id: str,
        task_id: str,
        target_url: str,
        vulnerability_type: str,
        severity: str,
        tool_name: str,
        evidence: Dict[str, Any],
        evidence_fn: callable,
        status_tracker: Any,
    ) -> str:
        """
        Dispatch evidence collection as a background task (non-blocking).

        Args:
            finding_id: Finding identifier
            task_id: Task identifier
            target_url: Target URL
            vulnerability_type: Vulnerability type
            severity: Severity level
            tool_name: Tool that detected it
            evidence: Evidence data
            evidence_fn: Async function to call for evidence collection
            status_tracker: FindingStatusTracker instance

        Returns:
            Task ID of the spawned background task
        """
        task_name = f"evidence_{finding_id}"

        # Create background coroutine
        async def _collect_evidence_background():
            """Background task for evidence collection."""
            try:
                logger.info(f"📋 Background task {task_name}: Starting evidence collection for {finding_id}")

                # Mark as EVIDENCE_COLLECTING
                await status_tracker.start_evidence_collection(finding_id)

                # Call evidence collection function (non-blocking)
                # evidence_fn should handle all parameters it needs
                result = await evidence_fn()

                # Mark as AWAITING_REVIEW (evidence complete)
                await status_tracker.complete_evidence_collection(finding_id)

                logger.info(f"✅ Background task {task_name}: Evidence collection complete")
                return result

            except Exception as e:
                logger.error(f"❌ Background task {task_name}: Error during evidence collection: {e}")
                raise
            finally:
                # Clean up task reference
                async with self._task_lock:
                    if task_name in self._active_tasks:
                        del self._active_tasks[task_name]

        # Spawn as background task (non-blocking)
        task = asyncio.create_task(_collect_evidence_background())

        # Store reference for tracking
        async with self._task_lock:
            self._active_tasks[task_name] = task

        logger.warning(
            f"🔀 Dispatched to background: {finding_id} "
            f"(evidence_collecting_task_id={task_name})"
        )

        # CRITICAL: Return immediately without waiting
        # This allows the scanner loop to continue
        return task_name

    async def wait_for_task(self, task_name: str, timeout_seconds: Optional[int] = None) -> Any:
        """
        Wait for a background task to complete.

        Args:
            task_name: Name of the task to wait for
            timeout_seconds: Optional timeout in seconds

        Returns:
            Result of the background task
        """
        async with self._task_lock:
            task = self._active_tasks.get(task_name)

        if task is None:
            raise ValueError(f"Task not found: {task_name}")

        try:
            if timeout_seconds:
                result = await asyncio.wait_for(task, timeout=timeout_seconds)
            else:
                result = await task
            return result
        except asyncio.TimeoutError:
            logger.error(f"Task {task_name} timed out after {timeout_seconds}s")
            raise

    async def get_active_tasks(self) -> Dict[str, str]:
        """Get all active background tasks."""
        async with self._task_lock:
            return {
                name: str(task)
                for name, task in self._active_tasks.items()
            }

    async def cancel_task(self, task_name: str) -> bool:
        """Cancel a background task."""
        async with self._task_lock:
            task = self._active_tasks.get(task_name)

        if task is None:
            return False

        task.cancel()
        logger.warning(f"Cancelled background task: {task_name}")

        try:
            await task
        except asyncio.CancelledError:
            pass

        return True

    async def wait_all_tasks(self, timeout_seconds: Optional[int] = None) -> list[Any]:
        """
        Wait for all active background tasks to complete.

        Args:
            timeout_seconds: Optional timeout in seconds

        Returns:
            List of task results
        """
        async with self._task_lock:
            tasks = list(self._active_tasks.values())

        if not tasks:
            return []

        logger.info(f"Waiting for {len(tasks)} background tasks to complete...")

        try:
            if timeout_seconds:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout_seconds
                )
            else:
                results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
        except asyncio.TimeoutError:
            logger.error(f"Waiting for background tasks timed out after {timeout_seconds}s")
            raise

    async def get_stats(self) -> Dict[str, int]:
        """Get dispatcher statistics."""
        async with self._task_lock:
            return {
                "active_tasks": len(self._active_tasks),
                "task_names": list(self._active_tasks.keys()),
            }


# Global singleton
_dispatcher: Optional[BackgroundEvidenceDispatcher] = None


def get_background_evidence_dispatcher() -> BackgroundEvidenceDispatcher:
    """Get or create global dispatcher singleton."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = BackgroundEvidenceDispatcher()
    return _dispatcher
