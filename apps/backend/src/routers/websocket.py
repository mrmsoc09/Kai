"""WebSocket handlers for real-time scan monitoring and log streaming.

Provides WebSocket endpoints for:
- Real-time scan status updates
- Real-time log streaming
- System health broadcasting
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Set
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.hil_db import get_db
from ..models.findings import ScanExecution

logger = logging.getLogger(__name__)
router = APIRouter()

# Store active WebSocket connections
class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.scans_connections: Dict[str, Set[WebSocket]] = {}
        self.logs_connections: Dict[str, Set[WebSocket]] = {}
        self.active_broadcast_tasks: Dict[str, asyncio.Task] = {}

    async def connect_to_scans(self, websocket: WebSocket) -> None:
        """Accept a WebSocket connection to scan updates."""
        await websocket.accept()
        if "scans" not in self.scans_connections:
            self.scans_connections["scans"] = set()
        self.scans_connections["scans"].add(websocket)
        logger.info(f"WebSocket connected to scans: {len(self.scans_connections['scans'])} total")

    async def connect_to_logs(self, scan_id: str, websocket: WebSocket) -> None:
        """Accept a WebSocket connection for log streaming."""
        await websocket.accept()
        if scan_id not in self.logs_connections:
            self.logs_connections[scan_id] = set()
        self.logs_connections[scan_id].add(websocket)
        logger.info(f"WebSocket connected to logs {scan_id}: {len(self.logs_connections[scan_id])} total")

    async def disconnect_from_scans(self, websocket: WebSocket) -> None:
        """Remove a WebSocket from scan updates."""
        if "scans" in self.scans_connections:
            self.scans_connections["scans"].discard(websocket)
            logger.info(f"WebSocket disconnected from scans: {len(self.scans_connections['scans'])} remaining")

    async def disconnect_from_logs(self, scan_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket from log streaming."""
        if scan_id in self.logs_connections:
            self.logs_connections[scan_id].discard(websocket)
            logger.info(f"WebSocket disconnected from logs {scan_id}: {len(self.logs_connections[scan_id])} remaining")
            if not self.logs_connections[scan_id]:
                del self.logs_connections[scan_id]

    async def broadcast_scan_update(self, scan_id: str, scan_data: dict) -> None:
        """Broadcast scan update to all connected clients."""
        if "scans" not in self.scans_connections:
            return

        dead_connections = []
        for connection in self.scans_connections["scans"]:
            try:
                await connection.send_json(
                    {"type": "scan_update", "scan_id": scan_id, "scan": scan_data}
                )
            except Exception as e:
                logger.error(f"Failed to broadcast scan update: {e}")
                dead_connections.append(connection)

        for connection in dead_connections:
            self.scans_connections["scans"].discard(connection)

    async def broadcast_scan_completed(self, scan_id: str, findings_count: int) -> None:
        """Broadcast scan completion to all connected clients."""
        if "scans" not in self.scans_connections:
            return

        dead_connections = []
        for connection in self.scans_connections["scans"]:
            try:
                await connection.send_json(
                    {"type": "scan_completed", "scan_id": scan_id, "findings_count": findings_count}
                )
            except Exception as e:
                logger.error(f"Failed to broadcast scan completion: {e}")
                dead_connections.append(connection)

        for connection in dead_connections:
            self.scans_connections["scans"].discard(connection)

    async def stream_log_entry(self, scan_id: str, log_entry: dict) -> None:
        """Stream log entry to all clients watching this scan."""
        if scan_id not in self.logs_connections:
            return

        dead_connections = []
        for connection in self.logs_connections[scan_id]:
            try:
                await connection.send_json({"type": "log_entry", "entry": log_entry})
            except Exception as e:
                logger.error(f"Failed to stream log entry: {e}")
                dead_connections.append(connection)

        for connection in dead_connections:
            self.logs_connections[scan_id].discard(connection)

    async def stream_log_batch(self, scan_id: str, log_entries: List[dict]) -> None:
        """Stream multiple log entries to all clients watching this scan."""
        if scan_id not in self.logs_connections:
            return

        dead_connections = []
        for connection in self.logs_connections[scan_id]:
            try:
                await connection.send_json({"type": "log_batch", "entries": log_entries})
            except Exception as e:
                logger.error(f"Failed to stream log batch: {e}")
                dead_connections.append(connection)

        for connection in dead_connections:
            self.logs_connections[scan_id].discard(connection)


manager = ConnectionManager()


@router.websocket("/ws/scans")
async def websocket_scans(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time scan updates.

    Clients connect here to receive real-time updates about all active scans.
    Updates include status changes, phase progress, findings count, etc.
    """
    await manager.connect_to_scans(websocket)

    try:
        while True:
            # Keep connection alive by listening for ping/pong
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                logger.debug(f"Received non-JSON data: {data}")

    except WebSocketDisconnect:
        await manager.disconnect_from_scans(websocket)
        logger.info("WebSocket disconnected from scans")
    except Exception as e:
        logger.error(f"WebSocket error (scans): {e}")
        await manager.disconnect_from_scans(websocket)


@router.websocket("/ws/logs/{scan_id}")
async def websocket_logs(websocket: WebSocket, scan_id: str) -> None:
    """WebSocket endpoint for real-time log streaming.

    Clients connect here with a specific scan_id to receive real-time logs
    from that scan. Logs are streamed as they are generated.

    Args:
        websocket: WebSocket connection
        scan_id: UUID of the scan to stream logs for
    """
    await manager.connect_to_logs(scan_id, websocket)

    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                logger.debug(f"Received non-JSON data: {data}")

    except WebSocketDisconnect:
        await manager.disconnect_from_logs(scan_id, websocket)
        logger.info(f"WebSocket disconnected from logs {scan_id}")
    except Exception as e:
        logger.error(f"WebSocket error (logs {scan_id}): {e}")
        await manager.disconnect_from_logs(scan_id, websocket)


# Helper functions for broadcasting from other parts of the application


async def broadcast_scan_status_update(scan_id: str, scan_data: dict) -> None:
    """Broadcast a scan status update to all connected clients.

    Args:
        scan_id: UUID of the scan
        scan_data: Dictionary containing scan status and metadata
    """
    await manager.broadcast_scan_update(scan_id, scan_data)


async def broadcast_log_entry(scan_id: str, level: str, message: str, source: str = "system") -> None:
    """Broadcast a single log entry to clients watching a scan.

    Args:
        scan_id: UUID of the scan
        level: Log level (info, warning, error, success, debug)
        message: Log message
        source: Source of the log (default: system)
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "source": source,
    }
    await manager.stream_log_entry(scan_id, log_entry)


async def broadcast_log_batch(scan_id: str, entries: List[dict]) -> None:
    """Broadcast multiple log entries to clients watching a scan.

    Args:
        scan_id: UUID of the scan
        entries: List of log entry dictionaries
    """
    await manager.stream_log_batch(scan_id, entries)


async def broadcast_scan_completed(scan_id: str, findings_count: int) -> None:
    """Broadcast scan completion to all connected clients.

    Args:
        scan_id: UUID of the completed scan
        findings_count: Total number of findings discovered
    """
    await manager.broadcast_scan_completed(scan_id, findings_count)
