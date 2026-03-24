from __future__ import annotations
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    Enum as SAEnum,
    ForeignKey,
    DateTime,
    func,
    CheckConstraint,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from apps.backend.src.models.base import Base
from apps.backend.src.models.mixins import TimestampMixin


class UserRole(str, enum.Enum):
    """User role enum. Hierarchy: ADMIN > ANALYST > OPERATOR > VIEWER."""
    ADMIN = "admin"
    ANALYST = "analyst"
    OPERATOR = "operator"
    VIEWER = "viewer"

class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    config_json = Column(JSON, nullable=False, server_default="{}")

    users = relationship("User", back_populates="tenant")

class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", "tenant_id", name="uq_user_tenant_username"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    username = Column(String, unique=True, index=True, nullable=False) # Global unique or unique per tenant?
    hashed_password = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True) # Optional
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    must_change_password = Column(Boolean, default=False, nullable=False)
    role = Column(
        SAEnum(
            UserRole,
            name="user_role_enum",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=UserRole.VIEWER
    )

    tenant = relationship("Tenant", back_populates="users")
    api_tokens = relationship("APIToken", back_populates="user", cascade="all, delete-orphan")

class APIToken(Base, TimestampMixin):
    __tablename__ = "api_tokens"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    token_hash = Column(String, unique=True, nullable=False) # Hashed version of the token
    name = Column(String, nullable=True) # e.g., "CLI token", "Integration X"
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    user = relationship("User", back_populates="api_tokens")
    tenant = relationship("Tenant") # One-way relationship for tenant_id filtering


class UserScanQueueSettings(Base, TimestampMixin):
    __tablename__ = "user_scan_queue_settings"
    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_user_scan_queue_settings_user_tenant"),
        CheckConstraint("min_concurrent >= 1", name="ck_user_scan_queue_settings_min_ge_1"),
        CheckConstraint("max_concurrent <= 20", name="ck_user_scan_queue_settings_max_le_20"),
        CheckConstraint("max_concurrent >= 1", name="ck_user_scan_queue_settings_max_ge_1"),
        CheckConstraint("min_concurrent <= max_concurrent", name="ck_user_scan_queue_settings_min_le_max"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    min_concurrent = Column(Integer, nullable=False, server_default="1")
    max_concurrent = Column(Integer, nullable=False, server_default="3")

    user = relationship("User")
    tenant = relationship("Tenant")
