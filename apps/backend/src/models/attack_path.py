from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, Index, JSON, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base
from .mixins import TimestampMixin, UTCAwareDatetime


class AttackPathNode(Base, TimestampMixin):
    __tablename__ = "attack_path_nodes"
    __table_args__ = (
        Index("ix_attack_path_nodes_mission_id", "mission_id"),
        Index("ix_attack_path_nodes_node_type", "node_type"),
        Index("ix_attack_path_nodes_tenant_id", "tenant_id"),
        CheckConstraint(
            "node_type IN ('asset','endpoint','parameter','finding','evidence','auth_boundary')",
            name="attack_path_nodes_node_type_allowed",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    mission_id = Column(UUID(as_uuid=True), nullable=True)
    node_type = Column(Text, nullable=False)
    label = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=False, server_default="{}")

    outgoing_edges = relationship(
        "AttackPathEdge",
        foreign_keys="AttackPathEdge.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )
    incoming_edges = relationship(
        "AttackPathEdge",
        foreign_keys="AttackPathEdge.target_node_id",
        back_populates="target_node",
        cascade="all, delete-orphan",
    )


class AttackPathEdge(Base):
    __tablename__ = "attack_path_edges"
    __table_args__ = (
        Index("ix_attack_path_edges_source_node_id", "source_node_id"),
        Index("ix_attack_path_edges_target_node_id", "target_node_id"),
        Index("ix_attack_path_edges_relationship_type", "relationship_type"),
        Index("ix_attack_path_edges_tenant_id", "tenant_id"),
        CheckConstraint(
            "relationship_type IN ('leads_to','exploits','bypasses','discovers')",
            name="attack_path_edges_relationship_type_allowed",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="attack_path_edges_confidence_range",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    source_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("attack_path_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("attack_path_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, server_default="0.5")
    # server_default matches migration 0024 which sets server_default=sa.text("now()")
    created_at = Column(UTCAwareDatetime, nullable=False, server_default=func.now())

    source_node = relationship(
        "AttackPathNode", foreign_keys=[source_node_id], back_populates="outgoing_edges"
    )
    target_node = relationship(
        "AttackPathNode", foreign_keys=[target_node_id], back_populates="incoming_edges"
    )
