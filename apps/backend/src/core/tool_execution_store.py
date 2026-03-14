from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from threading import Lock
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import select

from ..models.campaign import CampaignRun, Program, ScopeTarget, ToolExecution
from ..models.enums import CampaignStatusEnum, ToolExecutionStatusEnum
from .hil_db import get_async_session_maker


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ExecutionRecord:
    execution_id: str
    tool_id: str
    params: Dict[str, Any]
    status: str
    created_at: str
    updated_at: str
    run_id: Optional[str] = None
    user_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    rejected_reason: Optional[str] = None


class ToolExecutionStore:
    """Durable adapter for tools API pending approvals backed by canonical ToolExecution rows."""

    def __init__(self) -> None:
        self._context_lock = Lock()
        self._cached_campaign_id = None
        self._cached_scope_target_id = None
        self._cached_program_id = None
        self._fallback_lock = Lock()
        self._fallback_records: Dict[str, ExecutionRecord] = {}

    @staticmethod
    def _is_test_mode() -> bool:
        return os.getenv("K1_TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _allow_fallback(cls) -> bool:
        return cls._is_test_mode()

    @staticmethod
    def _test_db_timeout_seconds() -> float:
        try:
            return float(os.getenv("K1_TEST_TOOL_EXEC_DB_TIMEOUT_SECONDS", "5"))
        except Exception:
            return 5.0

    async def _ensure_campaign_context(self, db) -> tuple:
        with self._context_lock:
            cached_program_id = self._cached_program_id
            cached_scope_target_id = self._cached_scope_target_id
            cached_campaign_id = self._cached_campaign_id
        if cached_program_id and cached_campaign_id:
            return cached_program_id, cached_scope_target_id, cached_campaign_id

        program_key = "kai-tools-api"
        result = await db.execute(select(Program).where(Program.program_key == program_key))
        program = result.scalar_one_or_none()
        if program is None:
            program = Program(
                program_key=program_key,
                name="Kai Tools API",
                platform="LOCAL",
                status="ACTIVE",
                created_by="tools.api",
                config_json={"owner": "tools_router"},
            )
            db.add(program)
            await db.flush()

        result = await db.execute(
            select(ScopeTarget).where(
                ScopeTarget.program_id == program.id,
                ScopeTarget.target == "tools-api.local",
                ScopeTarget.target_type == "domain",
            )
        )
        scope_target = result.scalar_one_or_none()
        if scope_target is None:
            scope_target = ScopeTarget(
                program_id=program.id,
                target="tools-api.local",
                target_type="domain",
                is_in_scope=True,
                details_json={"source": "tools_api"},
            )
            db.add(scope_target)
            await db.flush()

        campaign_name = "tools-api-default"
        result = await db.execute(
            select(CampaignRun).where(
                CampaignRun.program_id == program.id,
                CampaignRun.campaign_name == campaign_name,
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            campaign = CampaignRun(
                program_id=program.id,
                primary_scope_target_id=scope_target.id,
                campaign_name=campaign_name,
                initiated_by="tools.api",
                declared_goal="Persist standalone tools API execution approvals",
                declared_reason="Durable tools API auditability",
                policy_basis="TOOLS_API",
                approval_required=False,
                status=CampaignStatusEnum.RUNNING,
                run_config_json={"source": "tools_router"},
                started_at=_utcnow(),
            )
            db.add(campaign)
            await db.flush()

        with self._context_lock:
            self._cached_program_id = program.id
            self._cached_scope_target_id = scope_target.id
            self._cached_campaign_id = campaign.id
        return program.id, scope_target.id, campaign.id

    @staticmethod
    def _parse_result(summary: str | None) -> Dict[str, Any] | None:
        if not isinstance(summary, str):
            return None
        text = summary.strip()
        if not text.startswith("{"):
            return None
        try:
            payload = json.loads(text)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _row_to_record(row: ToolExecution) -> ExecutionRecord:
        status_map = {
            ToolExecutionStatusEnum.WAITING_APPROVAL: "pending_approval",
            ToolExecutionStatusEnum.COMPLETED: "completed",
            ToolExecutionStatusEnum.CANCELED: "rejected",
            ToolExecutionStatusEnum.FAILED: "failed",
            ToolExecutionStatusEnum.RUNNING: "running",
            ToolExecutionStatusEnum.QUEUED: "queued",
            ToolExecutionStatusEnum.CREATED: "created",
        }
        return ExecutionRecord(
            execution_id=row.worker_task_id or str(row.id),
            tool_id=row.tool_name,
            params=dict(row.input_payload_json or {}),
            status=status_map.get(row.status, row.status.value.lower()),
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
            run_id=str((row.input_payload_json or {}).get("run_id") or ""),
            user_id=str((row.input_payload_json or {}).get("user_id") or ""),
            result=ToolExecutionStore._parse_result(row.stdout_summary),
            rejected_reason=row.error_message,
        )

    async def create_pending(
        self,
        execution_id: str,
        tool_id: str,
        params: Dict[str, Any],
        run_id: str | None,
        user_id: str | None,
    ) -> ExecutionRecord:
        if self._allow_fallback():
            try:
                return await asyncio.wait_for(
                    self._create_pending_db(execution_id, tool_id, params, run_id, user_id),
                    timeout=self._test_db_timeout_seconds(),
                )
            except Exception:
                return self._create_pending_fallback(execution_id, tool_id, params, run_id, user_id)
        return await self._create_pending_db(execution_id, tool_id, params, run_id, user_id)

    async def _create_pending_db(
        self,
        execution_id: str,
        tool_id: str,
        params: Dict[str, Any],
        run_id: str | None,
        user_id: str | None,
    ) -> ExecutionRecord:
        try:
            session_maker = get_async_session_maker()
        except Exception:
            if self._allow_fallback():
                return self._create_pending_fallback(execution_id, tool_id, params, run_id, user_id)
            raise
        async with session_maker() as db:
            try:
                _, _, campaign_id = await self._ensure_campaign_context(db)
                row = ToolExecution(
                    campaign_id=campaign_id,
                    tool_name=tool_id,
                    execution_mode="api",
                    input_target=str(
                        params.get("target")
                        or params.get("url")
                        or params.get("domain")
                        or params.get("host")
                        or ""
                    ),
                    input_payload_json={**dict(params), "run_id": run_id, "user_id": user_id},
                    status=ToolExecutionStatusEnum.WAITING_APPROVAL,
                    worker_task_id=execution_id,
                    queued_at=_utcnow(),
                    started_at=None,
                )
                db.add(row)
                await db.flush()
                record = self._row_to_record(row)
                await db.commit()
                return record
            except Exception:
                await db.rollback()
                if self._allow_fallback():
                    return self._create_pending_fallback(
                        execution_id,
                        tool_id,
                        params,
                        run_id,
                        user_id,
                    )
                raise

    async def get(self, execution_id: str) -> Optional[ExecutionRecord]:
        if self._allow_fallback():
            try:
                return await asyncio.wait_for(
                    self._get_db(execution_id),
                    timeout=self._test_db_timeout_seconds(),
                )
            except Exception:
                return self._get_fallback(execution_id)
        return await self._get_db(execution_id)

    async def _get_db(self, execution_id: str) -> Optional[ExecutionRecord]:
        try:
            session_maker = get_async_session_maker()
        except Exception:
            if self._allow_fallback():
                return self._get_fallback(execution_id)
            raise
        async with session_maker() as db:
            try:
                stmt = (
                    select(ToolExecution)
                    .where(ToolExecution.worker_task_id == execution_id)
                    .order_by(ToolExecution.created_at.desc())
                )
                result = await db.execute(stmt)
                row = result.scalar_one_or_none()
                if row is None:
                    return None
                return self._row_to_record(row)
            except Exception:
                if self._allow_fallback():
                    return self._get_fallback(execution_id)
                raise

    async def _lookup_row(self, db, execution_id: str) -> Optional[ToolExecution]:
        result = await db.execute(
            select(ToolExecution)
            .where(ToolExecution.worker_task_id == execution_id)
            .order_by(ToolExecution.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def mark_completed(
        self,
        execution_id: str,
        result: Dict[str, Any],
    ) -> Optional[ExecutionRecord]:
        if self._allow_fallback():
            try:
                return await asyncio.wait_for(
                    self._mark_completed_db(execution_id, result),
                    timeout=self._test_db_timeout_seconds(),
                )
            except Exception:
                return self._mark_completed_fallback(execution_id, result)
        return await self._mark_completed_db(execution_id, result)

    async def _mark_completed_db(
        self,
        execution_id: str,
        result: Dict[str, Any],
    ) -> Optional[ExecutionRecord]:
        try:
            session_maker = get_async_session_maker()
        except Exception:
            if self._allow_fallback():
                return self._mark_completed_fallback(execution_id, result)
            raise
        async with session_maker() as db:
            try:
                row = await self._lookup_row(db, execution_id)
                if row is None:
                    return None
                row.status = ToolExecutionStatusEnum.COMPLETED
                row.ended_at = _utcnow()
                row.stdout_summary = json.dumps(result, default=str)[:4000]
                row.error_message = None
                if row.started_at is not None:
                    row.duration_ms = (row.ended_at - row.started_at).total_seconds() * 1000
                await db.flush()
                record = self._row_to_record(row)
                await db.commit()
                return record
            except Exception:
                await db.rollback()
                if self._allow_fallback():
                    return self._mark_completed_fallback(execution_id, result)
                raise

    async def mark_rejected(
        self,
        execution_id: str,
        reason: str | None,
    ) -> Optional[ExecutionRecord]:
        if self._allow_fallback():
            try:
                return await asyncio.wait_for(
                    self._mark_rejected_db(execution_id, reason),
                    timeout=self._test_db_timeout_seconds(),
                )
            except Exception:
                return self._mark_rejected_fallback(execution_id, reason)
        return await self._mark_rejected_db(execution_id, reason)

    async def _mark_rejected_db(
        self,
        execution_id: str,
        reason: str | None,
    ) -> Optional[ExecutionRecord]:
        try:
            session_maker = get_async_session_maker()
        except Exception:
            if self._allow_fallback():
                return self._mark_rejected_fallback(execution_id, reason)
            raise
        async with session_maker() as db:
            try:
                row = await self._lookup_row(db, execution_id)
                if row is None:
                    return None
                row.status = ToolExecutionStatusEnum.CANCELED
                row.canceled_at = _utcnow()
                row.error_message = reason
                await db.flush()
                record = self._row_to_record(row)
                await db.commit()
                return record
            except Exception:
                await db.rollback()
                if self._allow_fallback():
                    return self._mark_rejected_fallback(execution_id, reason)
                raise

    def _create_pending_fallback(
        self,
        execution_id: str,
        tool_id: str,
        params: Dict[str, Any],
        run_id: str | None,
        user_id: str | None,
    ) -> ExecutionRecord:
        now = _utcnow().isoformat()
        rec = ExecutionRecord(
            execution_id=execution_id,
            tool_id=tool_id,
            params=dict(params),
            status="pending_approval",
            created_at=now,
            updated_at=now,
            run_id=run_id,
            user_id=user_id,
        )
        with self._fallback_lock:
            self._fallback_records[execution_id] = rec
        return rec

    def _get_fallback(self, execution_id: str) -> Optional[ExecutionRecord]:
        with self._fallback_lock:
            rec = self._fallback_records.get(execution_id)
            if rec is None:
                return None
            return ExecutionRecord(**rec.__dict__)

    def _mark_completed_fallback(
        self,
        execution_id: str,
        result: Dict[str, Any],
    ) -> Optional[ExecutionRecord]:
        with self._fallback_lock:
            rec = self._fallback_records.get(execution_id)
            if rec is None:
                return None
            rec.status = "completed"
            rec.updated_at = _utcnow().isoformat()
            rec.result = dict(result)
            return ExecutionRecord(**rec.__dict__)

    def _mark_rejected_fallback(
        self,
        execution_id: str,
        reason: str | None,
    ) -> Optional[ExecutionRecord]:
        with self._fallback_lock:
            rec = self._fallback_records.get(execution_id)
            if rec is None:
                return None
            rec.status = "rejected"
            rec.updated_at = _utcnow().isoformat()
            rec.rejected_reason = reason
            return ExecutionRecord(**rec.__dict__)


_STORE = ToolExecutionStore()


def get_tool_execution_store() -> ToolExecutionStore:
    return _STORE
