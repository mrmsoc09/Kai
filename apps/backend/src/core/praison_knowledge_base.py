"""
K1 Knowledge Base for Strategy Learning (Phase 4.5)
=====================================================
Governed, auditable knowledge store for cross-mission learning.

Retains curated intelligence:
  - tool_order_lesson:       Which tool orderings produce best results
  - prompt_effectiveness:    Which prompt profiles yield highest signal
  - exploit_pattern:         Repeatable vulnerability patterns per technology
  - false_positive_indicator: Scanner+template combos that produce FPs
  - evidence_heuristic:      Evidence collection patterns that improve findings
  - triage_pattern:          Efficient triage orderings for finding types

Governance:
  - All writes are auditable (event emitted + JSONL append)
  - Low-confidence lessons are quarantined, not written directly
  - Lessons have explicit provenance (mission_id, agent_id, strategy_id)
  - No LLM calls — all operations are deterministic
  - Knowledge cannot modify governance rules, scope, or graph topology

Persistence:
  - JSONL file at {K1_ARTIFACTS_ROOT}/knowledge/lessons.jsonl
  - In-memory index for fast lookup
  - Thread-safe read/write
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apps.backend.src.core.praison_execution_events import (
    emit,
    knowledge_lesson_created_event,
    knowledge_lesson_rejected_event,
)

logger = logging.getLogger(__name__)


# -- Lesson types --------------------------------------------------------------

VALID_LESSON_TYPES = frozenset({
    "tool_order_lesson",
    "prompt_effectiveness",
    "exploit_pattern",
    "false_positive_indicator",
    "evidence_heuristic",
    "triage_pattern",
})

# Confidence threshold below which lessons are quarantined
_QUARANTINE_THRESHOLD = 0.5


# -- KnowledgeLesson ----------------------------------------------------------

@dataclass(frozen=True)
class KnowledgeLesson:
    """
    A curated learning entry for cross-mission strategy improvement.

    Immutable once created. Quarantined lessons are stored separately
    and require governance review before promotion.
    """
    lesson_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    lesson_type: str = ""
    confidence: float = 0.0      # [0.0, 1.0]
    content: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    quarantined: bool = False

    # Provenance
    mission_id: str = ""
    workflow_id: str = ""
    program_id: str = ""
    agent_id: str = ""
    strategy_id: str = ""
    phase: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "lesson_id": self.lesson_id,
            "lesson_type": self.lesson_type,
            "confidence": round(self.confidence, 4),
            "content": self.content,
            "summary": self.summary,
            "quarantined": self.quarantined,
            "mission_id": self.mission_id,
            "workflow_id": self.workflow_id,
            "program_id": self.program_id,
            "agent_id": self.agent_id,
            "strategy_id": self.strategy_id,
            "phase": self.phase,
            "created_at": self.created_at,
        }


# -- KnowledgeBase -------------------------------------------------------------

class KnowledgeBase:
    """
    Governed knowledge store for strategy learning.

    Thread-safe. All writes produce audit events. Low-confidence lessons
    are quarantined rather than added to the active knowledge set.
    """

    def __init__(self, storage_root: str | None = None) -> None:
        root = Path(storage_root or os.getenv("K1_ARTIFACTS_ROOT", "artifacts"))
        self._lesson_path = root / "knowledge" / "lessons.jsonl"
        self._quarantine_path = root / "knowledge" / "quarantine.jsonl"
        self._lessons: dict[str, KnowledgeLesson] = {}
        self._quarantine: dict[str, KnowledgeLesson] = {}
        self._lock = threading.Lock()
        self._file_lock = threading.Lock()

    def add_lesson(self, lesson: KnowledgeLesson) -> KnowledgeLesson:
        """
        Add a curated lesson to the knowledge base.

        Validation:
          - lesson_type must be in VALID_LESSON_TYPES
          - summary must not be empty
          - confidence < threshold → quarantined

        Returns the lesson (possibly with quarantined=True).
        """
        # Validate
        rejection = self._validate_lesson(lesson)
        if rejection:
            emit(knowledge_lesson_rejected_event(
                mission_id=lesson.mission_id,
                workflow_id=lesson.workflow_id,
                program_id=lesson.program_id,
                lesson_id=lesson.lesson_id,
                reason=rejection,
                agent_id=lesson.agent_id,
            ))
            raise ValueError(rejection)

        # Quarantine low-confidence lessons
        if lesson.confidence < _QUARANTINE_THRESHOLD:
            quarantined = KnowledgeLesson(
                lesson_id=lesson.lesson_id,
                lesson_type=lesson.lesson_type,
                confidence=lesson.confidence,
                content=lesson.content,
                summary=lesson.summary,
                quarantined=True,
                mission_id=lesson.mission_id,
                workflow_id=lesson.workflow_id,
                program_id=lesson.program_id,
                agent_id=lesson.agent_id,
                strategy_id=lesson.strategy_id,
                phase=lesson.phase,
            )
            with self._lock:
                self._quarantine[quarantined.lesson_id] = quarantined
            self._persist(quarantined, quarantine=True)
            logger.info(
                "Lesson %s quarantined (confidence=%.2f < %.2f)",
                quarantined.lesson_id, quarantined.confidence, _QUARANTINE_THRESHOLD,
            )
            emit(knowledge_lesson_rejected_event(
                mission_id=lesson.mission_id,
                workflow_id=lesson.workflow_id,
                program_id=lesson.program_id,
                lesson_id=lesson.lesson_id,
                reason=f"Low confidence ({lesson.confidence:.2f}) — quarantined",
                agent_id=lesson.agent_id,
            ))
            return quarantined

        # Add to active knowledge
        with self._lock:
            self._lessons[lesson.lesson_id] = lesson
        self._persist(lesson, quarantine=False)

        emit(knowledge_lesson_created_event(
            mission_id=lesson.mission_id,
            workflow_id=lesson.workflow_id,
            program_id=lesson.program_id,
            lesson_id=lesson.lesson_id,
            lesson_type=lesson.lesson_type,
            agent_id=lesson.agent_id,
        ))

        logger.info(
            "Knowledge lesson added: %s type=%s confidence=%.2f",
            lesson.lesson_id, lesson.lesson_type, lesson.confidence,
        )
        return lesson

    def get_lessons(
        self,
        lesson_type: str | None = None,
        program_id: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[KnowledgeLesson]:
        """Query active (non-quarantined) lessons with optional filters."""
        with self._lock:
            results = list(self._lessons.values())

        if lesson_type:
            results = [l for l in results if l.lesson_type == lesson_type]
        if program_id:
            results = [l for l in results if l.program_id == program_id]
        if min_confidence > 0:
            results = [l for l in results if l.confidence >= min_confidence]

        results.sort(key=lambda l: l.confidence, reverse=True)
        return results[:limit]

    def get_quarantined(self, limit: int = 50) -> list[KnowledgeLesson]:
        """Return quarantined lessons awaiting review."""
        with self._lock:
            return list(self._quarantine.values())[:limit]

    def promote_lesson(self, lesson_id: str) -> KnowledgeLesson | None:
        """Promote a quarantined lesson to active knowledge. Governance action."""
        with self._lock:
            lesson = self._quarantine.pop(lesson_id, None)
            if not lesson:
                return None
            promoted = KnowledgeLesson(
                lesson_id=lesson.lesson_id,
                lesson_type=lesson.lesson_type,
                confidence=lesson.confidence,
                content=lesson.content,
                summary=lesson.summary,
                quarantined=False,
                mission_id=lesson.mission_id,
                workflow_id=lesson.workflow_id,
                program_id=lesson.program_id,
                agent_id=lesson.agent_id,
                strategy_id=lesson.strategy_id,
                phase=lesson.phase,
            )
            self._lessons[promoted.lesson_id] = promoted

        self._persist(promoted, quarantine=False)
        emit(knowledge_lesson_created_event(
            mission_id=promoted.mission_id,
            workflow_id=promoted.workflow_id,
            program_id=promoted.program_id,
            lesson_id=promoted.lesson_id,
            lesson_type=promoted.lesson_type,
            agent_id=promoted.agent_id,
        ))
        return promoted

    def lesson_count(self) -> int:
        with self._lock:
            return len(self._lessons)

    def quarantine_count(self) -> int:
        with self._lock:
            return len(self._quarantine)

    @staticmethod
    def _validate_lesson(lesson: KnowledgeLesson) -> str:
        """Return rejection reason or empty string if valid."""
        if lesson.lesson_type not in VALID_LESSON_TYPES:
            return (
                f"Invalid lesson_type '{lesson.lesson_type}'. "
                f"Must be one of: {sorted(VALID_LESSON_TYPES)}"
            )
        if not lesson.summary or not lesson.summary.strip():
            return "Lesson summary must not be empty"
        if not (0.0 <= lesson.confidence <= 1.0):
            return f"Confidence must be in [0.0, 1.0], got {lesson.confidence}"
        return ""

    def _persist(self, lesson: KnowledgeLesson, *, quarantine: bool) -> None:
        path = self._quarantine_path if quarantine else self._lesson_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._file_lock:
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(lesson.to_dict()) + "\n")
        except Exception as exc:
            logger.warning("Failed to persist lesson %s: %s", lesson.lesson_id, exc)


# -- Module singleton ----------------------------------------------------------

_KB: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    global _KB
    if _KB is None:
        _KB = KnowledgeBase()
    return _KB


def initialize_knowledge_base(storage_root: str | None = None) -> KnowledgeBase:
    global _KB
    _KB = KnowledgeBase(storage_root)
    return _KB
