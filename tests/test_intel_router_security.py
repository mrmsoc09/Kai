from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from apps.backend.src.core.auth import ROLE_ADMIN, ROLE_VIEWER, User
from apps.backend.src.core.intelligence_graph import EdgeType, get_intelligence_graph
from apps.backend.src.core.intelligence_memory import (
    MemoryScope,
    MemoryType,
    TargetFingerprint,
    ValidationStatus,
    get_memory_manager,
)
from apps.backend.src.routers import intel as intel_router


@pytest.fixture(autouse=True)
def isolated_intel_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    import apps.backend.src.core.intelligence_memory as memory_mod
    import apps.backend.src.core.intelligence_graph as graph_mod

    memory_mod._manager_instance = None
    graph_mod._graph_instance = None
    yield
    memory_mod._manager_instance = None
    graph_mod._graph_instance = None


def _seed_memory() -> tuple[str, str]:
    manager = get_memory_manager()
    shared_fingerprint = TargetFingerprint(domain="api.example.com", tech_stack=["nginx"], services=["https"])

    entry_tenant_a = manager.create_entry(
        memory_type=MemoryType.FINDING,
        scope=MemoryScope.MID_TERM,
        payload={"finding": "tenant-a"},
        confidence_score=0.9,
        validation_status=ValidationStatus.CONFIRMED,
        source_mission_id="mission-a",
        target_fingerprint=shared_fingerprint,
        tags=["xss", "tenant-a"],
        tenant_id="tenant-a",
    )
    entry_tenant_b = manager.create_entry(
        memory_type=MemoryType.FINDING,
        scope=MemoryScope.MID_TERM,
        payload={"finding": "tenant-b"},
        confidence_score=0.9,
        validation_status=ValidationStatus.CONFIRMED,
        source_mission_id="mission-b",
        target_fingerprint=shared_fingerprint,
        tags=["xss", "tenant-b"],
        tenant_id="tenant-b",
    )
    assert manager.ingest(entry_tenant_a)
    assert manager.ingest(entry_tenant_b)

    graph = get_intelligence_graph()
    graph.add_edge(entry_tenant_a.memory_id, entry_tenant_b.memory_id, EdgeType.SIMILAR_TO, weight=0.9)
    return entry_tenant_a.memory_id, entry_tenant_b.memory_id


def test_list_memory_is_tenant_scoped() -> None:
    _seed_memory()
    tenant_a_user = User(id=str(uuid4()), roles=[ROLE_VIEWER], tenant_id="tenant-a")

    response = intel_router.list_memory(
        scope=None,
        memory_type=None,
        validation_status=None,
        domain=None,
        search=None,
        min_confidence=0.0,
        limit=50,
        offset=0,
        user=tenant_a_user,
    )

    assert response.total == 1
    assert response.items[0].source_mission_id == "mission-a"


def test_get_memory_hides_cross_tenant_entries() -> None:
    _, tenant_b_memory_id = _seed_memory()
    tenant_a_user = User(id=str(uuid4()), roles=[ROLE_VIEWER], tenant_id="tenant-a")

    with pytest.raises(HTTPException) as exc_info:
        intel_router.get_memory(memory_id=tenant_b_memory_id, user=tenant_a_user)

    assert exc_info.value.status_code == 404


def test_relationships_filter_cross_tenant_neighbors_for_non_admin() -> None:
    tenant_a_memory_id, _ = _seed_memory()
    tenant_a_user = User(id=str(uuid4()), roles=[ROLE_VIEWER], tenant_id="tenant-a")
    admin_user = User(id=str(uuid4()), roles=[ROLE_ADMIN], tenant_id="tenant-a")

    restricted = intel_router.get_memory_relationships(memory_id=tenant_a_memory_id, user=tenant_a_user)
    privileged = intel_router.get_memory_relationships(memory_id=tenant_a_memory_id, user=admin_user)

    assert restricted["outbound"] == []
    assert len(privileged["outbound"]) == 1
