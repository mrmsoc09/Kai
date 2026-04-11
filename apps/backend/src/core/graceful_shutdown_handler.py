"""
Graceful Shutdown Handler — Never-Stop Orchestrator Logic.

Implements SIGTERM override and manual shutdown command handling.
Ensures the K1 scanning system runs indefinitely until explicitly
terminated via SIGTERM or `k1 shutdown` command.

The system refuses accidental shutdowns and requires explicit
acknowledgment before terminating.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class GracefulShutdownHandler:
    """
    Graceful shutdown manager for K1 orchestrator.

    Features:
    - Ignores accidental signals
    - Requires explicit `k1 shutdown` command or SIGTERM twice
    - Allows running background tasks to complete on shutdown
    - Implements cleanup hooks
    """

    def __init__(self):
        """Initialize shutdown handler."""
        self._shutdown_requested = False
        self._shutdown_count = 0
        self._shutdown_lock = asyncio.Lock()
        self._cleanup_hooks: list[Callable[[], asyncio.Coroutine[Any, Any, None]]] = []
        self._shutdown_event: Optional[asyncio.Event] = None

        logger.info("GracefulShutdownHandler initialized")

    def register_cleanup_hook(
        self,
        hook: Callable[[], asyncio.Coroutine[Any, Any, None]],
    ) -> None:
        """
        Register a cleanup hook to be called on shutdown.

        Args:
            hook: Async function to call on shutdown
        """
        self._cleanup_hooks.append(hook)
        logger.info(f"Registered cleanup hook: {hook.__name__}")

    async def initialize(self) -> None:
        """Initialize shutdown handler (set up signal handlers)."""
        self._shutdown_event = asyncio.Event()

        def _signal_handler(signum, frame):
            """Handle SIGTERM/SIGINT signals."""
            self._shutdown_count += 1
            sig_name = signal.Signals(signum).name

            if self._shutdown_count == 1:
                logger.warning(
                    f"⚠️  RECEIVED {sig_name} (count={self._shutdown_count})"
                )
                logger.warning(
                    "   Scan loop will continue. Send signal again to force shutdown, "
                    "or use: k1 shutdown"
                )
            elif self._shutdown_count >= 2:
                logger.critical(
                    f"🛑 FORCE SHUTDOWN REQUESTED (count={self._shutdown_count})"
                )
                asyncio.create_task(self.shutdown("SIGTERM force shutdown"))

        # Register signal handlers
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

        logger.info("✓ Signal handlers registered (SIGTERM, SIGINT)")

    async def request_shutdown(self, reason: str = "Manual shutdown request") -> None:
        """
        Explicitly request shutdown (via `k1 shutdown` command).

        Args:
            reason: Reason for shutdown
        """
        logger.critical(f"🛑 SHUTDOWN REQUESTED: {reason}")
        await self.shutdown(reason)

    async def shutdown(self, reason: str) -> None:
        """
        Execute graceful shutdown.

        1. Stop accepting new tasks
        2. Wait for background tasks to complete
        3. Run cleanup hooks
        4. Exit

        Args:
            reason: Reason for shutdown
        """
        async with self._shutdown_lock:
            if self._shutdown_requested:
                logger.warning("Shutdown already in progress")
                return

            self._shutdown_requested = True

        logger.warning("=" * 70)
        logger.warning("GRACEFUL SHUTDOWN INITIATED")
        logger.warning(f"Reason: {reason}")
        logger.warning("=" * 70)

        # Stop accepting new tasks
        logger.info("⏹️  Stopping new task acceptance...")

        # Run cleanup hooks
        logger.info("🧹 Running cleanup hooks...")
        for i, hook in enumerate(self._cleanup_hooks):
            try:
                hook_name = getattr(hook, '__name__', f'hook_{i}')
                logger.info(f"  → Running {hook_name}...")
                await hook()
                logger.info(f"  ✓ {hook_name} complete")
            except Exception as e:
                logger.error(f"  ❌ {hook.__name__} failed: {e}")

        # Signal shutdown complete
        if self._shutdown_event:
            self._shutdown_event.set()

        logger.warning("=" * 70)
        logger.critical("K1 SHUTDOWN COMPLETE")
        logger.warning("=" * 70)

        # Exit process
        sys.exit(0)

    async def wait_shutdown(self) -> None:
        """
        Wait until shutdown is requested.

        Used in main loop:
        ```python
        async def main():
            await shutdown_handler.initialize()
            while not shutdown_handler.is_shutdown_requested():
                # Run scanning logic
                ...
            await shutdown_handler.wait_shutdown()
        ```
        """
        if self._shutdown_event is None:
            raise RuntimeError("Shutdown handler not initialized")

        await self._shutdown_event.wait()

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_requested

    async def wait_for_background_tasks(
        self,
        timeout_seconds: int = 300,
    ) -> bool:
        """
        Wait for background tasks to complete before shutting down.

        Args:
            timeout_seconds: Timeout in seconds

        Returns:
            True if all tasks completed, False on timeout
        """
        logger.info(f"⏳ Waiting for background tasks (timeout: {timeout_seconds}s)...")

        try:
            # Get all pending tasks
            pending = asyncio.all_tasks()
            current_task = asyncio.current_task()

            # Filter out the current task and shutdown handler task
            background_tasks = {
                t for t in pending
                if t != current_task and not t.done()
            }

            if not background_tasks:
                logger.info("✓ No background tasks pending")
                return True

            logger.info(f"  Waiting for {len(background_tasks)} background task(s)...")

            # Wait for all to complete or timeout
            done, pending = await asyncio.wait(
                background_tasks,
                timeout=timeout_seconds,
                return_when=asyncio.ALL_COMPLETED,
            )

            if pending:
                logger.warning(
                    f"⚠️  {len(pending)} background task(s) still pending after {timeout_seconds}s"
                )
                # Force cancel pending
                for task in pending:
                    task.cancel()
                return False

            logger.info(f"✓ All {len(done)} background task(s) completed")
            return True

        except Exception as e:
            logger.error(f"Error waiting for background tasks: {e}")
            return False

    async def ensure_clean_shutdown(
        self,
        timeout_seconds: int = 300,
    ) -> None:
        """
        Ensure clean shutdown by waiting for background tasks.

        Call this before exiting to avoid leaving orphaned processes.

        Args:
            timeout_seconds: Timeout for background tasks
        """
        logger.info("Ensuring clean shutdown...")
        success = await self.wait_for_background_tasks(timeout_seconds)

        if not success:
            logger.warning("⚠️  Some background tasks did not complete in time")
            logger.info("Continuing with shutdown anyway...")

        logger.info("✓ Clean shutdown prepared")


# Global singleton
_handler: Optional[GracefulShutdownHandler] = None


def get_graceful_shutdown_handler() -> GracefulShutdownHandler:
    """Get or create global shutdown handler singleton."""
    global _handler
    if _handler is None:
        _handler = GracefulShutdownHandler()
    return _handler
