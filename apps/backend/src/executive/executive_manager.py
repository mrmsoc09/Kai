from __future__ import annotations

import logging
import os
import signal
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schemas import BountyWalletRegistry
from .payout_ledger import verify_bounty, list_payout_records

logger = logging.getLogger(__name__)


class ExecutiveManager:
    """
    K1 Executive Layer Manager.
    Handles Global/Local Kill Switches, Financial Mirrors, and V-RAD Silent Mode.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ExecutiveManager, cls).__new__(cls)
            cls._instance._silent_mode = os.getenv("K1_V_RAD_SILENT_MODE", "false").lower() == "true"
            cls._instance._active_subprocess_groups: set[int] = set()
        return cls._instance

    def toggle_silent_mode(self, enabled: bool) -> bool:
        """Visual Synthesis: bypass visual animations to save resources."""
        self._silent_mode = enabled
        logger.info(f"Executive Control: V-RAD Silent Mode set to {enabled}")
        return self._silent_mode

    @property
    def silent_mode(self) -> bool:
        return self._silent_mode

    def register_process_group(self, pgid: int) -> None:
        self._active_subprocess_groups.add(pgid)

    def unregister_process_group(self, pgid: int) -> None:
        if pgid in self._active_subprocess_groups:
            self._active_subprocess_groups.remove(pgid)

    def global_emergency_stop(self) -> dict[str, Any]:
        """
        Global Emergency Stop (K1Stop):
        - Sends SIGKILL to all active subprocess groups.
        - Clears volatile memory directories.
        - Drops SNL tunnels (via command).
        """
        results = {
            "timestamp": datetime.now(UTC).isoformat(),
            "processes_killed": 0,
            "snl_tunnels_dropped": False,
            "volatile_memory_cleared": False,
        }

        # 1. Kill Subprocesses
        for pgid in list(self._active_subprocess_groups):
            try:
                os.killpg(pgid, signal.SIGKILL)
                results["processes_killed"] += 1
            except Exception as e:
                logger.error(f"Kill Switch: Failed to kill process group {pgid}: {e}")
        self._active_subprocess_groups.clear()

        # 2. Drop SNL Tunnel
        try:
            # Placeholder for platform-specific SNL drop command
            subprocess.run(["k1-snl-stop"], check=False, capture_output=True)
            results["snl_tunnels_dropped"] = True
        except Exception as e:
            logger.error(f"Kill Switch: Failed to drop SNL tunnel: {e}")

        # 3. Clear Volatile Memory
        tmp_root = Path(os.getenv("K1_VOLATILE_ROOT", "/home/k1-admin/.gemini/tmp/k1-admin"))
        if tmp_root.exists():
            try:
                import shutil
                shutil.rmtree(tmp_root)
                tmp_root.mkdir(parents=True, exist_ok=True)
                results["volatile_memory_cleared"] = True
            except Exception as e:
                logger.error(f"Kill Switch: Failed to clear volatile memory: {e}")

        logger.critical("K1 GLOBAL EMERGENCY STOP EXECUTED.")
        return results

    def terminate_tool_instance(self, pgid: int, reason: str = "Resource Limit Exceeded") -> bool:
        """Per-Scan Isolation: Kill specific tool instance."""
        try:
            os.killpg(pgid, signal.SIGKILL)
            self.unregister_process_group(pgid)
            logger.warning(f"Local Kill Switch: PGID {pgid} terminated. Reason: {reason}")
            return True
        except Exception as e:
            logger.error(f"Local Kill Switch: Failed to terminate {pgid}: {e}")
            return False

    def get_financial_summary(self) -> dict[str, Any]:
        """Aggregation of Dual-Ledger wallet status."""
        records = list_payout_records()
        expected = sum(r.get("expected_amount", 0.0) for r in records)
        validated = sum(r.get("validated_amount", 0.0) for r in records)
        
        return {
            "total_bounties": len(records),
            "total_expected_usd": expected,
            "total_validated_usd": validated,
            "pending_validation_usd": expected - validated,
            "wallet_health": "SYNCED" if expected == validated else "PENDING_CREDITS",
        }
