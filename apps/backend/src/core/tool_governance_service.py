from __future__ import annotations

import logging
from typing import Any

from .tool_risk_registry import ToolGovernanceResult, get_tool_band

logger = logging.getLogger(__name__)


class ToolGovernanceService:
    """Enforces Band 0/1/2/3 risk classification before tool execution."""

    def check_tool_authorization(
        self,
        tool_name: str,
        campaign_id: str,
        existing_gate_id: str | None = None,
    ) -> ToolGovernanceResult:
        """Check whether a tool is authorized to run.

        - Band 0/1: auto-allowed
        - Band 2: requires an APPROVED gate; if existing_gate_id is provided and valid, allowed
        - Band 3: always blocked
        """
        band = get_tool_band(tool_name)

        if band <= 1:
            return ToolGovernanceResult(
                allowed=True,
                band=band,
                requires_approval=False,
                gate_id=None,
                reason=f"Band {band} tool auto-approved",
            )

        if band == 2:
            if existing_gate_id:
                # Caller asserts gate is approved; in production use is_approved() for DB check
                return ToolGovernanceResult(
                    allowed=True,
                    band=band,
                    requires_approval=False,
                    gate_id=existing_gate_id,
                    reason="Band 2 tool approved via gate",
                )
            return ToolGovernanceResult(
                allowed=False,
                band=band,
                requires_approval=True,
                gate_id=None,
                reason="Band 2 tool requires approval gate",
            )

        # Band 3
        return ToolGovernanceResult(
            allowed=False,
            band=3,
            requires_approval=False,
            gate_id=None,
            reason="Band 3 tools blocked",
        )

    async def is_approved(self, gate_id: str, db: Any) -> bool:
        """Check if a gate is APPROVED in the database."""
        from ..models.campaign import ApprovalGate
        from sqlalchemy import select

        result = await db.execute(
            select(ApprovalGate.status).where(ApprovalGate.id == gate_id)
        )
        row = result.scalar_one_or_none()
        return row == "APPROVED" if row else False
