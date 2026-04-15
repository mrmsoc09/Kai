"""Orchestrator wrapper that enforces scope at every step.

Wraps playbook execution with scope validation. If any violation is detected,
aborts the entire playbook execution immediately (no further requests).
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .scope_validator import ScopeValidator, ScopeViolationType

logger = logging.getLogger(__name__)


class ScopeEnforcedOrchestrator:
    """Orchestrator that validates scope before executing ANY request.

    If scope violation detected, aborts scan IMMEDIATELY with no further
    requests executed.
    """

    def __init__(self, db: AsyncSession, scope_validator: Optional[ScopeValidator] = None):
        self.db = db
        self.scope_validator = scope_validator or ScopeValidator(db)
        self.scan_aborted = False

    async def execute_playbook_with_scope_check(
        self,
        program_id: str | UUID,
        scan_id: str | UUID,
        playbook: dict[str, Any],
        target_urls: list[str],
    ) -> dict[str, Any]:
        """Execute playbook but check scope before EVERY request.

        Args:
            program_id: Program ID
            scan_id: Scan ID for audit trail
            playbook: Playbook definition with target_endpoint, target_port, etc.
            target_urls: List of URLs to test

        Returns:
            Results dict with:
                - aborted: True if scope violation caused abort
                - scope_violations: Number of violations detected
                - requests_made: Number of requests actually executed
                - findings: List of findings discovered
        """
        program_id_str = str(program_id) if isinstance(program_id, UUID) else program_id
        scan_id_str = str(scan_id) if isinstance(scan_id, UUID) else scan_id

        results = {
            "playbook_id": playbook.get("id"),
            "playbook_name": playbook.get("name"),
            "findings": [],
            "requests_made": 0,
            "scope_violations": 0,
            "aborted": False,
            "abort_reason": None,
        }

        for target_url in target_urls:
            # CRITICAL: Check scope BEFORE making ANY request
            is_valid, violation_type, reason = await self.scope_validator.validate_request(
                program_id=program_id_str,
                target_url=target_url,
                target_endpoint=playbook.get("target_endpoint", ""),
                scan_id=scan_id_str,
                target_port=playbook.get("target_port"),
                target_ip=playbook.get("target_ip"),
                parameters=playbook.get("parameters"),
            )

            if not is_valid:
                # ABORT IMMEDIATELY
                logger.error(
                    f"SCOPE VIOLATION DETECTED - ABORTING PLAYBOOK: {reason}. "
                    f"Violation type: {violation_type}"
                )
                results["scope_violations"] += 1
                results["aborted"] = True
                results["abort_reason"] = reason
                self.scan_aborted = True

                # Return immediately - no further requests
                return results

            # Scope is valid, execute request (caller would implement actual request logic)
            # For now, just mark as processed
            results["requests_made"] += 1

            # Process response for findings (placeholder - caller would implement)
            # if response.get('vulnerability_found'):
            #     results['findings'].append({...})

        logger.info(
            f"Playbook {playbook.get('id')} executed successfully with "
            f"{results['requests_made']} requests and {len(results['findings'])} findings"
        )

        return results

    async def check_and_abort_if_kill_switch(
        self, scan_id: str | UUID, kill_switch: Optional[Any] = None
    ) -> bool:
        """Check if kill switch was activated for this scan.

        Called during long-running playbooks to allow graceful abort.

        Args:
            scan_id: Scan ID to check
            kill_switch: Optional ScanKillSwitch instance

        Returns:
            True if kill switch is active (scan should abort), False otherwise
        """
        if not kill_switch:
            return False

        scan_id_str = str(scan_id) if isinstance(scan_id, UUID) else scan_id
        return await kill_switch.is_abort_requested(scan_id_str)

    def get_status(self) -> dict[str, Any]:
        """Get orchestrator status."""
        return {
            "scan_aborted": self.scan_aborted,
            "validator_stats": self.scope_validator.get_stats(),
        }
