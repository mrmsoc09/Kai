from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MidnightOrchestrator:
    """
    Runs at midnight PT to calculate API key budgets
    and write per-scan credential scripts.

    Design: pure arithmetic allocation.
    No LLM involvement. No complex logic.
    Query quota → divide by scan count → write scripts.

    Tool agents source the generated scripts before
    execution so they know exactly what API calls
    they can make today.
    """

    RESERVE_RATIO = 0.15
    OUTPUT_DIR = Path("artifacts/scan_configs")
    BUDGET_SUMMARY_PATH = Path(
        "artifacts/scan_configs/daily_budget_summary.json"
    )
    SIGNAL_HISTORY_PATH = Path(
        "artifacts/api_intelligence/source_signals.json"
    )

    SPIDERFOOT_TIER_0 = [
        "sfp_dns", "sfp_ssl", "sfp_whois",
        "sfp_crt", "sfp_netcraft", "sfp_robtex",
        "sfp_waybackmachine", "sfp_dnsbrute",
    ]

    SPIDERFOOT_TIER_1 = {
        "sfp_shodan": "SHODAN_API_KEY",
        "sfp_virustotal": "VIRUSTOTAL_API_KEY",
        "sfp_censys": "CENSYS_API_KEY",
        "sfp_github": "GITHUB_TOKEN",
        "sfp_hunter": "HUNTER_API_KEY",
    }

    def __init__(self):
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.SIGNAL_HISTORY_PATH.parent.mkdir(
            parents=True, exist_ok=True
        )

    def run(self) -> None:
        """Main entry point. Called by Celery beat at midnight."""
        logger.info("Midnight orchestrator starting")
        try:
            quota_data = self._query_all_sources()
            scan_queue = self._read_todays_queue()
            allocations = self._calculate_allocations(
                quota_data, scan_queue
            )
            self._write_scan_scripts(
                allocations, scan_queue
            )
            self._write_budget_summary(
                quota_data, allocations, scan_queue
            )
            logger.info(
                "Midnight orchestration complete. "
                "%d scans planned, %d sources available",
                len(scan_queue),
                len([
                    s for s in quota_data.values()
                    if s.get("remaining", 0) > 0
                ]),
            )
        except Exception as e:
            logger.error(
                "Midnight orchestrator failed: %s", e
            )
            self._write_default_scripts()

    def _query_all_sources(self) -> dict[str, dict]:
        """Query each registered API source for quota."""
        sources: dict[str, dict] = {}
        known_limits = {
            "SHODAN_API_KEY": 100,
            "VIRUSTOTAL_API_KEY": 500,
            "CENSYS_API_KEY": 250,
            "GITHUB_TOKEN": 5000,
            "HUNTER_API_KEY": 25,
            "FULLHUNT_API_KEY": 100,
            "LEAKIX_API_KEY": 500,
            "DEHASHED_API_KEY": 100,
            "GRAYHATWARFARE_API_KEY": 200,
            "NVD_NIST_API_KEY": 2000,
            "IPINFO_API_KEY": 1000,
        }
        for env_var, daily_limit in known_limits.items():
            key_present = bool(os.environ.get(env_var))
            sources[env_var] = {
                "present": key_present,
                "daily_limit": daily_limit if key_present else 0,
                "remaining": daily_limit if key_present else 0,
                "reset_time": "midnight_pt",
            }
        return sources

    def _read_todays_queue(self) -> list[dict]:
        """Read today's planned scans from database."""
        try:
            from sqlalchemy import create_engine, select
            db_url = os.environ.get(
                "DATABASE_URL", ""
            ).replace(
                "postgresql+asyncpg", "postgresql"
            ).replace(
                "sqlite+aiosqlite", "sqlite"
            )
            if not db_url:
                return []
            engine = create_engine(db_url)
            with engine.connect() as conn:
                # Placeholder — no ScanPool yet in model
                return []
        except Exception as e:
            logger.warning(
                "Could not read scan queue: %s", e
            )
            return []

    def _calculate_allocations(
        self,
        quota_data: dict[str, dict],
        scan_queue: list[dict],
    ) -> dict[str, dict[str, int]]:
        """Divide available quota across scans."""
        n_scans = max(len(scan_queue), 1)
        allocations: dict[str, dict[str, int]] = {}
        for source, data in quota_data.items():
            remaining = data.get("remaining", 0)
            if remaining <= 0:
                continue
            usable = int(
                remaining * (1 - self.RESERVE_RATIO)
            )
            per_scan = max(usable // n_scans, 0)
            allocations[source] = {
                scan.get("scan_id", "default"): per_scan
                for scan in scan_queue
            }
        return allocations

    def _write_scan_scripts(
        self,
        allocations: dict[str, dict[str, int]],
        scan_queue: list[dict],
    ) -> None:
        """Write a shell credential script for each scan."""
        scan_ids = {s.get("scan_id", "default") 
                    for s in scan_queue}
        scan_ids.add("default")

        for scan_id in scan_ids:
            script_lines = [
                "#!/bin/bash",
                f"# Generated by MidnightOrchestrator",
                f"# Scan: {scan_id}",
                f"# Generated: "
                f"{datetime.now(timezone.utc).isoformat()}",
                "",
            ]

            for source_env, scan_allocs in \
                    allocations.items():
                limit = scan_allocs.get(scan_id, 0)
                key_val = os.environ.get(source_env, "")
                if key_val and limit > 0:
                    script_lines.append(
                        f'export {source_env}='
                        f'"{key_val}"'
                    )
                    script_lines.append(
                        f'export {source_env}_DAILY_LIMIT='
                        f'"{limit}"'
                    )
                else:
                    script_lines.append(
                        f'export {source_env}=""'
                    )
                    script_lines.append(
                        f'export {source_env}_DAILY_LIMIT="0"'
                    )

            sf_modules = list(self.SPIDERFOOT_TIER_0)
            for module, env_var in \
                    self.SPIDERFOOT_TIER_1.items():
                limit = allocations.get(
                    env_var, {}
                ).get(scan_id, 0)
                if limit > 0:
                    sf_modules.append(module)
            script_lines.append(
                f'export SPIDERFOOT_MODULES='
                f'"{",".join(sf_modules)}"'
            )
            script_lines.append("")

            script_path = (
                self.OUTPUT_DIR /
                f"scan_{scan_id}_api_keys.sh"
            )
            script_path.write_text(
                "\n".join(script_lines)
            )
            script_path.chmod(0o700)

    def _write_budget_summary(
        self,
        quota_data: dict,
        allocations: dict,
        scan_queue: list,
    ) -> None:
        summary = {
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "scans_planned": len(scan_queue),
            "sources": {
                src: {
                    "daily_limit": data.get(
                        "daily_limit", 0
                    ),
                    "remaining": data.get(
                        "remaining", 0
                    ),
                    "has_budget": data.get(
                        "remaining", 0
                    ) > 0,
                }
                for src, data in quota_data.items()
            },
        }
        self.BUDGET_SUMMARY_PATH.write_text(
            json.dumps(summary, indent=2)
        )

    def _write_default_scripts(self) -> None:
        """Fallback: write empty scripts."""
        default = self.OUTPUT_DIR / "default_api_keys.sh"
        default.write_text(
            "#!/bin/bash\n"
            "# Default — midnight orchestrator fallback\n"
            "# No quota management active\n"
        )
        default.chmod(0o700)

    def reconcile_after_scan(
        self,
        scan_id: str,
        actual_usage: dict[str, int],
        findings_per_source: dict[str, int],
    ) -> None:
        """Called after each scan. Records usage and yield."""
        history = {}
        if self.SIGNAL_HISTORY_PATH.exists():
            try:
                history = json.loads(
                    self.SIGNAL_HISTORY_PATH.read_text()
                )
            except Exception:
                history = {}

        for source, calls_used in actual_usage.items():
            findings = findings_per_source.get(source, 0)
            signal_score = (
                findings / calls_used
                if calls_used > 0 else 0.0
            )
            if source not in history:
                history[source] = []
            history[source].append({
                "scan_id": scan_id,
                "calls_used": calls_used,
                "findings": findings,
                "signal_score": signal_score,
                "recorded_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            })
            history[source] = history[source][-30:]

        self.SIGNAL_HISTORY_PATH.write_text(
            json.dumps(history, indent=2)
        )
