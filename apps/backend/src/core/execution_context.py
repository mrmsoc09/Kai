from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ExecutionContextRecord, ExecutionStatusEnum


class ExecutionContext:
    """Tracks a transaction UUID and optional idempotency state for write operations."""

    def __init__(
        self,
        db: AsyncSession,
        operation: str,
        resource_id: Optional[uuid.UUID] = None,
        idempotency_key: Optional[str] = None,
    ) -> None:
        self.db = db
        self.operation = operation
        self.resource_id = resource_id
        self.idempotency_key = self._parse_uuid_or_none(idempotency_key, "idempotency_key")
        self.transaction_id = uuid.uuid4()
        self._record: Optional[ExecutionContextRecord] = None

    @staticmethod
    def _parse_uuid_or_none(raw: Optional[str], field_name: str) -> Optional[uuid.UUID]:
        if raw is None:
            return None
        try:
            return uuid.UUID(raw)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a UUID") from exc

    async def _lookup_existing(self) -> Optional[ExecutionContextRecord]:
        stmt = select(ExecutionContextRecord).where(
            ExecutionContextRecord.operation == self.operation,
            ExecutionContextRecord.resource_id == self.resource_id,
            ExecutionContextRecord.idempotency_key == self.idempotency_key,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def begin(self) -> Optional[dict[str, Any]]:
        """Returns cached response payload if this idempotent operation already completed."""
        if self.idempotency_key is not None:
            existing = await self._lookup_existing()
            if existing and existing.status == ExecutionStatusEnum.COMPLETED:
                self.transaction_id = existing.transaction_id
                self._record = existing
                payload = existing.response_payload or {}
                if isinstance(payload, dict):
                    return payload
                return {"result": payload}

        self._record = ExecutionContextRecord(
            transaction_id=self.transaction_id,
            operation=self.operation,
            resource_id=self.resource_id,
            idempotency_key=self.idempotency_key,
            status=ExecutionStatusEnum.PENDING,
        )
        self.db.add(self._record)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            existing = await self._lookup_existing()
            if existing and existing.status == ExecutionStatusEnum.COMPLETED:
                self.transaction_id = existing.transaction_id
                self._record = existing
                payload = existing.response_payload or {}
                if isinstance(payload, dict):
                    return payload
                return {"result": payload}
            raise

        return None

    def complete(self, response_payload: dict[str, Any]) -> None:
        if self._record is None:
            return
        self._record.status = ExecutionStatusEnum.COMPLETED
        self._record.response_payload = response_payload

    def fail(self, error_message: str) -> None:
        if self._record is None:
            return
        self._record.status = ExecutionStatusEnum.FAILED
        self._record.error_message = error_message
