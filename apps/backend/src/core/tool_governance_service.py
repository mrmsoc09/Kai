from __future__ import annotations

import logging
from typing import Any

from .tool_risk_registry import ToolGovernanceResult, get_tool_band

logger = logging.getLogger(__name__)


class ToolGovernanceService:
    """Enforces Band 0/1/2/3 risk classification before tool execution."""

    async def check_tool_authorization(
        self,
        tool_name: str,
        campaign_id: str,
        db: Any = None,
        existing_gate_id: str | None = None,
    ) -> ToolGovernanceResult:
        """Check whether a tool is authorized to run.

        - Band 0/1: auto-allowed (no DB call)
        - Band 2: requires an APPROVED gate in the database; existing_gate_id is
          verified via is_approved() — a bare UUID is never trusted
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
            if existing_gate_id and db is not None:
                approved = await self.is_approved(existing_gate_id, db)
                if approved:
                    return ToolGovernanceResult(
                        allowed=True,
                        band=band,
                        requires_approval=False,
                        gate_id=existing_gate_id,
                        reason="Band 2 tool approved via verified gate",
                    )
                # Gate exists but is not APPROVED — reject, preserve gate_id for caller
                return ToolGovernanceResult(
                    allowed=False,
                    band=band,
                    requires_approval=True,
                    gate_id=existing_gate_id,
                    reason="Band 2 tool gate not yet approved",
                )
            # No gate provided, or no db — cannot approve
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

    async def is_approved(self, gate_id: str | None, db: Any) -> bool:
        """Check if a gate is APPROVED in the database.

        Returns False immediately if gate_id is None or db is None.
        """
        if not gate_id or db is None:
            return False

        from sqlalchemy import select

        try:
            from ..models.campaign import ApprovalGate
        except ImportError:
            logger.warning("ApprovalGate model not importable — returning False")
            return False

        result = await db.execute(
            select(ApprovalGate.status).where(ApprovalGate.id == gate_id)
        )
        row = result.scalar_one_or_none()
        return row == "APPROVED" if row else False
