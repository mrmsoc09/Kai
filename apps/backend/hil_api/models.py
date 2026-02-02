from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, String, Text, Enum, JSON, TIMESTAMP, func, ForeignKey, LargeBinary
import uuid
from sqlalchemy.dialects.postgresql import UUID

Base = declarative_base()

class SeverityEnum(str, Enum):
    INFO = 'INFO'
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    CRITICAL = 'CRITICAL'

class StatusEnum(str, Enum):
    NEW = 'NEW'
    IN_REVIEW = 'IN_REVIEW'
    HIL_APPROVED = 'HIL_APPROVED'
    SUBMITTED = 'SUBMITTED'
    RESOLVED = 'RESOLVED'
    REJECTED = 'REJECTED'
    DUPLICATE = 'DUPLICATE'

class Finding(Base):
    __tablename__ = 'findings'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program = Column(Text, nullable=False)
    asset = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default='NEW')
    scope_json = Column(JSON, server_default='{}')
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    evidences = relationship('Evidence', back_populates='finding', cascade='all, delete-orphan')
    hil_approval = relationship('HILApproval', uselist=False, back_populates='finding', cascade='all, delete-orphan')

class Evidence(Base):
    __tablename__ = 'evidence'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id = Column(UUID(as_uuid=True), ForeignKey('findings.id', ondelete='CASCADE'), nullable=False)
    kind = Column(Text, nullable=False)
    uri = Column(Text, nullable=False)
    sha256 = Column(LargeBinary, nullable=False)
    meta = Column(JSON, server_default='{}')
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    finding = relationship('Finding', back_populates='evidences')

class HILApproval(Base):
    __tablename__ = 'hil_approvals'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id = Column(UUID(as_uuid=True), ForeignKey('findings.id', ondelete='CASCADE'), nullable=False, unique=True)
    approved_by = Column(Text, nullable=False)
    approved_at = Column(TIMESTAMP(timezone=True))
    status = Column(Text, nullable=False, server_default='PENDING')
    checklist = Column(JSON, nullable=False, server_default='{}')
    notes = Column(Text)

    finding = relationship('Finding', back_populates='hil_approval')

class Report(Base):
    __tablename__ = 'reports'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id = Column(UUID(as_uuid=True), ForeignKey('findings.id', ondelete='CASCADE'), nullable=False)
    content_hash = Column(LargeBinary, nullable=False)
    manifest_hash = Column(LargeBinary, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

class AuditMerkleRoot(Base):
    __tablename__ = 'audit_merkle_roots'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(Text, nullable=False)
    root_hash = Column(LargeBinary, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
