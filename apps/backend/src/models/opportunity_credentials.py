"""SQLAlchemy models for opportunity credentials and access metadata.

Two tables:
- opportunity_credentials — tracks credentials stored in Vault (no plaintext)
- opportunity_access_metadata — describes available access types per program
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base
from .mixins import TimestampMixin, UTCAwareDatetime


class OpportunityCredential(Base, TimestampMixin):
    """Tracks a stored credential in Vault for an opportunity.

    Does NOT contain plaintext secrets — only references the Vault path.
    Includes audit metadata: who created it, when it was last accessed, how many times.
    """

    __tablename__ = "opportunity_credentials"
    __table_args__ = (
        CheckConstraint(
            "access_type IN ('unauthenticated', 'user_account', 'api_key', 'hunter_account', 'admin_account')",
            name="opportunity_credentials_access_type_allowed",
        ),
        CheckConstraint(
            "status IN ('active', 'expired', 'invalid', 'needs_renewal')",
            name="opportunity_credentials_status_allowed",
        ),
        CheckConstraint(
            "validation_method IN ('login_test', 'api_ping', 'manual')",
            name="opportunity_credentials_validation_method_allowed",
        ),
        UniqueConstraint(
            "program_id",
            "access_type",
            name="uq_opportunity_credentials_program_access_type",
        ),
        Index("ix_opportunity_credentials_program_id", "program_id"),
        Index("ix_opportunity_credentials_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # What type of access this credential provides.
    access_type = Column(Text, nullable=False)

    # Current status: active, expired, invalid, needs_renewal.
    status = Column(Text, nullable=False, server_default="active")

    # Path to the secret in Vault (KV v2).
    # Format: secret/opportunities/{program_id}/credentials/{access_type}
    vault_secret_path = Column(Text, nullable=False)

    # Plaintext username/email for display (NOT the password or secret).
    credential_username = Column(Text, nullable=True)

    # When this credential was last tested against the live service.
    last_validated = Column(UTCAwareDatetime, nullable=True)

    # How the credential was validated: login_test, api_ping, or manual trust.
    validation_method = Column(Text, nullable=True)

    # Optional notes (analyst-provided context).
    notes = Column(Text, nullable=True)

    # Audit trail: who created this credential.
    created_by = Column(Text, nullable=False, server_default="unknown")

    # Audit trail: who last accessed this credential (retrieved from Vault).
    last_accessed_by = Column(Text, nullable=True)

    # Audit trail: when the credential was last accessed.
    last_accessed_at = Column(UTCAwareDatetime, nullable=True)

    # Audit trail: how many times this credential has been retrieved from Vault.
    access_count = Column(Integer, nullable=False, server_default="0")

    # Relationship to Program (for eager loading if needed).
    program = relationship("Program", foreign_keys=[program_id])


class OpportunityAccessMetadata(Base, TimestampMixin):
    """Describes what access types are AVAILABLE for a program.

    This is separate from stored credentials. It describes "what could be available"
    even if no credentials are currently stored.

    Example: A program allows user_account signup, API key generation, and hunter
    accounts — but we haven't stored credentials for all of them yet.
    """

    __tablename__ = "opportunity_access_metadata"
    __table_args__ = (
        CheckConstraint(
            "access_type IN ('unauthenticated', 'user_account', 'api_key', 'hunter_account', 'admin_account')",
            name="opportunity_access_metadata_access_type_allowed",
        ),
        UniqueConstraint(
            "program_id",
            "access_type",
            name="uq_opportunity_access_metadata_program_access_type",
        ),
        Index("ix_opportunity_access_metadata_program_id", "program_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # What type of access this describes: user_account, api_key, hunter_account, etc.
    access_type = Column(Text, nullable=False)

    # Is this access type available for this program? (enabled/disabled).
    enabled = Column(Boolean, nullable=False, server_default="true")

    # URL where an analyst can sign up for this access type.
    signup_url = Column(Text, nullable=True)

    # Instructions on how to sign up (markdown or plain text).
    signup_instructions = Column(Text, nullable=True)

    # Does signup require an email address?
    requires_email = Column(Boolean, nullable=False, server_default="false")

    # Does signup require payment?
    requires_payment = Column(Boolean, nullable=False, server_default="false")

    # Rate limits or quota info (e.g., "100 requests/minute", "5000 requests/day").
    rate_limits = Column(Text, nullable=True)

    # For API keys: JSON list of available endpoints.
    # Example: ["GET /api/users", "GET /api/posts", "POST /api/comments"]
    available_endpoints = Column(Text, nullable=True)

    # Is there a testing account provided by the program?
    testing_account_available = Column(Boolean, nullable=False, server_default="false")

    # URL to apply for a testing account (if available).
    testing_account_url = Column(Text, nullable=True)

    # Instructions for getting a testing account.
    testing_instructions = Column(Text, nullable=True)

    # Relationship to Program (for eager loading if needed).
    program = relationship("Program", foreign_keys=[program_id])
