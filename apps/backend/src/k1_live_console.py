from __future__ import annotations

import json
import os
import time
import asyncio
from datetime import datetime
from pathlib import Path
from collections import deque
from typing import Any, Dict, List

from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.console import Console, Group
from rich.align import Align

# --- Configuration ---
LOGS_DIR = Path("logs")
TELEMETRY_PATH = LOGS_DIR / "telemetry.jsonl"
ALERTS_PATH = LOGS_DIR / "alerts.log"

# Max lines to keep in memory for display
MAX_TELEMETRY_ROWS = 15
MAX_ALERTS_ROWS = 20

# Global state
telemetry_data: deque = deque(maxlen=MAX_TELEMETRY_ROWS)
alerts_data: deque = deque(maxlen=MAX_ALERTS_ROWS)
ralph_stats = {
    "total_requests": 0,
    "waf_blocks": 0,
    "current_payload": "None",
    "last_active": "Never"
}

console = Console()

class LogTailer:
    """Asynchronous file tailer for continuous log monitoring."""
    def __init__(self, path: Path, callback):
        self.path = path
        self.callback = callback
        self._last_size = 0

    async def tail(self):
        while True:
            if self.path.exists():
                current_size = self.path.stat().st_size
                if current_size < self._last_size:
                    # File rotated or truncated
                    self._last_size = 0
                
                if current_size > self._last_size:
                    with open(self.path, "r", encoding="utf-8") as f:
                        f.seek(self._last_size)
                        lines = f.readlines()
                        for line in lines:
                            await self.callback(line.strip())
                        self._last_size = f.tell()
            
            await asyncio.sleep(0.5)

async def handle_telemetry(line: str):
    try:
        data = json.loads(line)
        telemetry_data.append(data)
        
        # Update Ralph stats if the telemetry is from RalphFuzzer
        if "ralph" in data.get("node", "").lower():
            ralph_stats["last_active"] = datetime.now().strftime("%H:%M:%S")
            # In a real scenario, we'd extract specific stats from the result update
            # For now, we increment request count based on node execution
            ralph_stats["total_requests"] += 1
    except Exception:
        pass

async def handle_alerts(line: str):
    # Basic alert parsing
    # Expected format: [TIMESTAMP] LEVEL: Message or similar
    alerts_data.append(line)
    
    # Heuristic for Ralph Wiggum specific blocks
    if "FAIL" in line or "403" in line or "WAF" in line:
        ralph_stats["waf_blocks"] += 1
    if "Fuzzing with payload" in line:
        # Extract payload from log line if possible
        parts = line.split("payload): ")
        if len(parts) > 1:
            ralph_stats["current_payload"] = parts[1][:30] + "..."

def make_layout() -> Layout:
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=10)
    )
    layout["main"].split_row(
        Layout(name="left", ratio=2),
        Layout(name="right", ratio=1)
    )
    return layout

def get_header() -> Panel:
    curr_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    war_chest = vault.get_war_chest_total()
    header_text = Text.assemble(
        ("K1 COMMAND GLASS v1.0.0", "bold cyan"),
        " | ",
        (curr_time, "white"),
        " | ",
        ("WAR CHEST: ", "bold gold1"),
        (f"${war_chest:,.2f}", "gold1"),
        " | ",
        ("Sovereign Status: ", "white"),
        ("ONLINE", "bold green blink")
    )
    return Panel(Align.center(header_text), style="blue")

def get_telemetry_table() -> Panel:
    table = Table(expand=True, box=None)
    table.add_column("Node", style="white")
    table.add_column("Latency", justify="right")
    table.add_column("Memory", justify="right")
    table.add_column("Status", justify="center")

    for entry in list(telemetry_data):
        ms = entry.get("execution_ms", 0)
        mem = entry.get("peak_memory_mb", 0)
        node = entry.get("node", "unknown")
        
        # Visual Cues for Latency
        if ms < 50:
            ms_style = "cyan"
            status = "OPTIMIZED"
        elif ms > 2000:
            ms_style = "bold red"
            status = "HEAVY"
        elif ms > 500:
            ms_style = "yellow"
            status = "STRESSED"
        else:
            ms_style = "white"
            status = "NORMAL"

        table.add_row(
            node,
            f"[{ms_style}]{ms}ms[/]",
            f"{mem:.2f}MB",
            f"[{ms_style}]{status}[/]"
        )

    return Panel(table, title="[bold]Node Telemetry (Last 15)[/]", border_style="cyan")

def get_ralph_panel() -> Panel:
    stats_text = Text.assemble(
        ("Active Instances: ", "white"), ("25", "bold green"), "\n",
        ("Total Requests:  ", "white"), (str(ralph_stats["total_requests"]), "bold cyan"), "\n",
        ("WAF Blocks:      ", "white"), (str(ralph_stats["waf_blocks"]), "bold red"), "\n",
        ("Last Pulse:      ", "white"), (ralph_stats["last_active"], "yellow"), "\n\n",
        ("Current Profile: ", "white"), ("\n"),
        (ralph_stats["current_payload"], "dim italic gray")
    )
    return Panel(stats_text, title="[bold]Ralph Fuzzer Status[/]", border_style="green")

def get_alerts_pane() -> Panel:
    # Reverse alerts to show newest at top or scroll properly
    lines = []
    for line in list(alerts_data):
        style = "white"
        if "CRITICAL" in line.upper():
            style = "bold red blink"
        elif "POC" in line.upper() or "SUCCESS" in line.upper() or "VERIFIED" in line.upper():
            style = "bold green"
        elif "INFO" in line.upper():
            style = "blue"
        elif "WARNING" in line.upper():
            style = "yellow"
        
        lines.append(Text(line, style=style))
    
    return Panel(Group(*lines), title="[bold]Mission Alerts & Findings[/]", border_style="blue")

async def run_tui():
    layout = make_layout()
    
    telemetry_tailer = LogTailer(TELEMETRY_PATH, handle_telemetry)
    alerts_tailer = LogTailer(ALERTS_PATH, handle_alerts)
    
    # Start background tailing
    asyncio.create_task(telemetry_tailer.tail())
    asyncio.create_task(alerts_tailer.tail())

    with Live(layout, refresh_per_second=4, screen=True):
        while True:
            layout["header"].update(get_header())
            layout["left"].update(get_telemetry_table())
            layout["right"].update(get_ralph_panel())
            layout["footer"].update(get_alerts_pane())
            await asyncio.sleep(0.25)

if __name__ == "__main__":
    try:
        asyncio.run(run_tui())
    except KeyboardInterrupt:
        pass
