"""API Keys Orchestrator — Daily 6AM planning of API key usage across scan queue.

Runs daily at 6AM (PT) to:
1. Load all 55 API keys from Vault
2. Query quota limits for each service
3. Calculate daily allocation per scan queue entry
4. Distribute quotas to prevent bottlenecks
5. Enforce queue length limits

Public interface::

    orchestrator = APIKeysOrchestrator()
    await orchestrator.run(db)  # Called by beat task daily at 6AM PT
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class APIKeysOrchestrator:
    """
    Daily 6AM planning orchestrator for API key allocation.

    Integrates with:
    - Vault (55 loaded API keys)
    - OpportunityScanPool (scan queue entries)
    - ScanQueueRotator (queue advancement)
    """

    # Default daily quotas for each API provider (conservative estimates)
    DEFAULT_QUOTAS = {
        # AI/LLM Providers
        "OPENAI_API_KEY": 5000,
        "ANTHROPIC_API_KEY": 3000,
        "GEMINI_API_KEY": 4000,
        "GROQ_API_KEY": 2000,
        "MISTRAL_API_KEY": 2000,
        "PERPLEXITY_API_KEY": 1000,
        "OPENROUTER_API_KEY": 3000,
        "DEEPSEEK_API_KEY": 2000,
        "LITELLM_API_KEY": 5000,
        "AIMLAPI_API_KEY": 1000,
        "VERTEX_API_KEY": 3000,

        # OSINT Tools
        "SHODAN_API_KEY": 100,
        "FULLHUNT_API_KEY": 100,
        "ABUSEIPDB_API_KEY": 300,
        "LEAKIX_API_KEY": 500,
        "ZOOMEYE_API_KEY": 300,
        "HUNTER_API_KEY": 25,
        "DEHASHED_API_KEY": 100,
        "INTELX_API_KEY": 500,
        "ABUSE_CH_API_KEY": 200,
        "GRAYHATWARFARE_API_KEY": 200,

        # Search & Lookup
        "CENSYS_API_KEY": 250,
        "CENSYS_UID": 250,
        "CENSYS_SECRET": 250,
        "URLSCAN_API_KEY": 1000,
        "IPINFO_API_KEY": 1000,
        "PROJECTDISCOVERY_API_KEY": 500,
        "PROJECTDISCOVERY_TEAM_ID": 500,
        "SECURITYTRAILS_API_KEY": 500,

        # Security Tools
        "VIRUSTOTAL_API_KEY": 500,
        "OTX_API_KEY": 1000,
        "NVD_API_KEY": 2000,

        # BugBounty Platforms
        "HACKERONE_API_KEY": 100,
        "INTIGRITI_API_KEY": 100,

        # Communication
        "X_API_KEY": 300,
        "X_COM_BEARER_TOKEN": 300,
        "X_COM_ACCESS_TOKEN": 300,
        "X_COM_ACCESS_TOKEN_SECRET": 300,
        "X_COM_APP_ID": 300,
        "X_COM_SECRET": 300,
        "TWILIO_API_KEY": 500,
        "PROTON_API_KEY": 100,

        # Developer Tools
        "GITHUB_API_KEY": 5000,
        "GITHUB_USERNAME": 5000,
        "GOOGLE_API_KEY": 3000,
        "GOOGLE_WORKSPACE": 3000,
        "HUGGINGFACE_API_KEY": 1000,
        "GITKRAKEN_API_KEY": 100,
        "AGENTOPS_API_KEY": 500,
        "COINBASE_ID": 100,
        "COINBASE_ID_SECRET": 100,

        # Other Services
        "DEEPL_API_KEY": 500,
        "SERP_API_KEY": 300,
        "SERPER_DEV_API_KEY": 300,
    }

    RESERVE_RATIO = 0.15  # Reserve 15% of quota for peak demand
    OUTPUT_DIR = Path("artifacts/api_key_allocations")
    ALLOCATION_SUMMARY_PATH = Path(
        "artifacts/api_key_allocations/daily_allocation_summary.json"
    )
    QUEUE_STATUS_PATH = Path(
        "artifacts/api_key_allocations/queue_status.json"
    )

    # Queue length restrictions (prevent bottlenecks)
    MAX_QUEUE_LENGTH = 100
    MIN_QUEUE_LENGTH = 5
    TARGET_QUEUE_LENGTH = 50

    def __init__(self):
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async def run(self, db: Any) -> None:
        """Main entry point. Called by Celery beat daily at 6AM PT."""
        logger.info("API Keys Orchestrator starting (6AM daily planning)")
        try:
            # Load API keys from Vault
            api_keys = self._load_api_keys_from_vault()

            # Get current scan queue
            scan_entries = await self._get_scan_queue_entries(db)

            # Calculate quota allocations
            allocations = self._calculate_allocations(
                api_keys, scan_entries
            )

            # Check queue length and enforce limits
            queue_status = await self._check_and_enforce_queue_limits(
                db, len(scan_entries)
            )

            # Write allocation plan
            self._write_allocation_plan(
                allocations, scan_entries, queue_status
            )

            logger.info(
                "API Keys Orchestration complete. "
                "%d scan entries planned, %d keys available, "
                "queue_length=%d (limit=%d)",
                len(scan_entries),
                len(api_keys),
                queue_status.get("current_length", 0),
                self.MAX_QUEUE_LENGTH,
            )
        except Exception as e:
            logger.error("API Keys Orchestrator failed: %s", e)
            self._write_default_allocation()

    def _load_api_keys_from_vault(self) -> dict[str, dict]:
        """Load all 55 API keys from Vault via SecretManager."""
        from .secret_manager import get_secret_manager

        api_keys: dict[str, dict] = {}
        sm = get_secret_manager()

        for key_name, default_quota in self.DEFAULT_QUOTAS.items():
            try:
                # Try to get key from Vault/environment
                secret_value = sm.get_optional(key_name)
                if secret_value:
                    api_keys[key_name] = {
                        "present": True,
                        "daily_quota": default_quota,
                        "remaining": default_quota,
                        "reset_time": "6am_pt",
                        "last_reset": datetime.now(timezone.utc).isoformat(),
                    }
                else:
                    api_keys[key_name] = {
                        "present": False,
                        "daily_quota": 0,
                        "remaining": 0,
                        "reset_time": "6am_pt",
                        "last_reset": datetime.now(timezone.utc).isoformat(),
                    }
            except Exception as e:
                logger.debug(
                    "Could not load API key %s from Vault: %s",
                    key_name, e
                )
                api_keys[key_name] = {
                    "present": False,
                    "daily_quota": 0,
                    "remaining": 0,
                    "reset_time": "6am_pt",
                    "error": str(e),
                }

        return api_keys

    async def _get_scan_queue_entries(self, db: Any) -> list[dict]:
        """Get all pending scan queue entries from the database."""
        try:
            from sqlalchemy import select
            from ..models.scan_pool import (
                OpportunityScanPool, OpportunityScanPoolEntry
            )

            result = await db.execute(
                select(OpportunityScanPoolEntry).where(
                    OpportunityScanPoolEntry.status.in_(["waiting", "active"])
                )
            )
            entries = result.scalars().all()

            return [
                {
                    "id": str(entry.id),
                    "pool_id": str(entry.pool_id),
                    "opportunity_id": str(entry.opportunity_id),
                    "status": entry.status,
                    "queue_position": entry.queue_position,
                }
                for entry in entries
            ]
        except Exception as e:
            logger.warning("Could not read scan queue: %s", e)
            return []

    def _calculate_allocations(
        self,
        api_keys: dict[str, dict],
        scan_entries: list[dict],
    ) -> dict[str, dict[str, int]]:
        """Divide available API key quota across scan entries."""
        n_scans = max(len(scan_entries), 1)
        allocations: dict[str, dict[str, int]] = {}

        for key_name, key_data in api_keys.items():
            if not key_data.get("present", False):
                continue

            remaining = key_data.get("remaining", 0)
            if remaining <= 0:
                allocations[key_name] = {}
                continue

            # Reserve 15% for peak demand
            usable = int(remaining * (1 - self.RESERVE_RATIO))
            per_scan = max(usable // n_scans, 0)

            allocations[key_name] = {
                entry.get("id", "default"): per_scan
                for entry in scan_entries
            }

        return allocations

    async def _check_and_enforce_queue_limits(
        self,
        db: Any,
        current_queue_length: int,
    ) -> dict[str, Any]:
        """Check queue length against limits and return status."""
        status = {
            "current_length": current_queue_length,
            "max_length": self.MAX_QUEUE_LENGTH,
            "target_length": self.TARGET_QUEUE_LENGTH,
            "at_limit": current_queue_length >= self.MAX_QUEUE_LENGTH,
            "below_minimum": current_queue_length < self.MIN_QUEUE_LENGTH,
            "action": "none",
        }

        if current_queue_length >= self.MAX_QUEUE_LENGTH:
            status["action"] = "queue_paused"
            logger.warning(
                "API-Scan Queue at maximum length (%d). "
                "New scans paused to prevent bottleneck.",
                current_queue_length,
            )
        elif current_queue_length < self.MIN_QUEUE_LENGTH:
            status["action"] = "queue_needs_replenishment"
            logger.info(
                "API-Scan Queue below minimum (%d). "
                "Recommend adding more opportunities.",
                current_queue_length,
            )

        return status

    def _write_allocation_plan(
        self,
        allocations: dict[str, dict[str, int]],
        scan_entries: list[dict],
        queue_status: dict[str, Any],
    ) -> None:
        """Write allocation plan to artifacts directory."""
        # Write per-scan allocation scripts (similar to midnight orchestrator)
        for entry in scan_entries:
            scan_id = entry.get("id", "default")
            script_lines = [
                "#!/bin/bash",
                f"# Generated by APIKeysOrchestrator (6AM daily)",
                f"# Scan: {scan_id}",
                f"# Generated: {datetime.now(timezone.utc).isoformat()}",
                "",
                "# API Key allocations for this scan entry",
                "",
            ]

            for key_name, scan_allocs in allocations.items():
                quota = scan_allocs.get(scan_id, 0)
                script_lines.append(
                    f'export {key_name}_DAILY_LIMIT="{quota}"'
                )
                script_lines.append(
                    f'export {key_name}_ALLOCATED_AT="{datetime.now(timezone.utc).isoformat()}"'
                )

            script_lines.append("")

            script_path = (
                self.OUTPUT_DIR /
                f"scan_{scan_id}_api_allocation.sh"
            )
            script_path.write_text("\n".join(script_lines))
            script_path.chmod(0o700)

        # Write summary
        self._write_allocation_summary(
            allocations, scan_entries, queue_status
        )

    def _write_allocation_summary(
        self,
        allocations: dict[str, dict[str, int]],
        scan_entries: list[dict],
        queue_status: dict[str, Any],
    ) -> None:
        """Write allocation summary JSON."""
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "orchestrator": "api_keys_orchestrator",
            "schedule": "6am_pt_daily",
            "scans_planned": len(scan_entries),
            "queue_status": queue_status,
            "allocations_summary": {
                key: {
                    "total_allocated": sum(
                        v for v in allocs.values() if isinstance(v, int)
                    ),
                    "scans_receiving_quota": len(
                        [v for v in allocs.values() if isinstance(v, int) and v > 0]
                    ),
                }
                for key, allocs in allocations.items()
            },
        }

        self.ALLOCATION_SUMMARY_PATH.write_text(
            json.dumps(summary, indent=2)
        )

        # Also write queue status to separate file
        queue_status_path = self.QUEUE_STATUS_PATH
        queue_status_path.write_text(
            json.dumps(queue_status, indent=2)
        )

    def _write_default_allocation(self) -> None:
        """Write default allocation on orchestrator failure."""
        fallback = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "orchestrator": "api_keys_orchestrator",
            "status": "fallback",
            "error": "Orchestrator encountered an error",
            "queue_status": {
                "current_length": 0,
                "max_length": self.MAX_QUEUE_LENGTH,
                "action": "manual_review_required",
            },
        }
        self.ALLOCATION_SUMMARY_PATH.write_text(
            json.dumps(fallback, indent=2)
        )
