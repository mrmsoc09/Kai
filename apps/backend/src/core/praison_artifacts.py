"""
Praison Agent Artifacts
=======================
Structured artifact exchange model for K1's hybrid orchestration system.

IMMUTABILITY CONTRACT (Phase 3.5 hardening):
  AgentArtifact is frozen. Metadata fields (artifact_type, requires_governance_approval,
  requires_human_review, blocking, confidence, memory_scope) cannot be mutated after
  creation. The `content: dict` field remains mutable (practical constraint — we cannot
  deep-freeze arbitrary dicts) but is documented as a known limitation.
  tags field is coerced to tuple in __post_init__.

LOCK FIX (Phase 3.5):
  ArtifactStore uses two separate locks:
    _store_lock — guards in-memory dict (fast, never held during I/O)
    _file_lock  — guards disk appends (held only during file write)
  Previously a single lock was held during file I/O, serializing all store
  operations (including reads) behind disk latency.

SEVERITY FIX (Phase 3.5):
  make_vulnerability_signal normalizes severity to lowercase before comparison.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# ── Artifact types ────────────────────────────────────────────────────────────

class ArtifactType(str, Enum):
    RECON_SURFACE        = "recon_surface"
    VULNERABILITY_SIGNAL = "vulnerability_signal"
    TRIAGE_DECISION      = "triage_decision"
    PENTEST_EVIDENCE     = "pentest_evidence"
    REPORT_DRAFT         = "report_draft"
    GOVERNANCE_DECISION  = "governance_decision"
    HANDOFF_SUMMARY      = "handoff_summary"
    RAW_TOOL_OUTPUT      = "raw_tool_output"


# ── Confidence levels ─────────────────────────────────────────────────────────

class ConfidenceLevel(str, Enum):
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    INFERRED = "inferred"


# ── AgentArtifact ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AgentArtifact:
    """
    Structured data unit exchanged between agents. FROZEN for all metadata fields.

    NOTE: `content: dict[str, Any]` remains mutable (cannot deep-freeze arbitrary
    dicts). All governance/routing control fields (artifact_type, requires_*,
    blocking, confidence) are frozen and cannot be tampered with post-creation.

    Immutability guarantees:
      - FrozenInstanceError on direct field assignment
      - tags coerced to tuple in __post_init__
      - annotate() and forward() return new instances via replace()
    """

    # Identity
    artifact_id: str      = field(default_factory=lambda: str(uuid.uuid4()))
    artifact_type: ArtifactType = ArtifactType.RAW_TOOL_OUTPUT

    # Provenance
    producer_id: str      = ""
    consumer_id: str      = ""
    contract_id: str      = ""
    workflow_id: str      = ""
    program_id: str       = ""
    phase: str            = ""

    # Content (dict remains mutable — documented limitation)
    content: dict[str, Any] = field(default_factory=dict)
    summary: str          = ""
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    memory_scope: str     = "session"

    # Routing metadata — FROZEN, these control governance gates
    requires_human_review: bool         = False
    requires_governance_approval: bool  = False
    blocking: bool                      = False

    # Lifecycle
    created_at: datetime    = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int        = 86400
    tags: tuple[str, ...]   = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Coerce tags list to tuple for true immutability."""
        if isinstance(self.tags, list):
            object.__setattr__(self, "tags", tuple(self.tags))

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def is_expired(self) -> bool:
        age = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def annotate(self, *, consumer_id: str = "", tags: list[str] | None = None) -> "AgentArtifact":
        """Return new artifact with routing annotations applied."""
        merged_tags = tuple(set(self.tags) | set(tags or []))
        return replace(
            self,
            consumer_id=consumer_id or self.consumer_id,
            tags=merged_tags,
        )

    def forward(self, to_agent: str, contract_id: str = "") -> "AgentArtifact":
        """Return new artifact routed to a different consumer (new artifact_id)."""
        return replace(
            self,
            artifact_id=str(uuid.uuid4()),
            consumer_id=to_agent,
            contract_id=contract_id or self.contract_id,
            created_at=datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id":                  self.artifact_id,
            "artifact_type":                self.artifact_type.value,
            "producer_id":                  self.producer_id,
            "consumer_id":                  self.consumer_id,
            "contract_id":                  self.contract_id,
            "workflow_id":                  self.workflow_id,
            "program_id":                   self.program_id,
            "phase":                        self.phase,
            "content":                      self.content,
            "summary":                      self.summary,
            "confidence":                   self.confidence.value,
            "memory_scope":                 self.memory_scope,
            "requires_human_review":        self.requires_human_review,
            "requires_governance_approval": self.requires_governance_approval,
            "blocking":                     self.blocking,
            "created_at":                   self.created_at.isoformat(),
            "ttl_seconds":                  self.ttl_seconds,
            "tags":                         list(self.tags),
        }


# ── Artifact factory helpers ──────────────────────────────────────────────────

def make_recon_surface(
    producer_id: str,
    *,
    hosts: list[str],
    endpoints: list[str],
    technologies: list[str],
    workflow_id: str,
    program_id: str,
    phase: str = "recon",
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    contract_id: str = "",
) -> AgentArtifact:
    return AgentArtifact(
        artifact_type=ArtifactType.RECON_SURFACE,
        producer_id=producer_id,
        contract_id=contract_id,
        workflow_id=workflow_id,
        program_id=program_id,
        phase=phase,
        content={"hosts": hosts, "endpoints": endpoints, "technologies": technologies},
        summary=f"Surface: {len(hosts)} hosts, {len(endpoints)} endpoints",
        confidence=confidence,
        memory_scope="workflow",
    )


def make_vulnerability_signal(
    producer_id: str,
    *,
    target: str,
    signal_type: str,
    severity: str,
    evidence: dict[str, Any],
    workflow_id: str,
    program_id: str,
    phase: str = "scanning",
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
    contract_id: str = "",
) -> AgentArtifact:
    # SEVERITY FIX (Phase 3.5): normalize to lowercase before comparison
    sev = severity.lower().strip()
    return AgentArtifact(
        artifact_type=ArtifactType.VULNERABILITY_SIGNAL,
        producer_id=producer_id,
        contract_id=contract_id,
        workflow_id=workflow_id,
        program_id=program_id,
        phase=phase,
        content={"target": target, "signal_type": signal_type, "severity": sev, "evidence": evidence},
        summary=f"{sev.upper()} signal: {signal_type} on {target}",
        confidence=confidence,
        memory_scope="workflow",
        requires_human_review=(sev in ("critical", "high")),
        requires_governance_approval=(sev == "critical"),
        blocking=(sev == "critical"),
    )


def make_governance_decision(
    producer_id: str,
    *,
    approved: bool,
    reason: str,
    subject_artifact_id: str,
    workflow_id: str,
    program_id: str,
    contract_id: str = "",
) -> AgentArtifact:
    return AgentArtifact(
        artifact_type=ArtifactType.GOVERNANCE_DECISION,
        producer_id=producer_id,
        contract_id=contract_id,
        workflow_id=workflow_id,
        program_id=program_id,
        content={"approved": approved, "reason": reason, "subject_artifact_id": subject_artifact_id},
        summary=f"{'APPROVED' if approved else 'BLOCKED'}: {reason[:80]}",
        confidence=ConfidenceLevel.HIGH,
        memory_scope="mission",
        blocking=True,
    )


# ── ArtifactStore ─────────────────────────────────────────────────────────────

class ArtifactStore:
    """
    Thread-safe in-memory + optional disk artifact store.

    LOCK FIX (Phase 3.5):
      Two separate locks replace the single lock that was previously held
      during disk I/O:
        _store_lock — protects the in-memory dict (never held during file ops)
        _file_lock  — protects disk append (never held during dict ops)

      This means reads from the in-memory store are not blocked by concurrent
      disk writes. The brief window between in-memory write completion and
      disk flush is documented and accepted (process crash = in-memory artifact
      may not be on disk; disk is audit trail, not primary store).

    Disk persistence: append-only JSONL at
      K1_ARTIFACTS_ROOT/agent_artifacts/{workflow_id}.jsonl
    """

    def __init__(self) -> None:
        self._store: dict[str, AgentArtifact] = {}
        self._store_lock = threading.Lock()
        self._file_lock = threading.Lock()

    def put(self, artifact: AgentArtifact) -> AgentArtifact:
        """Store artifact in memory then persist to disk. Returns artifact unchanged."""
        with self._store_lock:
            self._store[artifact.artifact_id] = artifact
        # Persist OUTSIDE store_lock — file_lock used internally
        self._persist(artifact)
        return artifact

    def get(self, artifact_id: str) -> AgentArtifact | None:
        with self._store_lock:
            return self._store.get(artifact_id)

    def list_for_workflow(
        self,
        workflow_id: str,
        artifact_type: ArtifactType | None = None,
    ) -> list[AgentArtifact]:
        with self._store_lock:
            results = [
                a for a in self._store.values()
                if a.workflow_id == workflow_id
                and (artifact_type is None or a.artifact_type == artifact_type)
            ]
        return sorted(results, key=lambda a: a.created_at)

    def pending_review(self, workflow_id: str) -> list[AgentArtifact]:
        """Return non-expired artifacts requiring human review."""
        with self._store_lock:
            return [
                a for a in self._store.values()
                if a.workflow_id == workflow_id and a.requires_human_review and not a.is_expired
            ]

    def _persist(self, artifact: AgentArtifact) -> None:
        """Append artifact to JSONL file. Uses file_lock only — store_lock not held."""
        if not artifact.workflow_id:
            return
        root = Path(os.getenv("K1_ARTIFACTS_ROOT", "artifacts"))
        path = root / "agent_artifacts" / f"{artifact.workflow_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._file_lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(artifact.to_dict()) + "\n")


# ── Module singleton ──────────────────────────────────────────────────────────

_STORE = ArtifactStore()


def get_artifact_store() -> ArtifactStore:
    return _STORE
