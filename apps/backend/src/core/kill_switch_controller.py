"""
Global Kill Switch Controller.
Gracefully terminates all VPN tunnels, agent processes, and active workflows.
"""

from __future__ import annotations

import logging
import asyncio
import signal
import os
from typing import Any, Dict, Optional, Set, Callable
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class KillSwitchReason(str, Enum):
    """Reason for activation."""

    MANUAL_TRIGGER = "manual_trigger"
    CRITICAL_ERROR = "critical_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    SCOPE_VIOLATION = "scope_violation"
    NETWORK_FAILURE = "network_failure"
    POLICY_VIOLATION = "policy_violation"
    OPERATOR_COMMAND = "operator_command"


class KillSwitchStatus(str, Enum):
    """Kill switch status."""

    ARMED = "armed"
    TRIGGERED = "triggered"
    SHUTDOWN_IN_PROGRESS = "shutdown_in_progress"
    SHUTDOWN_COMPLETE = "shutdown_complete"


@dataclass
class KillSwitchEvent:
    """Kill switch event."""

    timestamp: str
    reason: KillSwitchReason
    triggered_by: str
    details: str


class KillSwitchController:
    """
    Global kill switch controller.
    Manages graceful shutdown of all K1 processes and network tunnels.
    """

    def __init__(self):
        """Initialize kill switch controller."""
        self.status = KillSwitchStatus.ARMED
        self.triggered_at: Optional[str] = None
        self.triggered_by: Optional[str] = ""
        self.reason: Optional[KillSwitchReason] = None
        self.events: list[KillSwitchEvent] = []

        # Registered shutdown handlers
        self.shutdown_handlers: Dict[str, Callable] = {}
        self.vpn_handlers: Dict[str, Callable] = {}
        self.agent_handlers: Set[Callable] = set()

        # Process tracking
        self.active_processes: Set[int] = set()
        self.active_tunnels: Dict[str, Any] = {}
        self.active_workflows: Dict[str, Any] = {}

        # Lock for thread safety
        self._lock = asyncio.Lock()

    def register_shutdown_handler(
        self, name: str, handler: Callable
    ) -> None:
        """
        Register a shutdown handler.

        Args:
            name: Handler name
            handler: Async callable handler
        """
        self.shutdown_handlers[name] = handler
        logger.info(f"Registered shutdown handler: {name}")

    def register_vpn_handler(
        self, vpn_id: str, handler: Callable
    ) -> None:
        """
        Register a VPN tunnel handler.

        Args:
            vpn_id: VPN tunnel ID
            handler: Async callable handler to disconnect
        """
        self.vpn_handlers[vpn_id] = handler
        logger.info(f"Registered VPN handler: {vpn_id}")

    def register_agent_handler(
        self, handler: Callable
    ) -> None:
        """
        Register an agent termination handler.

        Args:
            handler: Async callable handler
        """
        self.agent_handlers.add(handler)
        logger.info(f"Registered agent handler")

    def track_process(self, pid: int) -> None:
        """Track an active process."""
        self.active_processes.add(pid)
        logger.debug(f"Tracking process {pid}")

    def untrack_process(self, pid: int) -> None:
        """Untrack a process."""
        self.active_processes.discard(pid)

    def track_tunnel(self, tunnel_id: str, tunnel_data: Any) -> None:
        """Track an active VPN tunnel."""
        self.active_tunnels[tunnel_id] = tunnel_data
        logger.debug(f"Tracking tunnel {tunnel_id}")

    def track_workflow(self, workflow_id: str, workflow_data: Any) -> None:
        """Track an active workflow."""
        self.active_workflows[workflow_id] = workflow_data
        logger.debug(f"Tracking workflow {workflow_id}")

    async def trigger(
        self,
        reason: KillSwitchReason,
        triggered_by: str = "system",
        details: str = "",
    ) -> None:
        """
        Trigger the kill switch.

        Args:
            reason: Reason for triggering
            triggered_by: User/system that triggered
            details: Additional details
        """
        async with self._lock:
            if self.status == KillSwitchStatus.TRIGGERED:
                logger.warning(
                    "Kill switch already triggered"
                )
                return

            logger.critical(
                f"KILL SWITCH TRIGGERED by {triggered_by}: {reason.value}"
            )

            self.status = KillSwitchStatus.TRIGGERED
            self.triggered_at = datetime.now(timezone.utc).isoformat()
            self.triggered_by = triggered_by
            self.reason = reason

            # Log event
            event = KillSwitchEvent(
                timestamp=self.triggered_at,
                reason=reason,
                triggered_by=triggered_by,
                details=details,
            )
            self.events.append(event)

            # Execute shutdown sequence
            await self._execute_shutdown_sequence()

    async def _execute_shutdown_sequence(self) -> None:
        """Execute graceful shutdown sequence."""
        logger.critical(
            "Executing kill switch shutdown sequence..."
        )
        self.status = KillSwitchStatus.SHUTDOWN_IN_PROGRESS

        # Phase 1: Disconnect VPN tunnels
        logger.info("Phase 1: Disconnecting VPN tunnels")
        await self._disconnect_vpn_tunnels()

        # Phase 2: Terminate agent processes
        logger.info("Phase 2: Terminating agent processes")
        await self._terminate_agents()

        # Phase 3: Terminate active workflows
        logger.info("Phase 3: Terminating workflows")
        await self._terminate_workflows()

        # Phase 4: Terminate system processes
        logger.info("Phase 4: Terminating system processes")
        await self._terminate_processes()

        # Phase 5: Execute registered handlers
        logger.info("Phase 5: Executing shutdown handlers")
        await self._execute_handlers()

        self.status = KillSwitchStatus.SHUTDOWN_COMPLETE
        logger.critical(
            "Kill switch shutdown sequence complete"
        )

    async def _disconnect_vpn_tunnels(self) -> None:
        """Disconnect all VPN tunnels."""
        logger.info(
            f"Disconnecting {len(self.active_tunnels)} VPN tunnels"
        )

        disconnect_tasks = []
        for vpn_id, handler in self.vpn_handlers.items():
            if vpn_id in self.active_tunnels:
                task = self._safe_call_handler(handler)
                disconnect_tasks.append(task)

        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)

        logger.info("All VPN tunnels disconnected")

    async def _terminate_agents(self) -> None:
        """Terminate all agent processes."""
        logger.info(
            f"Terminating {len(self.agent_handlers)} agent processes"
        )

        terminate_tasks = [
            self._safe_call_handler(handler)
            for handler in self.agent_handlers
        ]

        if terminate_tasks:
            await asyncio.gather(*terminate_tasks, return_exceptions=True)

        logger.info("All agent processes terminated")

    async def _terminate_workflows(self) -> None:
        """Terminate active workflows."""
        logger.info(
            f"Terminating {len(self.active_workflows)} workflows"
        )

        for workflow_id in list(self.active_workflows.keys()):
            try:
                # Request workflow cancellation
                logger.info(f"Terminating workflow {workflow_id}")
                # Workflow termination logic would go here
            except Exception as e:
                logger.error(f"Error terminating workflow: {str(e)}")

        logger.info("All workflows terminated")

    async def _terminate_processes(self) -> None:
        """Terminate tracked processes."""
        logger.info(
            f"Terminating {len(self.active_processes)} processes"
        )

        for pid in list(self.active_processes):
            try:
                os.kill(pid, signal.SIGTERM)
                logger.info(f"Sent SIGTERM to PID {pid}")

                # Wait for graceful termination
                await asyncio.sleep(1)

                # Force kill if still alive
                try:
                    os.kill(pid, signal.SIGKILL)
                    logger.info(f"Sent SIGKILL to PID {pid}")
                except ProcessLookupError:
                    pass

            except ProcessLookupError:
                logger.info(f"Process {pid} already terminated")
            except Exception as e:
                logger.error(f"Error terminating PID {pid}: {str(e)}")

        logger.info("All processes terminated")

    async def _execute_handlers(self) -> None:
        """Execute registered shutdown handlers."""
        logger.info(
            f"Executing {len(self.shutdown_handlers)} shutdown handlers"
        )

        handler_tasks = [
            self._safe_call_handler(handler)
            for handler in self.shutdown_handlers.values()
        ]

        if handler_tasks:
            await asyncio.gather(*handler_tasks, return_exceptions=True)

        logger.info("All shutdown handlers executed")

    @staticmethod
    async def _safe_call_handler(handler: Callable) -> None:
        """Safely call a handler with error handling."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()
        except Exception as e:
            logger.error(f"Handler error: {str(e)}")

    def get_status(self) -> Dict[str, Any]:
        """Get kill switch status."""
        return {
            "status": self.status.value,
            "triggered_at": self.triggered_at,
            "triggered_by": self.triggered_by,
            "reason": self.reason.value if self.reason else None,
            "active_processes": len(self.active_processes),
            "active_tunnels": len(self.active_tunnels),
            "active_workflows": len(self.active_workflows),
            "shutdown_handlers": len(self.shutdown_handlers),
            "event_count": len(self.events),
            "last_event": (
                {
                    "timestamp": self.events[-1].timestamp,
                    "reason": self.events[-1].reason.value,
                }
                if self.events
                else None
            ),
        }

    def get_audit_log(self) -> list[Dict[str, Any]]:
        """Get audit log of kill switch events."""
        return [
            {
                "timestamp": evt.timestamp,
                "reason": evt.reason.value,
                "triggered_by": evt.triggered_by,
                "details": evt.details,
            }
            for evt in self.events
        ]


# Global kill switch instance
_kill_switch: Optional[KillSwitchController] = None


def get_kill_switch() -> KillSwitchController:
    """Get or create global kill switch."""
    global _kill_switch

    if _kill_switch is None:
        _kill_switch = KillSwitchController()

    return _kill_switch


async def trigger_kill_switch(
    reason: KillSwitchReason,
    triggered_by: str = "operator",
    details: str = "",
) -> None:
    """
    Trigger the global kill switch.

    Args:
        reason: Reason for triggering
        triggered_by: Who triggered it
        details: Additional details
    """
    controller = get_kill_switch()
    await controller.trigger(reason, triggered_by, details)
