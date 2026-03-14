from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    Enum as SAEnum,
    ForeignKey,
    Index,
    JSON,
    LargeBinary,
    Text,
    Float,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base
from .enums import FindingStatusEnum, HILApprovalStatusEnum, SeverityEnum
from .mixins import SoftDeleteMixin, TimestampMixin, UTCAwareDatetime


class Finding(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint("btrim(program) <> ''", name="finding_program_not_empty"),
        CheckConstraint("btrim(asset) <> ''", name="finding_asset_not_empty"),
        CheckConstraint("btrim(title) <> ''", name="finding_title_not_empty"),
        CheckConstraint("btrim(description) <> ''", name="finding_description_not_empty"),
        Index("ix_findings_is_deleted", "is_deleted"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program = Column(Text, nullable=False)
    asset = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(
        SAEnum(SeverityEnum, name="severity_enum", native_enum=True, create_constraint=True),
        nullable=False,
    )
    status = Column(
        SAEnum(FindingStatusEnum, name="finding_status_enum", native_enum=True, create_constraint=True),
        nullable=False,
        server_default=FindingStatusEnum.NEW.value,
    )
    scope_json = Column(JSON, nullable=False, server_default="{}")
    reproducibility_score = Column(Float, nullable=True)

    evidences = relationship("Evidence", back_populates="finding")
    hil_approval = relationship("HILApproval", uselist=False, back_populates="finding")


class Evidence(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint("btrim(kind) <> ''", name="evidence_kind_not_empty"),
        CheckConstraint("btrim(uri) <> ''", name="evidence_uri_not_empty"),
        Index("ix_evidence_finding_id", "finding_id"),
        Index("ix_evidence_is_deleted", "is_deleted"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id = Column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kind = Column(Text, nullable=False)
    uri = Column(Text, nullable=False)
    sha256 = Column(LargeBinary, nullable=False)
    meta = Column(JSON, nullable=False, server_default="{}")

    finding = relationship("Finding", back_populates="evidences")


class HILApproval(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "hil_approvals"
    __table_args__ = (
        UniqueConstraint("finding_id", name="uq_hil_approvals_finding_id"),
        CheckConstraint("btrim(approved_by) <> ''", name="hil_approvals_approved_by_not_empty"),
        Index("ix_hil_approvals_is_deleted", "is_deleted"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id = Column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    approved_by = Column(Text, nullable=False, server_default="pending")
    approved_at = Column(UTCAwareDatetime, nullable=True)
    status = Column(
        SAEnum(
            HILApprovalStatusEnum,
            name="hil_approval_status_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        server_default=HILApprovalStatusEnum.PENDING.value,
    )
    checklist = Column(JSON, nullable=False, server_default="{}")
    notes = Column(Text, nullable=True)

    finding = relationship("Finding", back_populates="hil_approval")


class Report(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_finding_id", "finding_id"),
        Index("ix_reports_is_deleted", "is_deleted"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id = Column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    content_hash = Column(LargeBinary, nullable=False)
    manifest_hash = Column(LargeBinary, nullable=False)


class AuditMerkleRoot(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "audit_merkle_roots"
    __table_args__ = (Index("ix_audit_merkle_roots_is_deleted", "is_deleted"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), nullable=False)
    root_hash = Column(LargeBinary, nullable=False)
