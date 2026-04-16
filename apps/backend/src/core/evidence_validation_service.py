from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.evidence_validation import EvidenceValidation
from ..models.structured_evidence import StructuredEvidence
from .evidence_lifecycle_service import EvidenceLifecycleService

logger = logging.getLogger(__name__)

VALID_VALIDATION_OUTCOMES: frozenset[str] = frozenset(
    {"CONFIRMED", "INCONCLUSIVE", "REJECTED", "NOISE"}
)

VALID_VALIDATION_METHODS: frozenset[str] = frozenset(
    {"manual_review", "automated_check", "reproduction", "peer_review"}
)


class EvidenceValidationService:
    """Service for creating and querying EvidenceValidation records.

    After a validation is created the service automatically advances the
    evidence lifecycle:
    - outcome == "CONFIRMED" → advance to REVIEWED (if transition is legal)
    - outcome == "REJECTED"  → advance to REJECTED  (if transition is legal)

    Lifecycle advancement failures are logged but not re-raised so that
    validation record creation always succeeds — the state machine may
    already be in a terminal or advanced state.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._lifecycle = EvidenceLifecycleService(db)

    async def create_validation(
        self,
        *,
        evidence_id: UUID,
        actor: str,
        method: str,
        outcome: str,
        notes: str | None = None,
        campaign_id: UUID | None = None,
        finding_id: UUID | None = None,
        tenant_id: UUID | None = None,
    ) -> EvidenceValidation:
        """Create a validation record and, if applicable, advance evidence lifecycle.

        Raises ``ValueError`` for unknown outcome or method values.
        Raises ``LookupError`` when the referenced evidence_id is not found.
        """
        if outcome not in VALID_VALIDATION_OUTCOMES:
            raise ValueError(
                f"Invalid validation_outcome '{outcome}'. "
                f"Allowed: {sorted(VALID_VALIDATION_OUTCOMES)}"
            )
        if method not in VALID_VALIDATION_METHODS:
            raise ValueError(
                f"Invalid validation_method '{method}'. "
                f"Allowed: {sorted(VALID_VALIDATION_METHODS)}"
            )

        # Verify evidence exists
        ev_result = await self.db.execute(
            select(StructuredEvidence).where(StructuredEvidence.id == evidence_id)
        )
        evidence = ev_result.scalar_one_or_none()
        if evidence is None:
            raise LookupError(
                f"StructuredEvidence not found: evidence_id={evidence_id}"
            )

        record = EvidenceValidation(
            evidence_id=evidence_id,
            campaign_id=campaign_id,
            finding_id=finding_id,
            tenant_id=tenant_id,
            actor=actor,
            validation_method=method,
            validation_outcome=outcome,
            notes=notes,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)

        logger.info(
            "evidence_validation.created id=%s evidence_id=%s outcome=%s actor=%s",
            record.id,
            evidence_id,
            outcome,
            actor,
        )

        # Advance lifecycle based on outcome — failures are non-fatal
        target_status: str | None = None
        if outcome == "CONFIRMED":
            target_status = "REVIEWED"
        elif outcome == "REJECTED":
            target_status = "REJECTED"

        if target_status is not None:
            try:
                await self._lifecycle.advance_lifecycle(
                    evidence=evidence,
                    to_status=target_status,
                    actor=actor,
                )
            except ValueError as exc:
                logger.warning(
                    "evidence_validation.lifecycle_advance_skipped "
                    "evidence_id=%s target=%s reason=%s",
                    evidence_id,
                    target_status,
                    exc,
                )

        return record

    async def get_validations_for_evidence(
        self,
        evidence_id: UUID,
    ) -> list[EvidenceValidation]:
        """Return all validation records for *evidence_id*, ordered oldest-first."""
        result = await self.db.execute(
            select(EvidenceValidation)
            .where(EvidenceValidation.evidence_id == evidence_id)
            .order_by(EvidenceValidation.validated_at.asc())
        )
        return list(result.scalars().all())
