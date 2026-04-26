from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

logger = logging.getLogger(__name__)

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .audit_events import record_transition_event
from .bugbounty_workflow_engine import WORKFLOW_TEMPLATES
from .credentials_manager import CredentialsManager
from .evidence_qualification_engine import qualify_evidence
from .helpers import workflow_output_root
from .impact_validation_engine import resolve_submission_candidate_decision, validate_impact
from .phase9_alert_case_service import Phase9AlertCaseService
from .platform_integrations.hackerone_client import HackerOneClient
from .secret_manager import get_secret_manager
from .scope_guardrails import ScopePolicy, evaluate_target_scope
from .tool_health_service import build_dashboard
from .tool_registry_catalog import get_catalog_entry
from .workflow_executor import WorkflowExecutor
from ..models.bug_bounty import (
    AnalystQueueItem,
    HuntReadinessRecord,
    HuntScheduleJob,
    WorkflowDeltaRecord,
)
from ..models.campaign import Artifact, Program, ScopeTarget, SubmissionDraft
from ..models.enums import ArtifactTypeEnum, WorkflowRunStatusEnum
from ..models.workflow import WorkflowFinding, WorkflowRun
from ..schemas.bug_bounty_hunt import (
    CandidateQueueUpdateRequest,
    GenerateReportDraftResponse,
    HuntScheduleCreateRequest,
    HuntScheduleUpdateRequest,
    MonitoredTargetUpdateRequest,
    ProgramOpportunityImportRequest,
    ReadinessCheckResponse,
    ScheduleDispatchResponse,
    ScheduleTriggerResponse,
    SchedulerStatusResponse,
    ScopeAssetInput,
)


READINESS_READY = "READY"
READINESS_BLOCKED_SCOPE = "BLOCKED_BY_SCOPE"
READINESS_BLOCKED_POLICY = "BLOCKED_BY_PROGRAM_POLICY"
READINESS_BLOCKED_HEALTH = "BLOCKED_BY_HEALTH"
READINESS_BLOCKED_CONFIG = "BLOCKED_BY_CONFIG"
READINESS_BLOCKED_COOLDOWN = "BLOCKED_BY_COOLDOWN"
READINESS_BLOCKED_DISABLED_TARGET = "BLOCKED_BY_DISABLED_TARGET"
READINESS_BLOCKED_SAFETY = "BLOCKED_BY_SAFETY_POLICY"

SCHEDULE_ACTIVE = "ACTIVE"
SCHEDULE_PAUSED = "PAUSED"
SCHEDULE_DISABLED = "DISABLED"
SCHEDULE_ERROR = "ERROR"

_HTTP_LINK_RE = re.compile(r"https?://[^\s<>)\"']+", re.IGNORECASE)
_PLATFORM_API_KEY_HINTS: dict[str, str] = {
    "GITHUB_TOKEN": "https://github.com/settings/tokens",
    "SHODAN_API_KEY": "https://account.shodan.io/",
    "SECURITYTRAILS_API_KEY": "https://securitytrails.com/corp/api",
    "VIRUSTOTAL_API_KEY": "https://www.virustotal.com/gui/join-us",
    "CHAOS_API_KEY": "https://chaos.projectdiscovery.io/",
    "TRILIUM_FREE_TIER_API_KEY": "https://trilium.cc/",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coalesce_json(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


async def _run_in_thread(func, /, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
    return await asyncio.to_thread(func, *args, **kwargs)


@dataclass
class _ReadinessDecision:
    status: str
    reason: str
    details: dict[str, Any]


class BugBountyHuntingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_programs(self) -> list[Program]:
        result = await self.db.execute(select(Program).order_by(Program.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    def _extract_urls(*chunks: str | None) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()
        for chunk in chunks:
            text = str(chunk or "")
            for match in _HTTP_LINK_RE.findall(text):
                cleaned = match.rstrip(".,;)]\"'")
                if cleaned in seen:
                    continue
                seen.add(cleaned)
                found.append(cleaned)
        return found

    @staticmethod
    def _derive_hackerone_handle(payload: ProgramOpportunityImportRequest) -> str | None:
        handle = str(payload.handle or "").strip()
        if handle:
            return handle
        program_key = str(payload.program_key or "").strip()
        if ":" in program_key:
            candidate = program_key.split(":", 1)[1].strip()
            if candidate:
                return candidate
        url = str(payload.program_url or "").strip()
        if not url:
            return None
        parsed = urlparse(url)
        parts = [item for item in parsed.path.split("/") if item]
        if not parts:
            return None
        return parts[-1]

    @staticmethod
    def _target_type_from_h1_asset(asset_type: str, identifier: str) -> str:
        normalized_type = str(asset_type or "").strip().lower()
        if normalized_type in {"cidr", "url", "domain", "wildcard"}:
            return normalized_type
        if normalized_type in {"ip", "ip_address"}:
            return "ip"
        if str(identifier).strip().startswith("*."):
            return "wildcard"
        if "://" in str(identifier):
            return "url"
        return "domain"

    @staticmethod
    def _looks_out_of_scope(instruction: str | None) -> bool:
        text = str(instruction or "").strip().lower()
        if not text:
            return False
        flags = (
            "out of scope",
            "not in scope",
            "excluded",
            "do not test",
            "prohibited",
            "forbidden",
        )
        return any(flag in text for flag in flags)

    @staticmethod
    def _merge_scope_assets(
        explicit_assets: list[ScopeAssetInput],
        discovered_assets: list[ScopeAssetInput],
    ) -> list[ScopeAssetInput]:
        merged: dict[tuple[str, str], ScopeAssetInput] = {}
        for asset in discovered_assets:
            key = (asset.target.strip().lower(), asset.target_type.strip().lower())
            merged[key] = asset
        for asset in explicit_assets:
            key = (asset.target.strip().lower(), asset.target_type.strip().lower())
            merged[key] = asset
        return list(merged.values())

    async def _fetch_platform_enrichment(
        self,
        payload: ProgramOpportunityImportRequest,
    ) -> dict[str, Any]:
        enrichment: dict[str, Any] = {
            "status": "skipped",
            "source": "none",
            "warnings": [],
            "rules_text": None,
            "submission_guidelines": None,
            "in_scope_assets": [],
            "out_of_scope_assets": [],
            "artifact_urls": [],
        }
        platform = str(payload.platform or "").strip().lower()
        if not payload.auto_fetch_platform_data:
            return enrichment
        if platform != "hackerone":
            enrichment["warnings"].append(
                "automatic platform enrichment currently supports platform=hackerone"
            )
            return enrichment

        handle = self._derive_hackerone_handle(payload)
        if not handle:
            enrichment["warnings"].append(
                "hackerone enrichment skipped: missing handle/program_key/program_url slug"
            )
            return enrichment

        api_key = str(payload.platform_api_key or "").strip()
        api_secret = str(payload.platform_api_secret or "").strip()
        if not api_key or not api_secret:
            secret_manager = get_secret_manager()
            if not api_key:
                api_key = (
                    str(secret_manager.get_optional("HACKERONE_API_KEY") or "").strip()
                    or str(secret_manager.get_optional("H1_API_KEY") or "").strip()
                )
            if not api_secret:
                api_secret = (
                    str(secret_manager.get_optional("HACKERONE_API_SECRET") or "").strip()
                    or str(secret_manager.get_optional("H1_API_SECRET") or "").strip()
                )
        if not api_key or not api_secret:
            enrichment["warnings"].append(
                "hackerone enrichment skipped: missing platform API credentials"
            )
            enrichment["artifact_urls"] = ["https://hackerone.com/hackers/settings/api_token"]
            return enrichment

        client = HackerOneClient(api_key=api_key, api_secret=api_secret)
        try:
            if not await client.authenticate():
                enrichment["warnings"].append(
                    f"hackerone enrichment failed: authentication failed for handle={handle}"
                )
                return enrichment
            program_details = await client.get_program_details(handle)
            if not isinstance(program_details, dict):
                enrichment["warnings"].append(
                    f"hackerone enrichment failed: no program payload for handle={handle}"
                )
                return enrichment

            enrichment["status"] = "fetched"
            enrichment["source"] = "hackerone_api"
            policy_text = str(program_details.get("policy") or "").strip()
            if policy_text:
                enrichment["rules_text"] = policy_text
                enrichment["submission_guidelines"] = policy_text

            discovered_in_scope: list[ScopeAssetInput] = []
            discovered_out_scope: list[ScopeAssetInput] = []
            scopes = program_details.get("structured_scopes", {})
            edges = scopes.get("edges", []) if isinstance(scopes, dict) else []
            for edge in edges:
                node = edge.get("node", edge) if isinstance(edge, dict) else {}
                identifier = str(node.get("asset_identifier") or "").strip()
                if not identifier:
                    continue
                asset_type = self._target_type_from_h1_asset(
                    str(node.get("asset_type") or ""),
                    identifier,
                )
                instruction = str(node.get("instruction") or "").strip()
                candidate = ScopeAssetInput(
                    target=identifier,
                    target_type=asset_type,
                    monitoring_enabled=not self._looks_out_of_scope(instruction),
                    safe_mode_required=True,
                    priority_tier=3,
                    notes=instruction[:2000] if instruction else None,
                )
                if self._looks_out_of_scope(instruction):
                    discovered_out_scope.append(candidate)
                else:
                    discovered_in_scope.append(candidate)

            enrichment["in_scope_assets"] = discovered_in_scope
            enrichment["out_of_scope_assets"] = discovered_out_scope
            enrichment["artifact_urls"] = self._extract_urls(
                payload.program_url,
                policy_text,
                str(payload.submission_guidelines or ""),
            )
            return enrichment
        except Exception as exc:
            enrichment["warnings"].append(f"hackerone enrichment error: {exc}")
            return enrichment
        finally:
            try:
                await client.close()
            except Exception:
                pass

    async def import_program_opportunity(
        self,
        payload: ProgramOpportunityImportRequest,
        *,
        actor: str,
    ) -> Program:
        enrichment = await self._fetch_platform_enrichment(payload)
        if (
            payload.auto_fetch_platform_data
            and not payload.allow_partial_platform_data
            and enrichment.get("status") != "fetched"
        ):
            raise ValueError(
                "platform enrichment required but unavailable; provide API credentials or disable strict enrichment"
            )

        resolved_rules_text = payload.rules_text or enrichment.get("rules_text")
        resolved_submission_guidelines = (
            payload.submission_guidelines or enrichment.get("submission_guidelines")
        )
        resolved_handle = payload.handle or self._derive_hackerone_handle(payload)
        merged_in_scope_assets = self._merge_scope_assets(
            explicit_assets=list(payload.in_scope_assets),
            discovered_assets=list(enrichment.get("in_scope_assets") or []),
        )
        merged_out_of_scope_assets = self._merge_scope_assets(
            explicit_assets=list(payload.out_of_scope_assets),
            discovered_assets=list(enrichment.get("out_of_scope_assets") or []),
        )

        stmt = select(Program).where(Program.program_key == payload.program_key) if payload.program_key else select(
            Program
        ).where(
            Program.name == payload.name,
            Program.platform == payload.platform,
        )
        result = await self.db.execute(stmt.limit(1))
        program = result.scalar_one_or_none()
        now = _utcnow()
        if program is None:
            program = Program(
                program_key=payload.program_key,
                name=payload.name,
                platform=payload.platform,
                handle=resolved_handle,
                policy_url=payload.program_url,
                status=payload.status,
                created_by=actor,
                config_json={},
            )
            self.db.add(program)
            await self.db.flush()
        else:
            program.name = payload.name
            program.platform = payload.platform
            program.handle = resolved_handle
            program.policy_url = payload.program_url
            program.status = payload.status

        config = _coalesce_json(program.config_json)
        config["opportunity"] = {
            "source": payload.source,
            "program_url": payload.program_url,
            "rules_text": resolved_rules_text,
            "submission_guidelines": resolved_submission_guidelines,
            "testing_restrictions": payload.testing_restrictions,
            "disclosure_restrictions": payload.disclosure_restrictions,
            "disclosure_policy": payload.disclosure_policy,
            "allowed_asset_types": payload.allowed_asset_types,
            "disallowed_workflows": payload.disallowed_workflows,
            "require_safe_mode": payload.require_safe_mode,
            "reward_metadata": payload.reward_metadata,
            "notes": payload.notes,
            "platform_enrichment": {
                "status": enrichment.get("status"),
                "source": enrichment.get("source"),
                "warnings": list(enrichment.get("warnings") or []),
                "artifact_urls": list(enrichment.get("artifact_urls") or []),
                "last_fetch_at": now.isoformat() if enrichment.get("status") == "fetched" else None,
            },
            "imported_at": now.isoformat(),
            "last_synced_at": now.isoformat(),
        }
        program.config_json = config

        for asset in merged_in_scope_assets:
            await self._upsert_scope_target(
                program=program,
                target=asset.target,
                target_type=asset.target_type,
                is_in_scope=True,
                monitoring_enabled=asset.monitoring_enabled,
                safe_mode_required=asset.safe_mode_required,
                priority_tier=asset.priority_tier,
                monitoring_source=f"import:{payload.source}",
                monitoring_notes=asset.notes,
            )
        for asset in merged_out_of_scope_assets:
            await self._upsert_scope_target(
                program=program,
                target=asset.target,
                target_type=asset.target_type,
                is_in_scope=False,
                monitoring_enabled=False,
                safe_mode_required=True,
                priority_tier=asset.priority_tier,
                monitoring_source=f"import:{payload.source}",
                monitoring_notes=asset.notes,
            )

        await self._ensure_default_access_metadata(
            program=program,
            platform=str(payload.platform or ""),
            enrichment=enrichment,
        )

        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="bugbounty.program.imported",
            actor=actor,
            message=f"Program opportunity imported: {program.name}",
            payload={
                "program_id": str(program.id),
                "source": payload.source,
                "in_scope_assets": len(merged_in_scope_assets),
                "out_of_scope_assets": len(merged_out_of_scope_assets),
                "platform_enrichment_status": enrichment.get("status"),
            },
        )
        # Refresh to load server-side values (e.g. updated_at set via onupdate)
        # that are marked expired after the config_json UPDATE flush.
        await self.db.refresh(program)
        return program

    @staticmethod
    def _resolve_required_secrets(required_keys: list[str]) -> tuple[list[str], list[str]]:
        manager = get_secret_manager()
        present: list[str] = []
        missing: list[str] = []
        for key in sorted({str(item).strip() for item in required_keys if str(item).strip()}):
            value = manager.get_optional(key)
            if value:
                present.append(key)
            else:
                missing.append(key)
        return present, missing

    async def _ensure_default_access_metadata(
        self,
        *,
        program: Program,
        platform: str,
        enrichment: dict[str, Any],
    ) -> None:
        existing_result = await self.db.execute(
            text(
                "SELECT access_type FROM opportunity_access_metadata WHERE program_id = :program_id"
            ),
            {"program_id": program.id},
        )
        existing_types = {
            str(row[0]).strip().lower()
            for row in existing_result.fetchall()
            if row and str(row[0]).strip()
        }

        mgr = CredentialsManager(self.db)
        platform_norm = str(platform or "").strip().lower()
        defaults: list[tuple[str, str | None, str | None]] = [
            ("unauthenticated", None, "Public surface scanning without account credentials."),
        ]
        if platform_norm == "hackerone":
            defaults.extend(
                [
                    (
                        "user_account",
                        "https://hackerone.com/users/sign_up",
                        "Create or use an existing HackerOne researcher account.",
                    ),
                    (
                        "api_key",
                        "https://hackerone.com/hackers/settings/api_token",
                        "Generate a HackerOne API token pair (identifier + secret).",
                    ),
                    (
                        "hunter_account",
                        "https://hackerone.com/users/sign_up",
                        "Optional dedicated hunter account for isolated testing.",
                    ),
                ]
            )
        elif enrichment.get("artifact_urls"):
            defaults.append(
                (
                    "user_account",
                    list(enrichment.get("artifact_urls"))[0],
                    "Program documentation contains onboarding links for authenticated testing.",
                )
            )

        for access_type, signup_url, instructions in defaults:
            if access_type in existing_types:
                continue
            await mgr.upsert_access_metadata(
                program_id=program.id,
                access_type=access_type,
                enabled=True,
                signup_url=signup_url,
                signup_instructions=instructions,
            )

    @staticmethod
    def _credential_setup_hints(
        *,
        missing_keys: list[str],
        scanning_warnings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        hints: list[dict[str, Any]] = []
        seen_links: set[str] = set()
        for key in missing_keys:
            signup_url = _PLATFORM_API_KEY_HINTS.get(key)
            if not signup_url:
                continue
            if signup_url in seen_links:
                continue
            seen_links.add(signup_url)
            hints.append(
                {
                    "type": "api_key",
                    "key": key,
                    "signup_url": signup_url,
                    "message": f"Generate/store {key} to unlock higher-coverage scans.",
                }
            )
        for warning in scanning_warnings:
            signup_url = str(warning.get("signup_url") or "").strip()
            if not signup_url or signup_url in seen_links:
                continue
            seen_links.add(signup_url)
            hints.append(
                {
                    "type": str(warning.get("access_type") or "credential"),
                    "key": str(warning.get("access_type") or "credential"),
                    "signup_url": signup_url,
                    "message": str(warning.get("message") or "Credentials not configured."),
                    "signup_instructions": warning.get("signup_instructions"),
                }
            )
        return hints

    async def _upsert_scope_target(
        self,
        *,
        program: Program,
        target: str,
        target_type: str,
        is_in_scope: bool,
        monitoring_enabled: bool,
        safe_mode_required: bool,
        priority_tier: int,
        monitoring_source: str | None,
        monitoring_notes: str | None,
    ) -> ScopeTarget:
        result = await self.db.execute(
            select(ScopeTarget).where(
                ScopeTarget.program_id == program.id,
                ScopeTarget.target == target,
                ScopeTarget.target_type == target_type,
            )
        )
        scope_target = result.scalar_one_or_none()
        if scope_target is None:
            scope_target = ScopeTarget(
                program_id=program.id,
                target=target,
                target_type=target_type,
                is_in_scope=is_in_scope,
                details_json={},
            )
            self.db.add(scope_target)
            await self.db.flush()
        scope_target.is_in_scope = is_in_scope
        scope_target.monitoring_enabled = monitoring_enabled
        scope_target.safe_mode_required = safe_mode_required
        scope_target.monitoring_priority_tier = max(1, min(priority_tier, 5))
        scope_target.monitoring_source = monitoring_source
        scope_target.monitoring_notes = monitoring_notes
        scope_target.monitoring_status = "ACTIVE" if monitoring_enabled else "DISABLED"
        return scope_target

    async def list_monitored_targets(self, program_id: UUID | None = None) -> list[ScopeTarget]:
        stmt: Select[tuple[ScopeTarget]] = select(ScopeTarget).order_by(
            ScopeTarget.created_at.desc()
        )
        if program_id is not None:
            stmt = stmt.where(ScopeTarget.program_id == program_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_monitored_target(
        self,
        scope_target_id: UUID,
        payload: MonitoredTargetUpdateRequest,
        *,
        actor: str,
    ) -> ScopeTarget:
        result = await self.db.execute(select(ScopeTarget).where(ScopeTarget.id == scope_target_id))
        scope_target = result.scalar_one_or_none()
        if scope_target is None:
            raise ValueError("Monitored target not found")

        if payload.monitoring_enabled is not None:
            scope_target.monitoring_enabled = payload.monitoring_enabled
            scope_target.monitoring_status = (
                scope_target.monitoring_status
                if payload.monitoring_enabled
                else "DISABLED"
            )
        if payload.monitoring_priority_tier is not None:
            scope_target.monitoring_priority_tier = payload.monitoring_priority_tier
        if payload.monitoring_status is not None:
            scope_target.monitoring_status = payload.monitoring_status
        if payload.monitoring_source is not None:
            scope_target.monitoring_source = payload.monitoring_source
        if payload.monitoring_notes is not None:
            scope_target.monitoring_notes = payload.monitoring_notes
        if payload.safe_mode_required is not None:
            scope_target.safe_mode_required = payload.safe_mode_required
        if payload.next_scheduled_run_at is not None:
            scope_target.next_scheduled_run_at = payload.next_scheduled_run_at
        if payload.details_json is not None:
            merged = _coalesce_json(scope_target.details_json)
            merged.update(payload.details_json)
            scope_target.details_json = merged

        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="bugbounty.target.updated",
            actor=actor,
            message=f"Monitored target updated: {scope_target.target}",
            payload={"scope_target_id": str(scope_target.id)},
        )
        return scope_target

    async def create_schedule(self, payload: HuntScheduleCreateRequest) -> HuntScheduleJob:
        scope_target = await self.db.scalar(
            select(ScopeTarget).where(
                ScopeTarget.id == payload.scope_target_id,
                ScopeTarget.program_id == payload.program_id,
            )
        )
        if scope_target is None:
            raise ValueError("Scope target does not belong to supplied program")
        if payload.workflow_template not in WORKFLOW_TEMPLATES:
            raise ValueError(f"Unknown workflow template: {payload.workflow_template}")
        if payload.schedule_type == "cron" and not payload.cron_expr:
            raise ValueError("cron_expr is required when schedule_type is 'cron'")

        existing = await self.db.scalar(
            select(HuntScheduleJob).where(
                HuntScheduleJob.program_id == payload.program_id,
                HuntScheduleJob.scope_target_id == payload.scope_target_id,
                HuntScheduleJob.workflow_template == payload.workflow_template,
            )
        )
        if existing is not None:
            raise ValueError("Schedule already exists for program/target/template")

        schedule = HuntScheduleJob(
            program_id=payload.program_id,
            scope_target_id=payload.scope_target_id,
            workflow_template=payload.workflow_template,
            schedule_type=payload.schedule_type,
            interval_minutes=payload.interval_minutes if payload.schedule_type == "interval" else None,
            cron_expr=payload.cron_expr if payload.schedule_type == "cron" else None,
            status=SCHEDULE_ACTIVE,
            safe_mode=payload.safe_mode,
            dry_run=payload.dry_run,
            priority_tier=payload.priority_tier,
            max_concurrency=payload.max_concurrency,
            cooldown_minutes=payload.cooldown_minutes,
            failure_backoff_minutes=payload.failure_backoff_minutes,
            failure_pause_threshold=payload.failure_pause_threshold,
            next_scheduled_run_at=payload.next_scheduled_run_at or _utcnow(),
            created_by=payload.created_by,
            updated_by=payload.created_by,
            config_json=payload.config_json,
        )
        self.db.add(schedule)
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="bugbounty.schedule.created",
            actor=payload.created_by,
            message=f"Created schedule for {scope_target.target}",
            payload={
                "schedule_id": str(schedule.id),
                "workflow_template": schedule.workflow_template,
            },
        )
        return schedule

    async def list_schedules(
        self,
        *,
        program_id: UUID | None = None,
        status: str | None = None,
    ) -> list[HuntScheduleJob]:
        stmt: Select[tuple[HuntScheduleJob]] = select(HuntScheduleJob).order_by(
            HuntScheduleJob.next_scheduled_run_at.asc().nullsfirst(),
            HuntScheduleJob.created_at.desc(),
        )
        if program_id is not None:
            stmt = stmt.where(HuntScheduleJob.program_id == program_id)
        if status is not None:
            stmt = stmt.where(HuntScheduleJob.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_schedule(self, schedule_id: UUID) -> HuntScheduleJob | None:
        return await self.db.scalar(
            select(HuntScheduleJob).where(HuntScheduleJob.id == schedule_id)
        )

    async def get_schedule_for_target(
        self,
        *,
        program_id: UUID,
        scope_target_id: UUID,
        workflow_template: str,
    ) -> HuntScheduleJob | None:
        return await self.db.scalar(
            select(HuntScheduleJob).where(
                HuntScheduleJob.program_id == program_id,
                HuntScheduleJob.scope_target_id == scope_target_id,
                HuntScheduleJob.workflow_template == workflow_template,
            )
        )

    async def update_schedule(
        self,
        schedule_id: UUID,
        payload: HuntScheduleUpdateRequest,
    ) -> HuntScheduleJob:
        schedule = await self.db.scalar(select(HuntScheduleJob).where(HuntScheduleJob.id == schedule_id))
        if schedule is None:
            raise ValueError("Schedule not found")
        if payload.status is not None:
            schedule.status = payload.status
            if payload.status == SCHEDULE_PAUSED:
                schedule.paused_at = _utcnow()
                schedule.paused_reason = payload.paused_reason
        if payload.interval_minutes is not None:
            schedule.interval_minutes = payload.interval_minutes
        if payload.cron_expr is not None:
            schedule.cron_expr = payload.cron_expr
        if payload.safe_mode is not None:
            schedule.safe_mode = payload.safe_mode
        if payload.dry_run is not None:
            schedule.dry_run = payload.dry_run
        if payload.max_concurrency is not None:
            schedule.max_concurrency = payload.max_concurrency
        if payload.cooldown_minutes is not None:
            schedule.cooldown_minutes = payload.cooldown_minutes
        if payload.failure_backoff_minutes is not None:
            schedule.failure_backoff_minutes = payload.failure_backoff_minutes
        if payload.failure_pause_threshold is not None:
            schedule.failure_pause_threshold = payload.failure_pause_threshold
        if payload.next_scheduled_run_at is not None:
            schedule.next_scheduled_run_at = payload.next_scheduled_run_at
        if payload.config_json is not None:
            merged = _coalesce_json(schedule.config_json)
            merged.update(payload.config_json)
            schedule.config_json = merged
        schedule.updated_by = payload.updated_by
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="bugbounty.schedule.updated",
            actor=payload.updated_by,
            message=f"Updated schedule {schedule.id}",
            payload={"schedule_id": str(schedule.id), "status": schedule.status},
        )
        return schedule

    async def _build_program_scope_policy(self, program_id: UUID) -> ScopePolicy:
        records = await self.db.execute(
            select(ScopeTarget).where(ScopeTarget.program_id == program_id)
        )
        allowlist: list[str] = []
        denylist: list[str] = []
        cidr_allowlist: list[str] = []
        for target in records.scalars().all():
            if target.target_type.lower() == "cidr":
                if target.is_in_scope:
                    cidr_allowlist.append(target.target)
                continue
            if target.is_in_scope:
                allowlist.append(target.target)
            else:
                denylist.append(target.target)
        return ScopePolicy(
            allowlist=allowlist,
            denylist=denylist,
            cidr_allowlist=cidr_allowlist,
            safe_mode_default=True,
            strict_allowlist=bool(allowlist),
        )

    async def _active_schedule_runs(self, schedule: HuntScheduleJob) -> int:
        result = await self.db.execute(
            select(func.count(WorkflowRun.id)).where(
                WorkflowRun.status == WorkflowRunStatusEnum.RUNNING,
                WorkflowRun.trigger_source.like(f"SCHEDULER:{schedule.id}%"),
            )
        )
        return int(result.scalar() or 0)

    async def evaluate_readiness(
        self,
        schedule: HuntScheduleJob,
        *,
        trigger_source: str = "scheduler",
        persist: bool = True,
    ) -> ReadinessCheckResponse:
        details: dict[str, Any] = {"schedule_id": str(schedule.id)}
        now = _utcnow()
        target = await self.db.scalar(select(ScopeTarget).where(ScopeTarget.id == schedule.scope_target_id))
        program = await self.db.scalar(select(Program).where(Program.id == schedule.program_id))
        if target is None or program is None:
            decision = _ReadinessDecision(
                status=READINESS_BLOCKED_CONFIG,
                reason="schedule target/program reference is invalid",
                details=details,
            )
            return await self._persist_readiness(decision, schedule, None, trigger_source, persist)

        details["target"] = target.target
        details["program"] = program.name
        if schedule.status != SCHEDULE_ACTIVE:
            decision = _ReadinessDecision(
                status=READINESS_BLOCKED_CONFIG,
                reason=f"schedule status is {schedule.status}",
                details=details,
            )
            return await self._persist_readiness(decision, schedule, target, trigger_source, persist)
        if not target.monitoring_enabled:
            decision = _ReadinessDecision(
                status=READINESS_BLOCKED_DISABLED_TARGET,
                reason="target monitoring is disabled",
                details=details,
            )
            return await self._persist_readiness(decision, schedule, target, trigger_source, persist)
        if not target.is_in_scope:
            decision = _ReadinessDecision(
                status=READINESS_BLOCKED_SCOPE,
                reason="target marked out-of-scope in canonical program scope",
                details=details,
            )
            return await self._persist_readiness(decision, schedule, target, trigger_source, persist)
        if schedule.next_scheduled_run_at is not None and schedule.next_scheduled_run_at > now:
            decision = _ReadinessDecision(
                status=READINESS_BLOCKED_COOLDOWN,
                reason="next scheduled run is in the future",
                details={
                    **details,
                    "next_scheduled_run_at": schedule.next_scheduled_run_at.isoformat(),
                },
            )
            return await self._persist_readiness(decision, schedule, target, trigger_source, persist)
        if schedule.last_run_finished_at is not None:
            cooldown_until = schedule.last_run_finished_at + timedelta(minutes=schedule.cooldown_minutes)
            if now < cooldown_until:
                decision = _ReadinessDecision(
                    status=READINESS_BLOCKED_COOLDOWN,
                    reason="cooldown window still active",
                    details={**details, "cooldown_until": cooldown_until.isoformat()},
                )
                return await self._persist_readiness(decision, schedule, target, trigger_source, persist)
        if schedule.max_concurrency > 0 and await self._active_schedule_runs(schedule) >= schedule.max_concurrency:
            decision = _ReadinessDecision(
                status=READINESS_BLOCKED_CONFIG,
                reason="max concurrency reached for schedule",
                details=details,
            )
            return await self._persist_readiness(decision, schedule, target, trigger_source, persist)

        template = WORKFLOW_TEMPLATES.get(schedule.workflow_template)
        if template is None:
            decision = _ReadinessDecision(
                status=READINESS_BLOCKED_CONFIG,
                reason=f"unknown workflow template: {schedule.workflow_template}",
                details=details,
            )
            return await self._persist_readiness(decision, schedule, target, trigger_source, persist)

        config = _coalesce_json(program.config_json).get("opportunity") if program.config_json else {}
        config = config if isinstance(config, dict) else {}
        if schedule.workflow_template in {str(x) for x in config.get("disallowed_workflows", [])}:
            decision = _ReadinessDecision(
                status=READINESS_BLOCKED_POLICY,
                reason=f"workflow template blocked by program policy: {schedule.workflow_template}",
                details=details,
            )
            return await self._persist_readiness(decision, schedule, target, trigger_source, persist)
        if bool(config.get("require_safe_mode", True)) and not schedule.safe_mode:
            decision = _ReadinessDecision(
                status=READINESS_BLOCKED_SAFETY,
                reason="program policy requires safe_mode for recurring runs",
                details=details,
            )
            return await self._persist_readiness(decision, schedule, target, trigger_source, persist)
        if target.safe_mode_required and not schedule.safe_mode:
            decision = _ReadinessDecision(
                status=READINESS_BLOCKED_SAFETY,
                reason="target requires safe_mode",
                details=details,
            )
            return await self._persist_readiness(decision, schedule, target, trigger_source, persist)

        required_secret_keys: list[str] = []
        for step in template.steps:
            if str(step.tool).lower().startswith("k1_"):
                continue
            entry = get_catalog_entry(step.tool)
            if entry is None:
                continue
            required_secret_keys.extend(entry.api_keys_required)
        present_keys, missing_keys = self._resolve_required_secrets(required_secret_keys)
        details["credentials"] = {
            "required_keys": sorted({str(item).strip() for item in required_secret_keys if str(item).strip()}),
            "present_keys": present_keys,
            "missing_keys": missing_keys,
        }

        # Check available scanning modes based on stored credentials (Option C: return + filter)
        try:
            creds_mgr = CredentialsManager(self.db)
            scanning_modes_info = await creds_mgr.get_scanning_modes(program.id)
            details["scanning_modes"] = {
                "available_modes": scanning_modes_info["available_modes"],
                "warnings": scanning_modes_info["warnings"],
                "recommendation": scanning_modes_info["recommendation"],
            }
        except Exception as e:
            # If credential checking fails, log but don't block the scan
            logger.warning(f"Failed to check scanning modes for {program.id}: {str(e)}")
            details["scanning_modes"] = {
                "available_modes": ["unauthenticated"],
                "warnings": [{"type": "CREDENTIAL_CHECK_FAILED", "message": str(e)}],
                "recommendation": "Only unauthenticated scanning available (credential check failed)",
            }
            scanning_modes_info = {
                "available_modes": ["unauthenticated"],
                "warnings": [{"type": "CREDENTIAL_CHECK_FAILED", "message": str(e)}],
            }

        credential_hints = self._credential_setup_hints(
            missing_keys=missing_keys,
            scanning_warnings=list(scanning_modes_info.get("warnings") or []),
        )
        details["credentials"]["setup_hints"] = credential_hints
        details["credentials"]["missing_required_credentials"] = bool(missing_keys)

        schedule_config = _coalesce_json(getattr(schedule, "config_json", {}))
        block_on_missing_credentials = bool(
            schedule_config.get("block_on_missing_credentials", False)
            or config.get("block_on_missing_credentials", False)
        )
        details["credentials"]["block_on_missing_credentials"] = block_on_missing_credentials
        if missing_keys and block_on_missing_credentials:
            decision = _ReadinessDecision(
                status=READINESS_BLOCKED_CONFIG,
                reason=f"required credentials missing (strict mode): {', '.join(missing_keys)}",
                details=details,
            )
            return await self._persist_readiness(decision, schedule, target, trigger_source, persist)

        policy = await self._build_program_scope_policy(program.id)
        scope_decision = evaluate_target_scope(target.target, policy, safe_mode=schedule.safe_mode)
        details["scope_reason"] = scope_decision.reason
        if not scope_decision.allowed:
            decision = _ReadinessDecision(
                status=READINESS_BLOCKED_SCOPE,
                reason=f"canonical scope policy rejected target ({scope_decision.reason})",
                details=details,
            )
            return await self._persist_readiness(decision, schedule, target, trigger_source, persist)

        tool_names = sorted(
            {
                step.tool
                for step in template.steps
                if not str(step.tool).lower().startswith("k1_")
            }
        )
        if tool_names:
            dashboard = await _run_in_thread(
                build_dashboard,
                tool_names=tool_names,
                enabled_only=False,
                run_smoke_tests=False,
                telemetry_window=10,
                install_timeout=4,
                use_cached_install_report=True,
            )
            degraded_tools = [
                tool["tool_name"]
                for tool in dashboard.get("tools", [])
                if tool.get("overall_health") in {"unavailable", "degraded"}
            ]
            details["tool_health"] = {
                "checked_tools": tool_names,
                "degraded_tools": degraded_tools,
            }
            if degraded_tools:
                decision = _ReadinessDecision(
                    status=READINESS_BLOCKED_HEALTH,
                    reason=f"required tools unhealthy: {', '.join(degraded_tools)}",
                    details=details,
                )
                return await self._persist_readiness(decision, schedule, target, trigger_source, persist)

        decision = _ReadinessDecision(
            status=READINESS_READY,
            reason=(
                "target/workflow ready with credential fallbacks"
                if missing_keys
                else "target/workflow ready for execution"
            ),
            details=details,
        )
        return await self._persist_readiness(decision, schedule, target, trigger_source, persist)

    async def _persist_readiness(
        self,
        decision: _ReadinessDecision,
        schedule: HuntScheduleJob,
        target: ScopeTarget | None,
        trigger_source: str,
        persist: bool,
    ) -> ReadinessCheckResponse:
        record_id: UUID | None = None
        if persist and target is not None:
            record = HuntReadinessRecord(
                schedule_job_id=schedule.id,
                program_id=schedule.program_id,
                scope_target_id=target.id,
                workflow_template=schedule.workflow_template,
                target_identifier=target.target,
                trigger_source=trigger_source,
                decision_status=decision.status,
                reason=decision.reason,
                details_json=decision.details,
            )
            self.db.add(record)
            await self.db.flush()
            record_id = record.id
            await record_transition_event(
                self.db,
                event_type="bugbounty.readiness.evaluated",
                actor=trigger_source,
                message=decision.reason,
                campaign_id=None,
                payload={
                    "schedule_id": str(schedule.id),
                    "scope_target_id": str(target.id),
                    "decision_status": decision.status,
                },
                dedupe_key=f"{schedule.id}:{decision.status}:{target.id}",
            )
        return ReadinessCheckResponse(
            decision_status=decision.status,
            reason=decision.reason,
            details=decision.details,
            record_id=record_id,
        )

    def _next_schedule_at(self, schedule: HuntScheduleJob, *, now: datetime) -> datetime:
        if schedule.schedule_type == "interval":
            minutes = schedule.interval_minutes or 60
            return now + timedelta(minutes=max(1, minutes))
        cron_expr = (schedule.cron_expr or "").strip()
        # Minimal cron support: */N * * * *
        if cron_expr.startswith("*/"):
            try:
                minutes = int(cron_expr.split(" ", 1)[0].replace("*/", ""))
                return now + timedelta(minutes=max(1, minutes))
            except Exception:
                pass
        return now + timedelta(minutes=60)

    @staticmethod
    def _worker_role_for_schedule(schedule: HuntScheduleJob) -> str:
        template = str(schedule.workflow_template or "").strip().lower()
        if "recon" in template:
            return "recon_worker"
        if "crawl" in template or "attack_surface" in template:
            return "crawler_worker"
        if "vuln" in template:
            return "vuln_scan_worker"
        if "secret" in template:
            return "secret_scan_worker"
        if "priority" in template or "ranking" in template:
            return "reporting_worker"
        return "enrichment_worker"

    async def trigger_schedule(
        self,
        schedule_id: UUID,
        *,
        actor: str,
        force: bool = False,
        trigger_source: str = "scheduler",
    ) -> ScheduleTriggerResponse:
        schedule = await self.db.scalar(select(HuntScheduleJob).where(HuntScheduleJob.id == schedule_id))
        if schedule is None:
            raise ValueError("Schedule not found")
        target = await self.db.scalar(select(ScopeTarget).where(ScopeTarget.id == schedule.scope_target_id))
        if target is None:
            raise ValueError("Schedule scope target not found")

        readiness = await self.evaluate_readiness(
            schedule,
            trigger_source=trigger_source,
            persist=True,
        )
        if not force and readiness.decision_status != READINESS_READY:
            schedule.last_run_status = readiness.decision_status
            schedule.last_failure_reason = readiness.reason
            schedule.next_scheduled_run_at = self._next_schedule_at(schedule, now=_utcnow())
            target.last_checked_at = _utcnow()
            await self.db.flush()
            return ScheduleTriggerResponse(
                schedule_id=schedule.id,
                decision_status=readiness.decision_status,
                reason=readiness.reason,
                readiness_record_id=readiness.record_id,
                next_scheduled_run_at=schedule.next_scheduled_run_at,
                details=readiness.details,
            )

        now = _utcnow()
        schedule.last_run_started_at = now
        target.last_checked_at = now
        await self.db.flush()

        policy = await self._build_program_scope_policy(schedule.program_id)
        executor = WorkflowExecutor(
            db=self.db,
            trigger_source=f"SCHEDULER:{schedule.id}",
            actor=actor,
        )
        run_key = f"bb-{schedule.id.hex[:8]}-{int(now.timestamp())}"
        campaign_name = (
            f"bb:{schedule.workflow_template}:{target.target}:{run_key}"
        )[:255]
        result = await executor.execute_template(
            workflow_template=schedule.workflow_template,
            target=target.target,
            run_id=run_key,
            safe_mode=schedule.safe_mode,
            dry_run=schedule.dry_run,
            concurrency_limit=max(1, schedule.max_concurrency),
            scope_policy_override=policy,
            program_id=schedule.program_id,
            scope_target_id=schedule.scope_target_id,
            campaign_name=campaign_name,
            initiated_by=actor,
        )
        finished_at = _utcnow()
        schedule.last_run_finished_at = finished_at
        schedule.last_run_status = result.status
        schedule.next_scheduled_run_at = self._next_schedule_at(schedule, now=finished_at)

        workflow_run_id: UUID | None = None
        if result.workflow_run_id:
            workflow_run_id = UUID(result.workflow_run_id)
        campaign_id: UUID | None = None
        if result.campaign_id:
            campaign_id = UUID(result.campaign_id)

        if result.status == "COMPLETED":
            schedule.consecutive_failures = 0
            schedule.last_failure_reason = None
            target.last_success_at = finished_at
        else:
            schedule.consecutive_failures = (schedule.consecutive_failures or 0) + 1
            schedule.last_failure_reason = result.status
            target.last_failure_at = finished_at
            if schedule.consecutive_failures >= schedule.failure_pause_threshold:
                schedule.status = SCHEDULE_PAUSED
                schedule.paused_at = finished_at
                schedule.paused_reason = (
                    f"Paused after {schedule.consecutive_failures} consecutive failures"
                )
                schedule.next_scheduled_run_at = finished_at + timedelta(
                    minutes=schedule.failure_backoff_minutes
                )

        readiness_record = HuntReadinessRecord(
            schedule_job_id=schedule.id,
            program_id=schedule.program_id,
            scope_target_id=schedule.scope_target_id,
            campaign_run_id=campaign_id,
            workflow_run_id=workflow_run_id,
            workflow_template=schedule.workflow_template,
            target_identifier=target.target,
            trigger_source=trigger_source,
            decision_status=READINESS_READY,
            reason="workflow launched",
            details_json={
                "run_id": result.run_id,
                "status": result.status,
                "manifest_path": result.manifest_path,
                "summary_path": result.summary_path,
            },
        )
        self.db.add(readiness_record)
        await self.db.flush()

        if workflow_run_id is not None:
            await self._persist_run_deltas(schedule, workflow_run_id)
            await self._persist_candidate_queue(schedule, workflow_run_id)
            await Phase9AlertCaseService(self.db).sync_alerts(
                actor="scheduler.phase9.alerts",
                program_id=schedule.program_id,
                cooldown_minutes=120,
            )

        await record_transition_event(
            self.db,
            event_type="bugbounty.schedule.triggered",
            actor=actor,
            message=f"Executed scheduled workflow {schedule.workflow_template}",
            campaign_id=campaign_id,
            payload={
                "schedule_id": str(schedule.id),
                "run_id": result.run_id,
                "workflow_run_id": result.workflow_run_id,
                "status": result.status,
            },
        )
        return ScheduleTriggerResponse(
            schedule_id=schedule.id,
            decision_status=READINESS_READY,
            reason="workflow launched",
            readiness_record_id=readiness_record.id,
            campaign_id=campaign_id,
            workflow_run_id=workflow_run_id,
            run_id=result.run_id,
            next_scheduled_run_at=schedule.next_scheduled_run_at,
            details={
                "status": result.status,
                "manifest_path": result.manifest_path,
                "summary_path": result.summary_path,
            },
        )

    async def get_scheduler_status(
        self,
        *,
        program_id: UUID | None = None,
    ) -> SchedulerStatusResponse:
        stmt = select(HuntScheduleJob)
        if program_id is not None:
            stmt = stmt.where(HuntScheduleJob.program_id == program_id)
        schedule_result = await self.db.execute(stmt)
        schedules = list(schedule_result.scalars().all())
        now = _utcnow()
        total = len(schedules)
        active = sum(1 for item in schedules if item.status == SCHEDULE_ACTIVE)
        paused = sum(1 for item in schedules if item.status == SCHEDULE_PAUSED)
        disabled = sum(1 for item in schedules if item.status == SCHEDULE_DISABLED)
        errored = sum(1 for item in schedules if item.status == SCHEDULE_ERROR)
        due = sum(
            1
            for item in schedules
            if item.status == SCHEDULE_ACTIVE
            and (
                item.next_scheduled_run_at is None
                or item.next_scheduled_run_at <= now
            )
        )

        readiness_stmt = select(HuntReadinessRecord).where(
            HuntReadinessRecord.decided_at >= now - timedelta(hours=24)
        )
        if program_id is not None:
            readiness_stmt = readiness_stmt.where(HuntReadinessRecord.program_id == program_id)
        readiness_result = await self.db.execute(readiness_stmt)
        readiness_rows = list(readiness_result.scalars().all())
        blocked_24h = sum(1 for row in readiness_rows if row.decision_status != READINESS_READY)
        ready_24h = sum(1 for row in readiness_rows if row.decision_status == READINESS_READY)

        return SchedulerStatusResponse(
            total_schedules=total,
            active_schedules=active,
            paused_schedules=paused,
            disabled_schedules=disabled,
            error_schedules=errored,
            due_schedules=due,
            blocked_readiness_last_24h=blocked_24h,
            ready_readiness_last_24h=ready_24h,
        )

    async def run_due_schedules(
        self,
        *,
        actor: str,
        limit: int = 25,
        program_id: UUID | None = None,
    ) -> list[ScheduleTriggerResponse]:
        now = _utcnow()
        stmt: Select[tuple[HuntScheduleJob]] = (
            select(HuntScheduleJob)
            .where(
                HuntScheduleJob.status == SCHEDULE_ACTIVE,
                or_(
                    HuntScheduleJob.next_scheduled_run_at.is_(None),
                    HuntScheduleJob.next_scheduled_run_at <= now,
                ),
            )
            .order_by(
                HuntScheduleJob.priority_tier.asc(),
                HuntScheduleJob.next_scheduled_run_at.asc().nullsfirst(),
            )
            .limit(max(1, min(limit, 200)))
        )
        if program_id is not None:
            stmt = stmt.where(HuntScheduleJob.program_id == program_id)
        result = await self.db.execute(stmt)
        schedules = list(result.scalars().all())
        responses: list[ScheduleTriggerResponse] = []
        for schedule in schedules:
            responses.append(
                await self.trigger_schedule(
                    schedule.id,
                    actor=actor,
                    force=False,
                    trigger_source="scheduler",
                )
            )
        return responses

    async def dispatch_due_schedules(
        self,
        *,
        actor: str,
        limit: int = 25,
        program_id: UUID | None = None,
    ) -> list[ScheduleDispatchResponse]:
        now = _utcnow()
        stmt: Select[tuple[HuntScheduleJob]] = (
            select(HuntScheduleJob)
            .where(
                HuntScheduleJob.status == SCHEDULE_ACTIVE,
                or_(
                    HuntScheduleJob.next_scheduled_run_at.is_(None),
                    HuntScheduleJob.next_scheduled_run_at <= now,
                ),
            )
            .order_by(
                HuntScheduleJob.priority_tier.asc(),
                HuntScheduleJob.next_scheduled_run_at.asc().nullsfirst(),
            )
            .limit(max(1, min(limit, 200)))
        )
        if program_id is not None:
            stmt = stmt.where(HuntScheduleJob.program_id == program_id)
        schedules = list((await self.db.execute(stmt)).scalars().all())
        responses: list[ScheduleDispatchResponse] = []
        from ..worker.campaign_tasks import run_bug_bounty_schedule_task

        for schedule in schedules:
            role = self._worker_role_for_schedule(schedule)
            dispatch_at = _utcnow()
            # Reserve next run timestamp before enqueue to prevent duplicate
            # dispatch when endpoint is called repeatedly.
            schedule.last_run_started_at = dispatch_at
            schedule.last_run_status = "DISPATCHED"
            schedule.next_scheduled_run_at = self._next_schedule_at(schedule, now=dispatch_at)
            schedule.updated_by = actor
            await self.db.flush()
            try:
                task = run_bug_bounty_schedule_task.delay(
                    schedule_id=str(schedule.id),
                    actor=actor,
                    worker_role=role,
                    force=False,
                )
                responses.append(
                    ScheduleDispatchResponse(
                        schedule_id=schedule.id,
                        worker_task_id=str(task.id),
                        worker_role=role,
                        decision_status="DISPATCHED",
                        reason="queued for worker execution",
                    )
                )
            except Exception as exc:
                schedule.last_run_status = "DISPATCH_FAILED"
                schedule.last_failure_reason = str(exc)[:2000]
                schedule.next_scheduled_run_at = dispatch_at + timedelta(
                    minutes=max(1, int(schedule.failure_backoff_minutes or 1))
                )
                await self.db.flush()
                responses.append(
                    ScheduleDispatchResponse(
                        schedule_id=schedule.id,
                        worker_task_id=None,
                        worker_role=role,
                        decision_status="FAILED",
                        reason=f"worker dispatch failed: {exc}",
                    )
                )
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="bugbounty.schedule.dispatched",
            actor=actor,
            message="Due schedules dispatched to worker queue",
            payload={
                "program_id": str(program_id) if program_id else None,
                "schedule_count": len(responses),
                "failed_dispatches": sum(
                    1 for item in responses if item.decision_status != "DISPATCHED"
                ),
            },
        )
        return responses

    async def list_readiness_records(
        self,
        *,
        program_id: UUID | None = None,
        decision_status: str | None = None,
        limit: int = 200,
    ) -> list[HuntReadinessRecord]:
        stmt: Select[tuple[HuntReadinessRecord]] = select(HuntReadinessRecord).order_by(
            HuntReadinessRecord.decided_at.desc()
        )
        if program_id is not None:
            stmt = stmt.where(HuntReadinessRecord.program_id == program_id)
        if decision_status:
            stmt = stmt.where(HuntReadinessRecord.decision_status == decision_status)
        stmt = stmt.limit(max(1, min(limit, 1000)))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_deltas(
        self,
        *,
        program_id: UUID | None = None,
        scope_target_id: UUID | None = None,
        limit: int = 500,
    ) -> list[WorkflowDeltaRecord]:
        stmt: Select[tuple[WorkflowDeltaRecord]] = select(WorkflowDeltaRecord).order_by(
            WorkflowDeltaRecord.created_at.desc()
        )
        if program_id is not None:
            stmt = stmt.where(WorkflowDeltaRecord.program_id == program_id)
        if scope_target_id is not None:
            stmt = stmt.where(WorkflowDeltaRecord.scope_target_id == scope_target_id)
        stmt = stmt.limit(max(1, min(limit, 2000)))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_candidate_queue(
        self,
        *,
        program_id: UUID | None = None,
        status: str | None = None,
        limit: int = 500,
    ) -> list[AnalystQueueItem]:
        stmt: Select[tuple[AnalystQueueItem]] = select(AnalystQueueItem).order_by(
            AnalystQueueItem.reportability_score.desc().nullslast(),
            AnalystQueueItem.created_at.desc(),
        )
        if program_id is not None:
            stmt = stmt.where(AnalystQueueItem.program_id == program_id)
        if status:
            stmt = stmt.where(AnalystQueueItem.status == status)
        stmt = stmt.limit(max(1, min(limit, 2000)))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_candidate_queue_item(
        self,
        queue_item_id: UUID,
        payload: CandidateQueueUpdateRequest,
    ) -> AnalystQueueItem:
        queue_item = await self.db.scalar(
            select(AnalystQueueItem).where(AnalystQueueItem.id == queue_item_id)
        )
        if queue_item is None:
            raise ValueError("Analyst queue item not found")

        allowed_statuses = {
            "new",
            "acknowledged",
            "triaged",
            "needs_manual_validation",
            "ready_for_report",
            "dismissed",
            "duplicate_suspected",
            "submitted_externally",
        }
        next_status = payload.status.strip().lower()
        if next_status not in allowed_statuses:
            raise ValueError(f"Invalid analyst queue status: {payload.status}")

        queue_item.status = next_status
        queue_item.assigned_to = payload.assigned_to
        queue_item.last_transition_at = _utcnow()
        details = _coalesce_json(queue_item.details_json)
        if payload.analyst_notes:
            notes = details.get("analyst_notes")
            notes_list = list(notes) if isinstance(notes, list) else []
            notes_list.append(
                {
                    "at": queue_item.last_transition_at.isoformat(),
                    "actor": payload.actor,
                    "note": payload.analyst_notes,
                }
            )
            details["analyst_notes"] = notes_list
        queue_item.details_json = details
        await self.db.flush()
        await Phase9AlertCaseService(self.db).sync_alerts(
            actor=payload.actor,
            program_id=queue_item.program_id,
            cooldown_minutes=120,
        )
        await record_transition_event(
            self.db,
            event_type="bugbounty.candidate.updated",
            actor=payload.actor,
            message=f"Updated analyst queue item {queue_item.id} to {next_status}",
            campaign_id=None,
            payload={
                "queue_item_id": str(queue_item.id),
                "status": next_status,
                "assigned_to": payload.assigned_to,
            },
        )
        return queue_item

    def _run_key_from_workflow(self, run: WorkflowRun) -> str | None:
        for path_value in (
            run.summary_artifact_path,
            run.plan_artifact_path,
            run.artifact_manifest_path,
        ):
            if not path_value:
                continue
            try:
                path = Path(path_value)
                return path.parent.name
            except Exception:
                continue
        return None

    def _load_jsonl_set(self, run_key: str, filename: str, key_fn) -> set[str]:
        path = workflow_output_root() / "normalized" / run_key / filename
        if not path.exists():
            return set()
        output: set[str] = set()
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = key_fn(payload)
            if key:
                output.add(key)
        return output

    async def _persist_run_deltas(self, schedule: HuntScheduleJob, workflow_run_id: UUID) -> None:
        current_run = await self.db.scalar(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))
        if current_run is None:
            return
        previous_run = await self.db.scalar(
            select(WorkflowRun)
            .where(
                WorkflowRun.scope_target_id == schedule.scope_target_id,
                WorkflowRun.template_name == current_run.template_name,
                WorkflowRun.id != current_run.id,
            )
            .order_by(WorkflowRun.created_at.desc())
            .limit(1)
        )
        current_key = self._run_key_from_workflow(current_run)
        previous_key = self._run_key_from_workflow(previous_run) if previous_run is not None else None
        if not current_key:
            return

        comparisons: list[tuple[str, str, Any]] = [
            ("subdomain", "discovered_assets.jsonl", lambda r: str(r.get("host") or "").strip()),
            (
                "live_service",
                "live_services.jsonl",
                lambda r: f"{r.get('host')}:{r.get('port')}" if r.get("host") and r.get("port") else "",
            ),
            ("url", "url_records.jsonl", lambda r: str(r.get("url") or "").strip()),
            ("endpoint", "endpoint_records.jsonl", lambda r: str(r.get("endpoint") or "").strip()),
            (
                "parameter",
                "parameter_records.jsonl",
                lambda r: (
                    f"{r.get('endpoint')}::{r.get('parameter_name')}"
                    if r.get("parameter_name")
                    else ""
                ),
            ),
            ("secret", "secret_findings.jsonl", lambda r: str(r.get("location") or "").strip()),
            (
                "vuln_candidate",
                "vuln_candidates.jsonl",
                lambda r: f"{r.get('target')}::{r.get('title')}" if r.get("title") else "",
            ),
        ]
        now = _utcnow()
        for delta_type, file_name, key_fn in comparisons:
            current_values = self._load_jsonl_set(current_key, file_name, key_fn)
            previous_values = (
                self._load_jsonl_set(previous_key, file_name, key_fn) if previous_key else set()
            )
            new_values = current_values - previous_values
            removed_values = previous_values - current_values

            for value in sorted(new_values):
                self.db.add(
                    WorkflowDeltaRecord(
                        schedule_job_id=schedule.id,
                        program_id=schedule.program_id,
                        scope_target_id=schedule.scope_target_id,
                        workflow_run_id=current_run.id,
                        previous_workflow_run_id=previous_run.id if previous_run else None,
                        delta_type=delta_type,
                        delta_key=value,
                        change_type="NEW",
                        details_json={"current_run_key": current_key, "previous_run_key": previous_key},
                    )
                )
            for value in sorted(removed_values):
                self.db.add(
                    WorkflowDeltaRecord(
                        schedule_job_id=schedule.id,
                        program_id=schedule.program_id,
                        scope_target_id=schedule.scope_target_id,
                        workflow_run_id=current_run.id,
                        previous_workflow_run_id=previous_run.id if previous_run else None,
                        delta_type=delta_type,
                        delta_key=value,
                        change_type="REMOVED",
                        details_json={"current_run_key": current_key, "previous_run_key": previous_key},
                    )
                )
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="bugbounty.delta.detected",
            actor="scheduler.delta",
            message=f"Delta detection completed for workflow run {current_run.id}",
            campaign_id=current_run.campaign_run_id,
            payload={
                "workflow_run_id": str(current_run.id),
                "scope_target_id": str(schedule.scope_target_id),
                "processed_at": now.isoformat(),
            },
        )

    def _severity_weight(self, severity_hint: str | None) -> float:
        value = (severity_hint or "").strip().lower()
        return {
            "critical": 1.0,
            "high": 0.85,
            "medium": 0.6,
            "low": 0.35,
            "info": 0.2,
        }.get(value, 0.4)

    async def _persist_candidate_queue(self, schedule: HuntScheduleJob, workflow_run_id: UUID) -> None:
        workflow_run = await self.db.scalar(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))
        if workflow_run is None:
            return
        scope_policy = await self._build_program_scope_policy(schedule.program_id)
        findings_result = await self.db.execute(
            select(WorkflowFinding).where(WorkflowFinding.workflow_run_id == workflow_run_id)
        )
        findings = list(findings_result.scalars().all())
        for wf in findings:
            existing = await self.db.scalar(
                select(AnalystQueueItem).where(AnalystQueueItem.workflow_finding_id == wf.id)
            )
            confidence = float(wf.confidence_score or 0.3)
            prior_count = int(
                (
                    await self.db.execute(
                        select(func.count(WorkflowFinding.id)).where(
                            WorkflowFinding.id != wf.id,
                            WorkflowFinding.asset_identifier == wf.asset_identifier,
                            WorkflowFinding.vulnerability_type == wf.vulnerability_type,
                        )
                    )
                ).scalar()
                or 0
            )
            novelty = 1.0 if prior_count == 0 else max(0.1, 1.0 / (prior_count + 1))
            duplicate_hint = "LOW" if prior_count == 0 else "ELEVATED"
            policy_fit = "IN_SCOPE"
            reportability = min(
                1.0,
                max(
                    0.0,
                    (confidence * 0.45)
                    + (self._severity_weight(wf.severity_hint) * 0.35)
                    + (novelty * 0.2),
                ),
            )
            scope_decision = evaluate_target_scope(wf.asset_identifier, scope_policy)
            qualification = qualify_evidence(
                {
                    "finding_id": str(wf.id),
                    "title": str((wf.details_json or {}).get("title") or wf.vulnerability_type),
                    "vulnerability_type": wf.vulnerability_type,
                    "severity": wf.severity_hint,
                    "target": wf.asset_identifier,
                    "endpoint": wf.endpoint,
                    "parameter": wf.parameter,
                    "confidence_score": confidence,
                    "evidence": [wf.evidence_artifact_path] if wf.evidence_artifact_path else [],
                    "validation_evidence": (wf.details_json or {}).get("validation_evidence", []),
                    "duplicate_risk": 0.0 if prior_count == 0 else min(1.0, prior_count * 0.2),
                },
                scope_metadata={
                    "target": wf.asset_identifier,
                    "allowed": bool(scope_decision.allowed),
                    "reason": scope_decision.reason,
                },
                mission_id=str(workflow_run_id),
                stage_id="candidate_queue_ingestion",
                report_id=str(wf.id),
                persist=True,
                update_duplicate_history=True,
            )
            impact_validation = validate_impact(
                finding={
                    "finding_id": str(wf.id),
                    "vulnerability_type": wf.vulnerability_type,
                    "target": wf.asset_identifier,
                    "endpoint": wf.endpoint,
                    "severity": wf.severity_hint,
                    "summary": str((wf.details_json or {}).get("summary") or ""),
                    "description": str((wf.details_json or {}).get("description") or ""),
                },
                qualification=qualification.to_dict(),
                baseline_response=(wf.details_json or {}).get("baseline_response"),
                exploit_response=(wf.details_json or {}).get("exploit_response"),
                scope_metadata={
                    "target": wf.asset_identifier,
                    "allowed": bool(scope_decision.allowed),
                    "reason": scope_decision.reason,
                },
                mission_id=str(workflow_run_id),
                stage_id="impact_validation_candidate_queue",
                report_id=str(wf.id),
                persist=True,
            )
            submission_decision = resolve_submission_candidate_decision(
                evidence_qualification=qualification.to_dict(),
                impact_validation=impact_validation.to_dict(),
            )

            reportability = min(
                1.0,
                max(
                    0.0,
                    (reportability * 0.45)
                    + (float(qualification.evidence_quality_score) * 0.35)
                    + (float(impact_validation.impact_score) * 0.20),
                ),
            )
            if qualification.duplicate_risk_score >= 0.75:
                duplicate_hint = "HIGH"
            elif qualification.duplicate_risk_score >= 0.5:
                duplicate_hint = "ELEVATED"

            if not qualification.scope_validity:
                policy_fit = "OUT_OF_SCOPE"
                status = "dismissed"
            elif bool(submission_decision.get("submission_candidate")) and reportability >= 0.8 and wf.evidence_artifact_path:
                status = "ready_for_report"
            elif reportability >= 0.55:
                status = "needs_manual_validation"
            else:
                status = "new"
            details = {
                "workflow_finding_id": str(wf.id),
                "prior_occurrence_count": prior_count,
                "scoring": {
                    "confidence": confidence,
                    "severity_weight": self._severity_weight(wf.severity_hint),
                    "novelty": novelty,
                    "reportability": reportability,
                },
                "scope_decision": {
                    "allowed": bool(scope_decision.allowed),
                    "reason": scope_decision.reason,
                    "matched_rule": scope_decision.matched_rule,
                },
                "evidence_qualification": qualification.to_dict(),
                "impact_validation": impact_validation.to_dict(),
                "submission_decision": submission_decision,
            }
            if existing is None:
                queue_item = AnalystQueueItem(
                    program_id=schedule.program_id,
                    scope_target_id=schedule.scope_target_id,
                    workflow_run_id=workflow_run_id,
                    workflow_finding_id=wf.id,
                    workflow_template=workflow_run.template_name,
                    finding_type="workflow_candidate",
                    vulnerability_type=wf.vulnerability_type,
                    affected_asset=wf.asset_identifier,
                    affected_endpoint=wf.endpoint,
                    parameter=wf.parameter,
                    evidence_summary=wf.evidence_artifact_path,
                    confidence_score=confidence,
                    severity_hint=wf.severity_hint,
                    novelty_score=novelty,
                    reportability_score=reportability,
                    duplicate_risk_hint=duplicate_hint,
                    policy_fit_status=policy_fit,
                    status=status,
                    artifact_ref=wf.evidence_artifact_path,
                    last_transition_at=_utcnow(),
                    details_json=details,
                )
                self.db.add(queue_item)
            else:
                existing.workflow_run_id = workflow_run_id
                existing.workflow_template = workflow_run.template_name
                existing.affected_asset = wf.asset_identifier
                existing.affected_endpoint = wf.endpoint
                existing.parameter = wf.parameter
                existing.evidence_summary = wf.evidence_artifact_path
                existing.confidence_score = confidence
                existing.severity_hint = wf.severity_hint
                existing.novelty_score = novelty
                existing.reportability_score = reportability
                existing.duplicate_risk_hint = duplicate_hint
                existing.policy_fit_status = policy_fit
                existing.status = status
                existing.artifact_ref = wf.evidence_artifact_path
                existing.last_transition_at = _utcnow()
                existing.details_json = details
        await self.db.flush()

    async def generate_report_draft(
        self,
        queue_item_id: UUID,
        *,
        actor: str,
        analyst_notes: str | None = None,
    ) -> GenerateReportDraftResponse:
        queue_item = await self.db.scalar(
            select(AnalystQueueItem).where(AnalystQueueItem.id == queue_item_id)
        )
        if queue_item is None:
            raise ValueError("Analyst queue item not found")
        workflow_run = await self.db.scalar(
            select(WorkflowRun).where(WorkflowRun.id == queue_item.workflow_run_id)
        )
        if workflow_run is None:
            raise ValueError("Workflow run not found for queue item")
        if workflow_run.campaign_run_id is None:
            raise ValueError("Workflow run does not have a linked campaign context")
        details = _coalesce_json(queue_item.details_json)
        qualification = details.get("evidence_qualification")
        impact_validation = details.get("impact_validation")
        if not isinstance(qualification, dict):
            qualification = qualify_evidence(
                {
                    "finding_id": str(queue_item.id),
                    "title": f"{queue_item.vulnerability_type} on {queue_item.affected_asset}",
                    "vulnerability_type": queue_item.vulnerability_type,
                    "severity": queue_item.severity_hint,
                    "target": queue_item.affected_asset,
                    "endpoint": queue_item.affected_endpoint,
                    "parameter": queue_item.parameter,
                    "confidence_score": queue_item.confidence_score,
                    "evidence": [queue_item.evidence_summary] if queue_item.evidence_summary else [],
                    "duplicate_risk": 0.0
                    if (queue_item.duplicate_risk_hint or "").upper() == "LOW"
                    else 0.7
                    if (queue_item.duplicate_risk_hint or "").upper() in {"HIGH", "ELEVATED"}
                    else 0.4,
                },
                scope_metadata={"target": queue_item.affected_asset, "in_scope": queue_item.policy_fit_status == "IN_SCOPE"},
                mission_id=str(queue_item.workflow_run_id),
                stage_id="report_draft_generation",
                report_id=str(queue_item.id),
                persist=True,
                update_duplicate_history=False,
            ).to_dict()
            details["evidence_qualification"] = qualification
            queue_item.details_json = details
        if not isinstance(impact_validation, dict):
            impact_validation = validate_impact(
                finding={
                    "finding_id": str(queue_item.id),
                    "vulnerability_type": queue_item.vulnerability_type,
                    "target": queue_item.affected_asset,
                    "endpoint": queue_item.affected_endpoint,
                    "severity": queue_item.severity_hint,
                },
                qualification=qualification,
                scope_metadata={"target": queue_item.affected_asset, "in_scope": queue_item.policy_fit_status == "IN_SCOPE"},
                mission_id=str(queue_item.workflow_run_id),
                stage_id="impact_validation_report_draft",
                report_id=str(queue_item.id),
                persist=True,
            ).to_dict()
            details["impact_validation"] = impact_validation
            queue_item.details_json = details
        submission_decision = details.get("submission_decision")
        if not isinstance(submission_decision, dict):
            submission_decision = resolve_submission_candidate_decision(
                evidence_qualification=qualification,
                impact_validation=impact_validation,
            )
            details["submission_decision"] = submission_decision
            queue_item.details_json = details

        if not bool(submission_decision.get("submission_candidate")):
            reason = str(submission_decision.get("rejection_reason") or "submission_candidate_rejected")
            raise ValueError(f"Submission candidate rejected: {reason}")

        reports_dir = workflow_output_root() / "reports" / "bug_bounty"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"candidate_{queue_item.id}.md"
        content = "\n".join(
            [
                "# Kai Candidate Report Draft",
                "",
                f"- Queue Item: `{queue_item.id}`",
                f"- Workflow Run: `{queue_item.workflow_run_id}`",
                f"- Program: `{queue_item.program_id}`",
                f"- Target: `{queue_item.affected_asset}`",
                f"- Vulnerability Type: `{queue_item.vulnerability_type}`",
                f"- Confidence: `{queue_item.confidence_score}`",
                f"- Reportability Score: `{queue_item.reportability_score}`",
                f"- Evidence: `{queue_item.evidence_summary or 'n/a'}`",
                f"- Impact Score: `{impact_validation.get('impact_score', 'n/a')}`",
                "",
                "## Reproduction Notes",
                queue_item.details_json.get("reproduction", "Based on captured workflow evidence."),
                "",
                "## Impact Validation",
                str(impact_validation.get("impact_statement", {})),
                "",
                "## Analyst Notes",
                analyst_notes or "Pending analyst notes.",
            ]
        )
        report_path.write_text(content, encoding="utf-8")

        draft = SubmissionDraft(
            campaign_id=workflow_run.campaign_run_id,
            branch_id=None,
            finding_id=queue_item.finding_id,
            report_id=None,
            intention_id=None,
            status="NEEDS_REVIEW",
            title=f"{queue_item.vulnerability_type} on {queue_item.affected_asset}",
            content_uri=str(report_path),
            content_hash=None,
            prepared_by=actor,
            details_json={
                "queue_item_id": str(queue_item.id),
                "workflow_run_id": str(queue_item.workflow_run_id),
                "reportability_score": queue_item.reportability_score,
                "evidence_qualification": qualification,
                "impact_validation": impact_validation,
                "submission_decision": submission_decision,
            },
        )
        self.db.add(draft)
        await self.db.flush()

        artifact = Artifact(
            campaign_id=workflow_run.campaign_run_id,
            branch_id=None,
            phase_job_id=None,
            tool_execution_id=None,
            finding_id=queue_item.finding_id,
            report_id=None,
            intention_id=None,
            artifact_type=ArtifactTypeEnum.REPORT_DRAFT,
            uri=str(report_path),
            content_hash=None,
            mime_type="text/markdown",
            size_bytes=report_path.stat().st_size if report_path.exists() else None,
            description="Bug bounty candidate report draft",
            details_json={"queue_item_id": str(queue_item.id)},
        )
        self.db.add(artifact)
        await self.db.flush()

        queue_item.status = "ready_for_report"
        queue_item.last_transition_at = _utcnow()
        await self.db.flush()
        await Phase9AlertCaseService(self.db).sync_alerts(
            actor=actor,
            program_id=queue_item.program_id,
            cooldown_minutes=120,
        )

        await record_transition_event(
            self.db,
            event_type="bugbounty.report_draft.generated",
            actor=actor,
            message=f"Generated report draft for queue item {queue_item.id}",
            campaign_id=workflow_run.campaign_run_id,
            artifact_id=artifact.id,
            draft_id=draft.id,
            payload={
                "queue_item_id": str(queue_item.id),
                "draft_path": str(report_path),
            },
        )
        return GenerateReportDraftResponse(
            queue_item_id=queue_item.id,
            submission_draft_id=draft.id,
            artifact_id=artifact.id,
            draft_path=str(report_path),
            status=queue_item.status,
        )
