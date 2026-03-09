from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import Artifact, CampaignRun, Observation, PhaseJob, Program, ScopeTarget, ToolExecution
from ..models.enums import ObservationTypeEnum, SeverityEnum
from ..models.hil import Finding
from .audit_events import record_transition_event
from .evidence_service import EvidenceService
from .submission_draft_service import SubmissionDraftService


CONTEXT_ONLY_CATEGORIES = {"DISCOVERY", "SIGNAL", "CONTEXT"}
FINDING_ELIGIBLE_CATEGORIES = {"VALIDATION", "DECISION"}


@dataclass
class CorrelationResult:
    observation_id: UUID
    action: str
    finding_id: UUID | None = None
    evidence_created: int = 0
    draft_created: bool = False
    duplicate: bool = False


class FindingCorrelationService:
    """Deterministic Observation -> Finding correlation and evidence linking."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.evidence = EvidenceService(db)
        self.drafts = SubmissionDraftService(db)

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        return " ".join((value or "").strip().lower().split())

    def _category(self, observation: Observation) -> str:
        explicit = self._normalize_text(observation.category).upper()
        if explicit:
            return explicit
        if observation.observation_type is not None:
            return observation.observation_type.value.upper()
        return ObservationTypeEnum.OTHER.value

    @staticmethod
    def _observation_payload(observation: Observation) -> dict[str, Any]:
        return observation.payload_json if isinstance(observation.payload_json, dict) else {}

    async def _campaign(self, campaign_id: UUID) -> CampaignRun | None:
        result = await self.db.execute(select(CampaignRun).where(CampaignRun.id == campaign_id))
        return result.scalar_one_or_none()

    async def _program_name(self, campaign: CampaignRun) -> str:
        result = await self.db.execute(select(Program).where(Program.id == campaign.program_id))
        program = result.scalar_one_or_none()
        if program is None:
            return f"program:{campaign.program_id}"
        return program.name

    async def _execution(self, observation: Observation) -> ToolExecution | None:
        if observation.tool_execution_id is None:
            return None
        result = await self.db.execute(
            select(ToolExecution).where(ToolExecution.id == observation.tool_execution_id)
        )
        return result.scalar_one_or_none()

    async def _finding_by_id(self, finding_id: UUID) -> Finding | None:
        result = await self.db.execute(
            select(Finding).where(Finding.id == finding_id, Finding.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()

    async def _phase_job(self, observation: Observation) -> PhaseJob | None:
        if observation.phase_job_id is None:
            return None
        result = await self.db.execute(select(PhaseJob).where(PhaseJob.id == observation.phase_job_id))
        return result.scalar_one_or_none()

    async def _target_identifier(
        self,
        *,
        observation: Observation,
        campaign: CampaignRun,
        phase_job: PhaseJob | None,
        execution: ToolExecution | None,
    ) -> str:
        payload = self._observation_payload(observation)
        for key in ("target", "target_identifier", "asset", "input_target"):
            raw = payload.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()

        if execution and execution.input_target and execution.input_target.strip():
            return execution.input_target.strip()

        if phase_job and isinstance(phase_job.input_payload_json, dict):
            for key in ("target", "target_identifier", "asset"):
                raw = phase_job.input_payload_json.get(key)
                if isinstance(raw, str) and raw.strip():
                    return raw.strip()

        if campaign.primary_scope_target_id:
            result = await self.db.execute(
                select(ScopeTarget).where(ScopeTarget.id == campaign.primary_scope_target_id)
            )
            scope_target = result.scalar_one_or_none()
            if scope_target and scope_target.target:
                return scope_target.target

        return f"campaign:{campaign.id}"

    def _finding_title(self, observation: Observation, category: str) -> str:
        title = (observation.title or "").strip()
        if title:
            return title[:200]
        return f"{category.title()} observation".strip()

    @staticmethod
    def _severity_for_category(category: str) -> SeverityEnum:
        if category == "VALIDATION":
            return SeverityEnum.LOW
        return SeverityEnum.INFO

    async def _collect_related_artifacts(self, observation: Observation) -> list[Artifact]:
        artifacts: dict[UUID, Artifact] = {}
        if observation.source_artifact_id is not None:
            result = await self.db.execute(
                select(Artifact).where(Artifact.id == observation.source_artifact_id)
            )
            source = result.scalar_one_or_none()
            if source is not None:
                artifacts[source.id] = source

        if observation.tool_execution_id is not None:
            result = await self.db.execute(
                select(Artifact)
                .where(Artifact.tool_execution_id == observation.tool_execution_id)
                .order_by(Artifact.created_at.asc())
            )
            for artifact in result.scalars().all():
                artifacts[artifact.id] = artifact

        return list(artifacts.values())

    async def _matching_finding(
        self,
        *,
        program_name: str,
        target_identifier: str,
        normalized_title: str,
        normalized_category: str,
        campaign_id: UUID,
    ) -> tuple[Finding | None, bool]:
        result = await self.db.execute(
            select(Finding)
            .where(
                Finding.program == program_name,
                Finding.asset == target_identifier,
                Finding.is_deleted.is_(False),
            )
            .order_by(Finding.created_at.asc())
        )
        for finding in result.scalars().all():
            scope_json = finding.scope_json if isinstance(finding.scope_json, dict) else {}
            same_campaign = str(scope_json.get("campaign_id")) == str(campaign_id)
            candidate_title = str(scope_json.get("normalized_title") or self._normalize_text(finding.title))
            same_title = candidate_title == normalized_title
            same_category = str(scope_json.get("normalized_category")) == normalized_category
            same_target = str(scope_json.get("target_identifier")) == target_identifier
            if same_campaign and same_title and same_category and same_target:
                return finding, True
        return None, False

    async def _create_finding(
        self,
        *,
        observation: Observation,
        campaign: CampaignRun,
        program_name: str,
        target_identifier: str,
        title: str,
        normalized_title: str,
        normalized_category: str,
        actor: str | None,
        intention_id: UUID | None,
    ) -> Finding:
        description = (
            observation.summary.strip()
            if observation.summary and observation.summary.strip()
            else "Correlated from canonical observation. Human validation required before submission."
        )
        finding = Finding(
            program=program_name,
            asset=target_identifier,
            title=title,
            description=description,
            severity=self._severity_for_category(normalized_category),
            scope_json={
                "campaign_id": str(campaign.id),
                "branch_id": str(observation.branch_id) if observation.branch_id else None,
                "phase_job_id": str(observation.phase_job_id) if observation.phase_job_id else None,
                "tool_execution_id": str(observation.tool_execution_id)
                if observation.tool_execution_id
                else None,
                "source_observation_id": str(observation.id),
                "normalized_title": normalized_title,
                "normalized_category": normalized_category,
                "target_identifier": target_identifier,
                "deterministic_correlation": True,
            },
        )
        self.db.add(finding)
        await self.db.flush()

        await record_transition_event(
            self.db,
            event_type="finding.correlation.created",
            actor=actor,
            message="Finding created from observation correlation",
            campaign_id=campaign.id,
            branch_id=observation.branch_id,
            phase_job_id=observation.phase_job_id,
            tool_execution_id=observation.tool_execution_id,
            finding_id=finding.id,
            observation_id=observation.id,
            intention_id=intention_id,
            payload={
                "category": normalized_category,
                "target_identifier": target_identifier,
                "title": title,
            },
        )
        return finding

    async def _attach_observation_to_finding(
        self,
        *,
        observation: Observation,
        finding: Finding,
        campaign: CampaignRun,
        actor: str | None,
        intention_id: UUID | None,
        duplicate: bool,
        already_linked: bool,
    ) -> None:
        observation.finding_id = finding.id
        await self.db.flush()
        if duplicate:
            event_type = "finding.correlation.deduplicated"
            message = "Observation attached to existing finding via duplicate criteria"
        elif already_linked:
            event_type = "finding.correlation.already_linked"
            message = "Observation was already linked to finding"
        else:
            event_type = "finding.correlation.attached_existing"
            message = "Observation attached to existing finding"
        await record_transition_event(
            self.db,
            event_type=event_type,
            actor=actor,
            message=message,
            campaign_id=campaign.id,
            branch_id=observation.branch_id,
            phase_job_id=observation.phase_job_id,
            tool_execution_id=observation.tool_execution_id,
            finding_id=finding.id,
            observation_id=observation.id,
            intention_id=intention_id,
            payload={"duplicate": duplicate},
        )

    async def process_observation(
        self,
        observation: Observation,
        *,
        actor: str | None = None,
    ) -> CorrelationResult:
        category = self._category(observation)
        intention_id = observation.intention_id

        campaign = await self._campaign(observation.campaign_id)
        if campaign is None:
            raise ValueError(f"Campaign not found: {observation.campaign_id}")

        if category in CONTEXT_ONLY_CATEGORIES:
            await record_transition_event(
                self.db,
                event_type="finding.correlation.context_only",
                actor=actor,
                message="Observation kept as context only; no finding created",
                campaign_id=observation.campaign_id,
                branch_id=observation.branch_id,
                phase_job_id=observation.phase_job_id,
                tool_execution_id=observation.tool_execution_id,
                observation_id=observation.id,
                intention_id=intention_id,
                payload={"category": category},
            )
            return CorrelationResult(observation_id=observation.id, action="CONTEXT_ONLY")

        if category not in FINDING_ELIGIBLE_CATEGORIES:
            await record_transition_event(
                self.db,
                event_type="finding.correlation.unsupported_category",
                actor=actor,
                message="Observation category is not eligible for finding creation",
                campaign_id=observation.campaign_id,
                observation_id=observation.id,
                intention_id=intention_id,
                payload={"category": category},
            )
            return CorrelationResult(observation_id=observation.id, action="UNSUPPORTED")

        execution = await self._execution(observation)
        phase_job = await self._phase_job(observation)
        target_identifier = await self._target_identifier(
            observation=observation,
            campaign=campaign,
            phase_job=phase_job,
            execution=execution,
        )
        program_name = await self._program_name(campaign)
        title = self._finding_title(observation, category)
        normalized_title = self._normalize_text(title)
        normalized_category = self._normalize_text(category).upper()

        finding: Finding | None = None
        already_linked = False
        duplicate = False

        if observation.finding_id is not None:
            finding = await self._finding_by_id(observation.finding_id)
            if finding is not None:
                already_linked = True

        if finding is None:
            finding, duplicate = await self._matching_finding(
                program_name=program_name,
                target_identifier=target_identifier,
                normalized_title=normalized_title,
                normalized_category=normalized_category,
                campaign_id=campaign.id,
            )

        created_new = finding is None
        if finding is None:
            finding = await self._create_finding(
                observation=observation,
                campaign=campaign,
                program_name=program_name,
                target_identifier=target_identifier,
                title=title,
                normalized_title=normalized_title,
                normalized_category=normalized_category,
                actor=actor,
                intention_id=intention_id,
            )
        await self._attach_observation_to_finding(
            observation=observation,
            finding=finding,
            campaign=campaign,
            actor=actor,
            intention_id=intention_id,
            duplicate=duplicate,
            already_linked=already_linked,
        )

        artifacts = await self._collect_related_artifacts(observation)
        evidence_created = 0
        for artifact in artifacts:
            _evidence, created = await self.evidence.attach_artifact_to_finding(
                finding_id=finding.id,
                artifact=artifact,
                actor=actor,
                intention_id=intention_id,
            )
            if created:
                evidence_created += 1

        draft = await self.drafts.upsert_draft_for_finding(
            finding=finding,
            campaign_id=observation.campaign_id,
            branch_id=observation.branch_id,
            intention_id=intention_id,
            actor=actor,
            duplicate_detected=duplicate and not already_linked,
        )

        return CorrelationResult(
            observation_id=observation.id,
            action=(
                "CREATED"
                if created_new
                else "ALREADY_LINKED"
                if already_linked
                else "ATTACHED"
            ),
            finding_id=finding.id,
            evidence_created=evidence_created,
            draft_created=draft is not None,
            duplicate=duplicate,
        )

    async def process_campaign(
        self,
        campaign_id: UUID,
        *,
        actor: str | None = None,
    ) -> dict[str, int]:
        result = await self.db.execute(
            select(Observation)
            .where(Observation.campaign_id == campaign_id, Observation.finding_id.is_(None))
            .order_by(Observation.created_at.asc())
        )
        observations = list(result.scalars().all())

        summary = {
            "processed": 0,
            "created_findings": 0,
            "attached_existing": 0,
            "context_only": 0,
            "duplicates": 0,
            "evidence_created": 0,
        }
        for observation in observations:
            outcome = await self.process_observation(observation, actor=actor)
            summary["processed"] += 1
            summary["evidence_created"] += outcome.evidence_created
            if outcome.action == "CREATED":
                summary["created_findings"] += 1
            elif outcome.action in {"ATTACHED", "ALREADY_LINKED"}:
                summary["attached_existing"] += 1
            elif outcome.action == "CONTEXT_ONLY":
                summary["context_only"] += 1
            if outcome.duplicate:
                summary["duplicates"] += 1

        await record_transition_event(
            self.db,
            event_type="finding.correlation.campaign_run",
            actor=actor,
            message="Campaign observation correlation run completed",
            campaign_id=campaign_id,
            payload=summary,
        )
        return summary
