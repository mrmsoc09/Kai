from __future__ import annotations

import uuid

from sqlalchemy import Column, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from .base import Base
from .mixins import UTCAwareDatetime


class DedupFingerprint(Base):
    """Persistent deduplication fingerprint store.

    One row per unique (campaign_id, fingerprint) pair.  Near-duplicate
    detection is performed by querying on (campaign_id, endpoint).
    """

    __tablename__ = "dedup_fingerprints"
    __table_args__ = (
        UniqueConstraint("campaign_id", "fingerprint", name="uq_dedup_fingerprints_campaign_fp"),
        Index("ix_dedup_fingerprints_campaign_id", "campaign_id"),
        Index("ix_dedup_fingerprints_campaign_endpoint", "campaign_id", "endpoint"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # campaign_id kept as TEXT — no FK so campaign deletes don't cascade-block dedup cleanup
    campaign_id = Column(Text, nullable=False)
    # finding_id is a soft reference only — no FK constraint
    finding_id = Column(Text, nullable=True)
    # SHA-256 hex fingerprint of (endpoint + vuln_type + parameter)
    fingerprint = Column(Text, nullable=False)
    # Normalized endpoint path for near-duplicate detection
    endpoint = Column(Text, nullable=False)
    vuln_type = Column(Text, nullable=False)
    created_at = Column(UTCAwareDatetime, nullable=False)
