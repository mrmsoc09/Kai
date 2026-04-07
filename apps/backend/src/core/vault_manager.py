from __future__ import annotations

import os
import re
import json
import sqlite3
import logging
import asyncio
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class VaultManager:
    """
    K1 Stage 19: Vault & Logistics Manager.
    Tracks achievements, payouts, and manages PGP-encrypted reward logistics.
    """

    DB_PATH = Path("data/vault.db")
    LOGS_PATH = Path("logs/alerts.log")
    LOGISTICS_DIR = Path("logistics")
    
    MILESTONES = [10000, 50000, 100000]
    
    RALPH_QUOTES = [
        "I'm a financial advisor!",
        "My war chest tastes like pennies!",
        "I'm learning about compounding interest!",
        "Is this enough for a new red crayon?",
        "Yay! Capitalist victory!"
    ]

    def __init__(self):
        self._init_db()
        self._last_processed_line = 0
        self._running = False

    def _init_db(self):
        """Initializes the SQLite ledger."""
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vault_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id TEXT,
                    entry_type TEXT, -- FINDING or PAYOUT
                    amount REAL DEFAULT 0,
                    label TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE TABLE IF NOT EXISTS milestones (milestone REAL PRIMARY KEY, reached_at DATETIME)")

    def get_war_chest_total(self) -> float:
        """Calculates the total USD earned."""
        with sqlite3.connect(self.DB_PATH) as conn:
            row = conn.execute("SELECT SUM(amount) FROM vault_ledger WHERE entry_type='PAYOUT'").fetchone()
            return row[0] if row[0] else 0.0

    async def start_monitoring(self):
        """Starts the log tailer for payout detection."""
        self._running = True
        logger.info("VaultManager: Monitoring alerts for payout events...")
        while self._running:
            await self._process_logs()
            await asyncio.sleep(5)

    async def _process_logs(self):
        """Tails the alerts log for specific bounty strings."""
        if not self.LOGS_PATH.exists():
            return

        # Simple tail logic
        with open(self.LOGS_PATH, "r") as f:
            lines = f.readlines()
            # In a real impl, we'd store the offset. For K1, we'll scan for new entries.
            # (Simplified for the TUI context)
            for line in lines:
                await self._parse_line(line)

    async def _parse_line(self, line: str):
        """Detects findings and payouts via regex."""
        # Detect Payout: 💰 BOUNTY CONFIRMED: $5000
        payout_match = re.search(r"BOUNTY CONFIRMED: \$(\d+)", line)
        if payout_match:
            amount = float(payout_match.group(1))
            await self._record_entry("PAYOUT", amount, line)
            await self._check_milestones()

        # Detect Finding: ✅ VULNERABILITY VERIFIED
        elif "VULNERABILITY VERIFIED" in line:
            await self._record_entry("FINDING", 0.0, line)

    async def _record_entry(self, entry_type: str, amount: float, raw_line: str):
        """Commits an event to the ledger."""
        with sqlite3.connect(self.DB_PATH) as conn:
            # Check if this line was already processed (simplified dedupe)
            exists = conn.execute("SELECT 1 FROM vault_ledger WHERE label = ?", (raw_line.strip(),)).fetchone()
            if not exists:
                conn.execute("INSERT INTO vault_ledger (entry_type, amount, label) VALUES (?, ?, ?)",
                            (entry_type, amount, raw_line.strip()))
                logger.info(f"Vault: Recorded {entry_type} - ${amount}")

    async def _check_milestones(self):
        """Checks if a milestone threshold has been crossed."""
        total = self.get_war_chest_total()
        for m in self.MILESTONES:
            if total >= m:
                with sqlite3.connect(self.DB_PATH) as conn:
                    reached = conn.execute("SELECT 1 FROM milestones WHERE milestone = ?", (m,)).fetchone()
                    if not reached:
                        conn.execute("INSERT INTO milestones (milestone, reached_at) VALUES (?, ?)", 
                                    (m, datetime.now(UTC).isoformat()))
                        logger.critical(f"VAULT_MILESTONE_UNLOCKED: ${m} Milestone Reached!")
                        # Trigger Frontend Event (Mock)
                        # trigger_payout_animation(type='bounty', milestone=m)

    def save_redemption(self, encrypted_blob: str):
        """Saves a PGP-encrypted address to the logistics folder."""
        self.LOGISTICS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        file_path = self.LOGISTICS_DIR / f"pending_shipment_{timestamp}.gpg"
        
        with open(file_path, "w") as f:
            f.write(encrypted_blob)
        
        logger.info(f"Vault: Redemption stored at {file_path}. Zero-knowledge integrity preserved.")

# --- FastAPI Integration Stubs ---
# @app.post("/api/vault/redeem")
# async def redeem_milestone(blob: str):
#     vault.save_redemption(blob)
#     return {"status": "success", "message": "Address queued for shipment"}
