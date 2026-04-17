from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_REPLAY_FIELDS = [
    "request_response_uri",
    "command_transcript_uri",
    "screen_recording_uri",
    "reproduction_steps",
    "terminal_ref",
]


@dataclass
class ReplayPackage:
    evidence_id: str
    request_response_uri: str | None = None
    command_transcript_uri: str | None = None
    screen_recording_uri: str | None = None
    reproduction_steps: str | None = None
    terminal_ref: str | None = None

    @property
    def is_reproducible(self) -> bool:
        """True if at least one replay artifact is present."""
        return any(
            getattr(self, f) is not None
            for f in _REPLAY_FIELDS
        )

    @property
    def completeness_score(self) -> float:
        """Fraction of 5 artifact types that are present (0.0-1.0)."""
        present = sum(
            1 for f in _REPLAY_FIELDS
            if getattr(self, f) is not None
        )
        return present / len(_REPLAY_FIELDS)


class ReplayService:
    """Builds replay packages from structured evidence records."""

    def build_replay_package(self, evidence: Any) -> ReplayPackage:
        """Map evidence replay fields to a ReplayPackage.

        evidence can be a StructuredEvidence ORM instance or any object/dict with
        replay_* attributes.
        """
        def _get(field_name: str) -> str | None:
            prefixed = f"replay_{field_name}"
            if hasattr(evidence, prefixed):
                val = getattr(evidence, prefixed)
                return val if val else None
            if isinstance(evidence, dict):
                val = evidence.get(prefixed)
                return val if val else None
            return None

        eid = str(getattr(evidence, "id", None) or (evidence.get("id") if isinstance(evidence, dict) else "unknown"))

        return ReplayPackage(
            evidence_id=eid,
            request_response_uri=_get("request_response_uri"),
            command_transcript_uri=_get("command_transcript_uri"),
            screen_recording_uri=_get("screen_recording_uri"),
            reproduction_steps=_get("reproduction_steps"),
            terminal_ref=_get("terminal_ref"),
        )

    async def get_replay_package_for_finding(
        self, finding_id: str, db: Any
    ) -> list[ReplayPackage]:
        """Load all evidence for a finding and build replay packages."""
        from sqlalchemy import select
        from ..models.structured_evidence import StructuredEvidence

        result = await db.execute(
            select(StructuredEvidence).where(
                StructuredEvidence.finding_id == finding_id
            )
        )
        rows = result.scalars().all()
        return [self.build_replay_package(row) for row in rows]

    def assess_proof_completeness(self, packages: list[ReplayPackage]) -> dict[str, Any]:
        """Assess overall proof completeness across all replay packages.

        proof_ready = at least 1 package is reproducible with completeness >= 0.6
        """
        total = len(packages)
        reproducible = [p for p in packages if p.is_reproducible]
        scores = [p.completeness_score for p in packages]
        avg = sum(scores) / total if total > 0 else 0.0

        proof_ready = any(
            p.is_reproducible and p.completeness_score >= 0.6
            for p in packages
        )

        return {
            "total_evidence": total,
            "reproducible_count": len(reproducible),
            "avg_completeness": round(avg, 3),
            "proof_ready": proof_ready,
        }
