from __future__ import annotations

from pathlib import Path

from apps.backend.src.core.experience_engine import ExperienceEngine
from apps.backend.src.core.experience_memory import ExperienceMemory
from apps.backend.src.core.master_orchestrator import MasterOrchestrator


def test_experience_memory_falls_back_to_local_runtime(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("K1_EXPERIENCE_MEMORY_PATH", "/proc/k1-forbidden/chromadb")
    ExperienceMemory._instance = None

    memory = ExperienceMemory.get_instance(disable_chroma=True)
    expected = tmp_path / "runtime" / "k1-experience-memory" / "chromadb"
    assert memory.storage_path == expected

    memory.record_lesson(
        target_fingerprint={"service": "nginx", "version": "1.18.0"},
        attempted_cve="CVE-2026-0001",
        outcome="Success",
        mutation_used="default",
    )
    lessons = memory.query_lessons(
        target_fingerprint={"service": "nginx", "version": "1.18.0"},
        attempted_cve="CVE-2026-0001",
        limit=5,
    )
    assert lessons
    assert memory.exploit_efficiency_ratio() == 1.0


def test_master_orchestrator_dispatch_records_execution_feedback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("K1_EXPERIENCE_MEMORY_PATH", str(tmp_path / "exp-memory"))
    monkeypatch.setenv("K1_VECTOR_MEMORY_PATH", str(tmp_path / "vec-memory"))
    ExperienceMemory._instance = None
    ExperienceEngine._instance = None

    orchestrator = MasterOrchestrator()

    def _fake_dispatch(instructions, *, target: str):
        return [{"step": 1, "tool_id": "tool.alpha", "status": "completed", "output": {"target": target}}]

    monkeypatch.setattr(orchestrator.dispatcher, "dispatch_instruction_tuples", _fake_dispatch)

    target_fp = {"service": "nginx", "version": "1.18.0", "waf": "none"}
    out = orchestrator.dispatch_instruction_tuples(
        [[1, "CVE-2026-1000", {}, {"timeout_seconds": 10}, None]],
        target="example.com",
        target_fingerprint=target_fp,
    )
    assert out[0]["status"] == "completed"

    lessons = orchestrator.experience_memory.query_lessons(
        target_fingerprint=target_fp,
        attempted_cve="CVE-2026-1000",
        limit=5,
    )
    assert lessons
