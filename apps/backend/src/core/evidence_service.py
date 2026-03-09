from __future__ import annotations

import binascii
import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import Artifact
from ..models.hil import Evidence
from .audit_events import record_transition_event


class EvidenceService:
    """Deterministic Artifact -> Evidence linker for canonical findings."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _is_synthetic(artifact: Artifact) -> bool:
        if artifact.uri.startswith("inline://"):
            return True
        details = artifact.details_json if isinstance(artifact.details_json, dict) else {}
        return bool(details.get("inline") or details.get("placeholder") or details.get("synthetic"))

    @staticmethod
    def _digest_from_artifact(artifact: Artifact) -> bytes:
        if artifact.content_hash:
            try:
                return binascii.unhexlify(artifact.content_hash)
            except (binascii.Error, ValueError):
                pass
        details = artifact.details_json if isinstance(artifact.details_json, dict) else {}
        seed = json.dumps(
            {
                "uri": artifact.uri,
                "mime_type": artifact.mime_type,
                "size_bytes": artifact.size_bytes,
                "details": details,
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(seed).digest()

    async def _existing_evidence(
        self,
        *,
        finding_id: UUID,
        uri: str,
        sha256: bytes,
    ) -> Evidence | None:
        result = await self.db.execute(
            select(Evidence)
            .where(
                Evidence.finding_id == finding_id,
                Evidence.uri == uri,
                Evidence.sha256 == sha256,
                Evidence.is_deleted.is_(False),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def attach_artifact_to_finding(
        self,
        *,
        finding_id: UUID,
        artifact: Artifact,
        actor: str | None = None,
        intention_id: UUID | None = None,
    ) -> tuple[Evidence, bool]:
        digest = self._digest_from_artifact(artifact)
        existing = await self._existing_evidence(
            finding_id=finding_id,
            uri=artifact.uri,
            sha256=digest,
        )
        if existing is not None:
            if artifact.finding_id != finding_id:
                artifact.finding_id = finding_id
                await self.db.flush()
            return existing, False

        evidence = Evidence(
            finding_id=finding_id,
            kind=(artifact.artifact_type.value if artifact.artifact_type else "artifact").lower(),
            uri=artifact.uri,
            sha256=digest,
            meta={
                "artifact_id": str(artifact.id),
                "campaign_id": str(artifact.campaign_id),
                "branch_id": str(artifact.branch_id) if artifact.branch_id else None,
                "phase_job_id": str(artifact.phase_job_id) if artifact.phase_job_id else None,
                "tool_execution_id": str(artifact.tool_execution_id)
                if artifact.tool_execution_id
                else None,
                "content_hash": artifact.content_hash,
                "mime_type": artifact.mime_type,
                "size_bytes": artifact.size_bytes,
                "description": artifact.description,
                "synthetic": self._is_synthetic(artifact),
            },
        )
        self.db.add(evidence)
        artifact.finding_id = finding_id
        await self.db.flush()

        await record_transition_event(
            self.db,
            event_type="finding.evidence.linked",
            actor=actor,
            message="Artifact linked to finding evidence",
            campaign_id=artifact.campaign_id,
            branch_id=artifact.branch_id,
            phase_job_id=artifact.phase_job_id,
            tool_execution_id=artifact.tool_execution_id,
            artifact_id=artifact.id,
            finding_id=finding_id,
            intention_id=intention_id,
            payload={
                "evidence_id": str(evidence.id),
                "uri": artifact.uri,
                "synthetic": self._is_synthetic(artifact),
            },
        )
        return evidence, True

    async def list_finding_evidence(self, finding_id: UUID) -> list[Evidence]:
        result = await self.db.execute(
            select(Evidence)
            .where(Evidence.finding_id == finding_id, Evidence.is_deleted.is_(False))
            .order_by(Evidence.created_at.asc())
        )
        return list(result.scalars().all())
