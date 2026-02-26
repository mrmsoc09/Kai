from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Column, Enum as SAEnum, Index, JSON, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from .base import Base
from .enums import ExecutionStatusEnum
from .mixins import TimestampMixin


class ExecutionContextRecord(Base, TimestampMixin):
    __tablename__ = "execution_contexts"
    __table_args__ = (
        UniqueConstraint(
            "operation",
            "resource_id",
            "idempotency_key",
            name="uq_execution_contexts_operation_resource_idempotency_key",
        ),
        CheckConstraint("btrim(operation) <> ''", name="execution_contexts_operation_not_empty"),
        Index("ix_execution_contexts_resource_id", "resource_id"),
        Index("ix_execution_contexts_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), nullable=False, unique=True, default=uuid.uuid4)
    operation = Column(Text, nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    idempotency_key = Column(UUID(as_uuid=True), nullable=True)
    status = Column(
        SAEnum(ExecutionStatusEnum, name="execution_status_enum", native_enum=True, create_constraint=True),
        nullable=False,
        server_default=ExecutionStatusEnum.PENDING.value,
    )
    response_payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
