"""Scanning mode detection based on available credentials."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ScanningModeDetector:
    """
    Detects which scanning modes are available for an opportunity
    based on stored credentials and access metadata.
    """

    # Playbook count per mode (from workflow templates)
    PLAYBOOK_COUNTS = {
        "unauthenticated": 8,
        "user_account": 15,
        "api_key": 8,
        "hunter_account": 20,
    }

    # Coverage gain estimates
    COVERAGE_GAINS = {
        "user_account": "+25%",
        "api_key": "+12%",
        "hunter_account": "+15%",
    }

    def __init__(self, credentials_manager: Any):
        """
        Initialize mode detector with credentials manager.

        Args:
            credentials_manager: CredentialsManager instance
        """
        self.creds_mgr = credentials_manager

    async def get_available_modes(self, program_id: str) -> dict[str, Any]:
        """
        Determine which scanning modes are available.

        Returns:
            {
                "available_modes": ["unauthenticated", "user_account", ...],
                "unavailable_modes": ["hunter_account"],
                "mode_details": {...},
                "coverage_analysis": {...}
            }
        """
        # Get stored credentials
        try:
            credentials = await self.creds_mgr.list_credentials_for_program(program_id)
        except Exception as e:
            logger.warning(f"Failed to load credentials for {program_id}: {e}")
            credentials = []

        # Get access metadata
        try:
            access_metadata = await self.creds_mgr.upsert_access_metadata(
                program_id, "placeholder", enabled=False
            )  # Just to trigger loading
        except Exception:
            access_metadata = {}

        # Build available modes
        available_modes = ["unauthenticated"]  # Always available
        unavailable_modes = []
        mode_details = {
            "unauthenticated": {
                "available": True,
                "stored": False,
                "status": "ready",
                "playbook_count": self.PLAYBOOK_COUNTS["unauthenticated"],
                "description": "Public pages without login",
            }
        }

        # Check each credential type
        for access_type in ["user_account", "api_key", "hunter_account"]:
            stored = any(c.access_type == access_type for c in credentials)

            if stored:
                # Get credential details
                cred = next(
                    c for c in credentials if c.access_type == access_type
                )
                available_modes.append(access_type)
                mode_details[access_type] = {
                    "available": True,
                    "stored": True,
                    "status": cred.status,
                    "playbook_count": self.PLAYBOOK_COUNTS.get(access_type, 0),
                    "last_validated_at": cred.last_validated.isoformat()
                    if cred.last_validated
                    else None,
                    "credential_username": cred.credential_username,
                    "credential_identifier": cred.credential_identifier,
                }
            else:
                unavailable_modes.append(access_type)
                mode_details[access_type] = {
                    "available": True,
                    "stored": False,
                    "status": "not_stored",
                    "playbook_count": self.PLAYBOOK_COUNTS.get(access_type, 0),
                    "coverage_gain": self.COVERAGE_GAINS.get(access_type, "+5%"),
                    "action": "Add credential to enable this mode",
                }

        # Coverage analysis
        coverage = self._analyze_coverage(available_modes, unavailable_modes)

        result = {
            "available_modes": available_modes,
            "unavailable_modes": unavailable_modes,
            "mode_details": mode_details,
            "coverage_analysis": coverage,
        }

        logger.info(
            f"Scanning modes for {program_id}: {len(available_modes)} available, "
            f"{len(unavailable_modes)} unavailable"
        )

        return result

    def _analyze_coverage(self, available: list[str], unavailable: list[str]) -> dict[str, Any]:
        """
        Analyze current vs. potential coverage.

        Returns:
            {
                "current_coverage": "85%",
                "potential_coverage": "100%",
                "coverage_gain_possible": "+15%",
                "coverage_gain_source": "hunter_account",
                "recommendation": "..."
            }
        """
        # Calculate available playbook count
        available_playbook_count = sum(
            self.PLAYBOOK_COUNTS.get(mode, 0) for mode in available
        )

        # Total playbooks
        total_playbook_count = sum(self.PLAYBOOK_COUNTS.values())

        # Potential count (if all were available)
        potential_count = total_playbook_count

        # Percentages
        current_coverage = int((available_playbook_count / total_playbook_count) * 100)
        potential_coverage = int((potential_count / total_playbook_count) * 100)
        coverage_gain = potential_coverage - current_coverage

        # Identify gain source
        gain_source = None
        if unavailable:
            gain_source = unavailable[0]  # First missing mode

        recommendation = (
            f"Add {gain_source} to increase coverage by {coverage_gain}%"
            if gain_source
            else "Full coverage achieved with all credentials"
        )

        return {
            "current_coverage": f"{current_coverage}%",
            "potential_coverage": f"{potential_coverage}%",
            "coverage_gain_possible": f"+{coverage_gain}%",
            "coverage_gain_source": gain_source,
            "recommendation": recommendation,
        }
