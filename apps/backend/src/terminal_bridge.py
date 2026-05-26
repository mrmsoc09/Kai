from __future__ import annotations

import os
import pty
import select
import asyncio
import logging
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class TerminalBridge:
    """
    Bridges a local PTY (running Tmux) to a WebSocket for the React frontend.
    """
    def __init__(self):
        self.fd = None
        self.child_pid = None

    def spawn_terminal(self):
        self.child_pid, self.fd = pty.fork()
        if self.child_pid == 0:
            # Child process
            # Attempt to attach to k1_main tmux session, or create it
            os.execvpe("tmux", ["tmux", "new-session", "-A", "-s", "k1_main", "python3", "apps/backend/src/k1_live_console.py"], os.environ)
        else:
            # Parent process
            logger.info(f"Terminal PTY spawned with PID {self.child_pid}")

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.spawn_terminal()

        async def read_from_pty():
            while True:
                await asyncio.sleep(0.01)
                if self.fd:
                    timeout = 0
                    [r, _, _] = select.select([self.fd], [], [], timeout)
                    if r:
                        output = os.read(self.fd, 1024)
                        await websocket.send_bytes(output)

        async def write_to_pty():
            try:
                while True:
                    data = await websocket.receive_bytes()
                    if self.fd:
                        os.write(self.fd, data)
            except WebSocketDisconnect:
                logger.info("Terminal WebSocket disconnected.")

        await asyncio.gather(read_from_pty(), write_to_pty())


async def terminal_websocket(websocket: WebSocket) -> None:
    """Standalone entrypoint imported by main.py for the /ws/terminal route."""
    bridge = TerminalBridge()
    await bridge.connect(websocket)
