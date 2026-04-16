from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.structured_evidence import StructuredEvidence
from ..schemas.evidence import EvidenceReadinessReport

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Evidence lifecycle state machine
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[str, set[str]] = {
    "COLLECTED": {"CORRELATED", "REJECTED"},
    "CORRELATED": {"REVIEWED", "REJECTED"},
    "REVIEWED": {"VALIDATED", "REJECTED"},
    "VALIDATED": {"RECORDED", "REJECTED"},
    "RECORDED": {"REPORT_READY"},
    "REPORT_READY": set(),   # terminal
    "REJECTED": set(),        # terminal
}

VALID_LIFECYCLE_STATUSES: frozenset[str] = frozenset(VALID_TRANSITIONS.keys())


class EvidenceLifecycleService:
    """State machine manager for StructuredEvidence lifecycle.

    All mutations go through ``advance_lifecycle`` so the transition graph
    is enforced in a single place.  Callers must commit the session after
    calling service methods — the service only flushes.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def advance_lifecycle(
        self,
        evidence: StructuredEvidence,
        to_status: str,
        actor: str,
    ) -> StructuredEvidence:
        """Advance evidence lifecycle to *to_status*.

        Raises ``ValueError`` for:
        - unknown target status
        - disallowed transition from current state
        """
        if to_status not in VALID_LIFECYCLE_STATUSES:
            raise ValueError(
                f"Unknown lifecycle status '{to_status}'. "
                f"Allowed: {sorted(VALID_LIFECYCLE_STATUSES)}"
            )
        current = evidence.lifecycle_status or "COLLECTED"
        if to_status not in VALID_TRANSITIONS.get(current, set()):
            allowed = sorted(VALID_TRANSITIONS.get(current, set()))
            raise ValueError(
                f"Invalid lifecycle transition '{current}' -> '{to_status}' "
                f"for evidence_id={evidence.id}. Allowed next states: {allowed}"
            )

        previous = current
        evidence.lifecycle_status = to_status
        evidence.lifecycle_transitioned_at = datetime.now(timezone.utc)
        evidence.lifecycle_actor = actor
        await self.db.flush()
        logger.info(
            "evidence_lifecycle.advanced evidence_id=%s %s -> %s actor=%s",
            evidence.id,
            previous,
            to_status,
            actor,
        )
        return evidence

    async def get_readiness(
        self,
        evidence_id: UUID,
    ) -> EvidenceReadinessReport:
        """Compute a readiness report for *evidence_id*.

        Queries evidence, counts validations and approval links, then returns
        the computed ``EvidenceReadinessReport``.  Raises ``ValueError`` when
        evidence is not found.
        """
        # Lazy import to avoid circular imports at module load time
        from ..models.evidence_validation import EvidenceValidation
        from ..models.approval_evidence_link import ApprovalEvidenceLink

        result = await self.db.execute(
            select(StructuredEvidence).where(StructuredEvidence.id == evidence_id)
        )
        evidence = result.scalar_one_or_none()
        if evidence is None:
            raise ValueError(f"StructuredEvidence not found: evidence_id={evidence_id}")

        # Count validations
        val_result = await self.db.execute(
            select(func.count())
            .select_from(EvidenceValidation)
            .where(EvidenceValidation.evidence_id == evidence_id)
        )
        validation_count: int = val_result.scalar_one() or 0

        # Count confirmed validations
        confirmed_result = await self.db.execute(
            select(func.count())
            .select_from(EvidenceValidation)
            .where(
                EvidenceValidation.evidence_id == evidence_id,
                EvidenceValidation.validation_outcome == "CONFIRMED",
            )
        )
        confirmed_count: int = confirmed_result.scalar_one() or 0

        # Count approval links
        link_result = await self.db.execute(
            select(func.count())
            .select_from(ApprovalEvidenceLink)
            .where(ApprovalEvidenceLink.evidence_id == evidence_id)
        )
        link_count: int = link_result.scalar_one() or 0

        has_replay = any([
            evidence.replay_request_response_uri is not None,
            evidence.replay_command_transcript_uri is not None,
            evidence.replay_screen_recording_uri is not None,
            evidence.replay_reproduction_steps is not None,
            evidence.replay_terminal_ref is not None,
        ])

        lifecycle = evidence.lifecycle_status or "COLLECTED"

        return EvidenceReadinessReport(
            evidence_id=evidence_id,
            lifecycle_status=lifecycle,
            has_validation=validation_count > 0,
            has_confirmed_validation=confirmed_count > 0,
            has_replay_artifacts=has_replay,
            has_approval_link=link_count > 0,
            report_ready=lifecycle == "REPORT_READY",
            validation_count=validation_count,
            approval_link_count=link_count,
        )
