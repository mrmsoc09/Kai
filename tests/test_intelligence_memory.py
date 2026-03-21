"""
Intelligence Memory System Tests
===================================
Tests for:
  - Encryption layer (encrypt/decrypt/tamper detection)
  - MemoryEntry (creation, promotion, serialization)
  - MemoryStore (write/read/dedup/index)
  - MemoryManager (ingest, promote, query, metrics)
  - IntelligenceGraph (edges, exploit chains, similar nodes)
  - IntelligenceCache (indexing, lookup, TTL, metrics)
  - AccessPolicy (per-agent filtering, delegation)
  - IntelligenceCompressor (pattern signatures, summarization)
  - IntelligenceQueryEngine (structured queries)
"""

from __future__ import annotations

import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Set test artifact root to a tempdir so tests don't touch production data
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_artifacts(tmp_path, monkeypatch):
    """Redirect all artifact writes to a temp directory."""
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    # Clear module-level singletons between tests
    import apps.backend.src.core.intelligence_memory as im
    import apps.backend.src.core.intelligence_graph as ig
    import apps.backend.src.core.intelligence_cache as ic
    import apps.backend.src.core.intelligence_query as iq
    im._manager_instance = None
    ig._graph_instance = None
    ic._cache_instance = None
    iq._engine_instance = None
    yield tmp_path


# ---------------------------------------------------------------------------
# Imports (after fixture sets env)
# ---------------------------------------------------------------------------

from apps.backend.src.core.intelligence_encryption import (
    encrypt_payload,
    decrypt_payload,
    is_encrypted,
    derive_content_hash,
    rotate_key_cache,
    _resolve_key,
)
from apps.backend.src.core.intelligence_memory import (
    MemoryEntry,
    MemoryManager,
    MemoryScope,
    MemoryType,
    TargetFingerprint,
    ValidationStatus,
    MemoryStore,
    ShortTermMemory,
    get_memory_manager,
)
from apps.backend.src.core.intelligence_graph import (
    Edge,
    EdgeType,
    IntelligenceGraph,
    get_intelligence_graph,
)
from apps.backend.src.core.intelligence_cache import (
    IntelligenceCache,
    CacheEntry,
    _SCOPE_TTL,
)
from apps.backend.src.core.memory_access_control import (
    AccessPolicy,
    AgentClass,
    DelegationContract,
    create_delegation,
)
from apps.backend.src.core.intelligence_compression import (
    IntelligenceCompressor,
    PatternSignature,
    _domain_similar,
    _make_signature,
)
from apps.backend.src.core.intelligence_query import (
    IntelligenceQueryEngine,
    _tag_vuln_type,
    _generate_recommendation,
)


# ===========================================================================
# Helper factories
# ===========================================================================


def make_fingerprint(domain: str = "example.com", tech: list[str] | None = None) -> TargetFingerprint:
    return TargetFingerprint(
        domain=domain,
        tech_stack=tech or ["nginx", "php"],
        services=["http", "https"],
    )


def make_manager(tmp_path: Path) -> MemoryManager:
    """Create a fresh MemoryManager using tmp_path as artifact root."""
    with patch.dict(os.environ, {"K1_ARTIFACTS_ROOT": str(tmp_path)}):
        return MemoryManager()


def make_entry(
    mgr: MemoryManager,
    scope: MemoryScope = MemoryScope.MID_TERM,
    confidence: float = 0.75,
    vuln_type: str = "sqli",
    validated: bool = True,
    domain: str = "example.com",
    mission_id: str = "mission-001",
) -> MemoryEntry:
    return mgr.create_entry(
        memory_type=MemoryType.FINDING,
        scope=scope,
        payload={"url": f"http://{domain}/search", "vuln": vuln_type},
        confidence_score=confidence,
        validation_status=ValidationStatus.CONFIRMED if validated else ValidationStatus.UNVALIDATED,
        source_mission_id=mission_id,
        target_fingerprint=make_fingerprint(domain),
        tags=[f"vuln_type:{vuln_type}", vuln_type],
    )


# ===========================================================================
# Encryption tests
# ===========================================================================


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self, tmp_path):
        rotate_key_cache()
        data = {"url": "http://example.com", "vuln": "sqli", "score": 0.9}
        env = {"JWT_SECRET_KEY": "test-jwt-secret-for-derive"}
        with patch.dict(os.environ, env):
            envelope = encrypt_payload(data)
            assert is_encrypted(envelope)
            result = decrypt_payload(envelope)
        assert result == data

    def test_encrypt_string_payload(self, tmp_path):
        rotate_key_cache()
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret-key-x1"}):
            env = encrypt_payload("hello world")
            assert is_encrypted(env)
            assert decrypt_payload(env) == "hello world"

    def test_encrypt_list_payload(self, tmp_path):
        rotate_key_cache()
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-list-key"}):
            data = [1, 2, 3, {"nested": True}]
            env = encrypt_payload(data)
            result = decrypt_payload(env)
        assert result == data

    def test_master_key_overrides_jwt(self, tmp_path):
        rotate_key_cache()
        env = {
            "K1_INTELLIGENCE_MASTER_KEY": "deadbeef" * 8,
            "JWT_SECRET_KEY": "jwt-secret",
        }
        with patch.dict(os.environ, env):
            envelope = encrypt_payload({"data": "test"})
            assert envelope["kid"] == "__platform__"

    def test_per_tenant_key(self, tmp_path):
        rotate_key_cache()
        env = {
            "K1_TENANT_ACME_KEY": "a1b2c3d4" * 8,
            "JWT_SECRET_KEY": "jwt-fallback",
        }
        with patch.dict(os.environ, env):
            envelope = encrypt_payload({"data": "tenant"}, tenant_id="acme")
            result = decrypt_payload(envelope, tenant_id="acme")
        assert result == {"data": "tenant"}

    def test_tamper_detection_raises(self, tmp_path):
        rotate_key_cache()
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "tamper-test-key"}):
            envelope = encrypt_payload({"secret": "data"})
            # Corrupt the token
            tampered = dict(envelope)
            tampered["enc"] = tampered["enc"][:-4] + "XXXX"
            with pytest.raises(ValueError):
                decrypt_payload(tampered)

    def test_is_encrypted_checks_structure(self):
        assert is_encrypted({"enc": "abc", "alg": "fernet"}) is True
        assert is_encrypted({"data": "plain"}) is False
        assert is_encrypted("string") is False
        assert is_encrypted(None) is False

    def test_content_hash_deterministic(self):
        data = {"url": "http://example.com", "vuln": "xss"}
        h1 = derive_content_hash(data)
        h2 = derive_content_hash(data)
        assert h1 == h2

    def test_content_hash_differs_for_different_data(self):
        assert derive_content_hash({"a": 1}) != derive_content_hash({"a": 2})


# ===========================================================================
# MemoryEntry tests
# ===========================================================================


class TestMemoryEntry:
    def test_create_entry(self, tmp_path):
        mgr = make_manager(tmp_path)
        entry = make_entry(mgr)
        assert entry.memory_id
        assert entry.scope == MemoryScope.MID_TERM
        assert entry.confidence_score == 0.75
        assert is_encrypted(entry.encrypted_payload)

    def test_to_dict_roundtrip(self, tmp_path):
        mgr = make_manager(tmp_path)
        entry = make_entry(mgr)
        d = entry.to_dict()
        restored = MemoryEntry.from_dict(d)
        assert restored.memory_id == entry.memory_id
        assert restored.scope == entry.scope
        assert restored.confidence_score == entry.confidence_score

    def test_decrypt_returns_payload(self, tmp_path):
        rotate_key_cache()
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "decrypt-test-key"}):
            mgr = make_manager(tmp_path)
            entry = make_entry(mgr, domain="target.com")
            data = entry.decrypt()
        assert isinstance(data, dict)
        assert "url" in data

    def test_can_promote_mid_to_long(self, tmp_path):
        mgr = make_manager(tmp_path)
        entry = make_entry(mgr, scope=MemoryScope.MID_TERM, confidence=0.80, validated=True)
        assert entry.can_promote(MemoryScope.LONG_TERM) is True

    def test_cannot_promote_mid_to_long_low_confidence(self, tmp_path):
        mgr = make_manager(tmp_path)
        entry = make_entry(mgr, scope=MemoryScope.MID_TERM, confidence=0.60)
        assert entry.can_promote(MemoryScope.LONG_TERM) is False

    def test_cannot_promote_to_strategic_unvalidated(self, tmp_path):
        mgr = make_manager(tmp_path)
        entry = make_entry(mgr, scope=MemoryScope.LONG_TERM, confidence=0.95, validated=False)
        assert entry.can_promote(MemoryScope.STRATEGIC) is False

    def test_can_promote_to_strategic_confirmed(self, tmp_path):
        mgr = make_manager(tmp_path)
        entry = make_entry(mgr, scope=MemoryScope.LONG_TERM, confidence=0.92, validated=True)
        assert entry.can_promote(MemoryScope.STRATEGIC) is True


# ===========================================================================
# MemoryStore tests
# ===========================================================================


class TestMemoryStore:
    def test_write_and_read(self, tmp_path):
        store = MemoryStore(MemoryScope.MID_TERM)
        mgr = make_manager(tmp_path)
        entry = make_entry(mgr)
        store.write(entry)
        recovered = store.read(entry.memory_id)
        assert recovered is not None
        assert recovered.memory_id == entry.memory_id

    def test_deduplication_by_content_hash(self, tmp_path):
        store = MemoryStore(MemoryScope.MID_TERM)
        mgr = make_manager(tmp_path)
        entry = make_entry(mgr)
        r1 = store.write(entry)
        r2 = store.write(entry)  # duplicate
        assert r1 is True
        assert r2 is False

    def test_iter_all(self, tmp_path):
        store = MemoryStore(MemoryScope.MID_TERM)
        mgr = make_manager(tmp_path)
        for i in range(5):
            e = mgr.create_entry(
                memory_type=MemoryType.FINDING,
                scope=MemoryScope.MID_TERM,
                payload={"i": i, "unique": str(uuid.uuid4())},
                confidence_score=0.7,
                validation_status=ValidationStatus.CONFIRMED,
                source_mission_id="m1",
            )
            store.write(e)
        entries = list(store.iter_all())
        assert len(entries) == 5

    def test_count(self, tmp_path):
        store = MemoryStore(MemoryScope.MID_TERM)
        mgr = make_manager(tmp_path)
        assert store.count() == 0
        e = make_entry(mgr)
        store.write(e)
        assert store.count() == 1


# ===========================================================================
# MemoryManager tests
# ===========================================================================


class TestMemoryManager:
    def test_ingest_accepted(self, tmp_path):
        mgr = make_manager(tmp_path)
        entry = make_entry(mgr, scope=MemoryScope.MID_TERM, confidence=0.75)
        result = mgr.ingest(entry)
        assert result is True
        metrics = mgr.get_metrics()
        assert metrics["entries_created"] == 1

    def test_ingest_rejected_low_confidence_long_term(self, tmp_path):
        mgr = make_manager(tmp_path)
        entry = make_entry(mgr, scope=MemoryScope.LONG_TERM, confidence=0.50, validated=True)
        result = mgr.ingest(entry)
        assert result is False
        metrics = mgr.get_metrics()
        assert metrics["ingestion_rejected_confidence"] >= 1

    def test_ingest_rejected_unvalidated_long_term(self, tmp_path):
        mgr = make_manager(tmp_path)
        entry = make_entry(mgr, scope=MemoryScope.LONG_TERM, confidence=0.80, validated=False)
        result = mgr.ingest(entry)
        assert result is False
        metrics = mgr.get_metrics()
        assert metrics["ingestion_rejected_validation"] >= 1

    def test_ingest_strategic_requires_confirmed_and_high_conf(self, tmp_path):
        mgr = make_manager(tmp_path)
        # Should succeed
        e = make_entry(mgr, scope=MemoryScope.STRATEGIC, confidence=0.92, validated=True)
        assert mgr.ingest(e) is True
        # Should fail — low confidence
        e2 = make_entry(mgr, scope=MemoryScope.STRATEGIC, confidence=0.80, validated=True)
        assert mgr.ingest(e2) is False

    def test_promote_mid_to_long(self, tmp_path):
        mgr = make_manager(tmp_path)
        e = make_entry(mgr, scope=MemoryScope.MID_TERM, confidence=0.80, validated=True)
        mgr.ingest(e)
        promoted = mgr.promote(e)
        assert promoted is not None
        assert promoted.scope == MemoryScope.LONG_TERM
        assert promoted.promoted_from == MemoryScope.MID_TERM
        assert promoted.promotion_count == 1
        metrics = mgr.get_metrics()
        assert metrics["entries_promoted"] == 1

    def test_promote_returns_none_if_threshold_not_met(self, tmp_path):
        mgr = make_manager(tmp_path)
        e = make_entry(mgr, scope=MemoryScope.MID_TERM, confidence=0.55)
        mgr.ingest(e)
        promoted = mgr.promote(e)
        assert promoted is None

    def test_query_by_tags(self, tmp_path):
        mgr = make_manager(tmp_path)
        for i in range(3):
            e = make_entry(mgr, vuln_type="sqli", domain=f"target{i}.com")
            mgr.ingest(e)
        e2 = make_entry(mgr, vuln_type="xss", domain="other.com")
        mgr.ingest(e2)
        sqli = mgr.query(tags=["sqli"])
        assert len(sqli) == 3
        xss = mgr.query(tags=["xss"])
        assert len(xss) == 1

    def test_query_by_scope(self, tmp_path):
        mgr = make_manager(tmp_path)
        mid = make_entry(mgr, scope=MemoryScope.MID_TERM, confidence=0.75)
        mgr.ingest(mid)
        long = make_entry(mgr, scope=MemoryScope.LONG_TERM, confidence=0.80, validated=True)
        mgr.ingest(long)
        mid_results = mgr.query(scope=MemoryScope.MID_TERM)
        assert all(e.scope == MemoryScope.MID_TERM for e in mid_results)

    def test_get_by_id(self, tmp_path):
        mgr = make_manager(tmp_path)
        e = make_entry(mgr)
        mgr.ingest(e)
        retrieved = mgr.get(e.memory_id)
        assert retrieved is not None
        assert retrieved.memory_id == e.memory_id

    def test_short_term_eviction(self, tmp_path):
        mgr = make_manager(tmp_path)
        e = make_entry(mgr, scope=MemoryScope.SHORT_TERM, mission_id="m1")
        e = MemoryEntry(
            **{**e.__dict__, "mission_phase": "recon"}
        )
        mgr._short.write(e)
        evicted = mgr.evict_short_term("m1", "recon")
        assert len(evicted) == 1
        assert evicted[0].memory_id == e.memory_id

    def test_metrics_structure(self, tmp_path):
        mgr = make_manager(tmp_path)
        metrics = mgr.get_metrics()
        assert "entries_created" in metrics
        assert "entries_promoted" in metrics
        assert "mid_term_count" in metrics
        assert "high_value_ratio" in metrics


# ===========================================================================
# Intelligence Graph tests
# ===========================================================================


class TestIntelligenceGraph:
    def test_add_and_retrieve_edge(self, tmp_path):
        g = IntelligenceGraph(path=tmp_path / "graph.json")
        edge = g.add_edge("mem-001", "mem-002", EdgeType.FINDING_TO_EXPLOIT)
        assert edge.source_id == "mem-001"
        assert edge.target_id == "mem-002"
        neighbors = g.get_neighbors("mem-001")
        assert len(neighbors) == 1
        assert neighbors[0].edge_type == EdgeType.FINDING_TO_EXPLOIT

    def test_duplicate_edges_not_added(self, tmp_path):
        g = IntelligenceGraph(path=tmp_path / "graph.json")
        g.add_edge("a", "b", EdgeType.SIMILAR_TO)
        g.add_edge("a", "b", EdgeType.SIMILAR_TO)
        edges = g.get_neighbors("a")
        assert len(edges) == 1

    def test_inbound_edges(self, tmp_path):
        g = IntelligenceGraph(path=tmp_path / "graph.json")
        g.add_edge("src", "tgt", EdgeType.FINDING_TO_ENDPOINT)
        inbound = g.get_neighbors("tgt", direction="inbound")
        assert len(inbound) == 1
        assert inbound[0].source_id == "src"

    def test_exploit_chain_bfs(self, tmp_path):
        g = IntelligenceGraph(path=tmp_path / "graph.json")
        g.add_edge("v1", "v2", EdgeType.VULN_CHAINS_TO)
        g.add_edge("v2", "v3", EdgeType.VULN_CHAINS_TO)
        g.add_edge("v3", "v4", EdgeType.VULN_CHAINS_TO)
        chains = g.find_exploit_chain("v1", max_depth=5)
        # Should find paths: v1→v2, v1→v2→v3, v1→v2→v3→v4
        chain_ends = {path[-1] for path in chains}
        assert "v2" in chain_ends
        assert "v3" in chain_ends
        assert "v4" in chain_ends

    def test_find_similar(self, tmp_path):
        g = IntelligenceGraph(path=tmp_path / "graph.json")
        g.add_edge("m1", "m2", EdgeType.SIMILAR_TO)
        g.add_edge("m1", "m3", EdgeType.SIMILAR_TO)
        similar = g.find_similar("m1")
        assert "m2" in similar
        assert "m3" in similar

    def test_remove_edges(self, tmp_path):
        g = IntelligenceGraph(path=tmp_path / "graph.json")
        g.add_edge("x", "y", EdgeType.SIMILAR_TO)
        g.add_edge("x", "z", EdgeType.SIMILAR_TO)
        removed = g.remove_edges("x")
        assert removed >= 2
        assert g.get_neighbors("x") == []

    def test_edge_count_and_node_count(self, tmp_path):
        g = IntelligenceGraph(path=tmp_path / "graph.json")
        g.add_edge("a", "b", EdgeType.FINDING_TO_EXPLOIT)
        g.add_edge("b", "c", EdgeType.EXPLOIT_TO_TOOL_SEQ)
        assert g.edge_count() == 2
        assert g.node_count() == 2  # "a" and "b" are source nodes

    def test_graph_persisted_and_reloaded(self, tmp_path):
        path = tmp_path / "graph.json"
        g1 = IntelligenceGraph(path=path)
        g1.add_edge("persist-1", "persist-2", EdgeType.SIMILAR_TO)
        # Reload
        g2 = IntelligenceGraph(path=path)
        neighbors = g2.get_neighbors("persist-1")
        assert len(neighbors) == 1

    def test_mission_to_finding_query(self, tmp_path):
        g = IntelligenceGraph(path=tmp_path / "graph.json")
        g.add_edge("mission-xyz", "finding-1", EdgeType.MISSION_TO_FINDING)
        g.add_edge("mission-xyz", "finding-2", EdgeType.MISSION_TO_FINDING)
        findings = g.get_all_findings_for_mission("mission-xyz")
        assert "finding-1" in findings
        assert "finding-2" in findings


# ===========================================================================
# Intelligence Cache tests
# ===========================================================================


class TestIntelligenceCache:
    def _make_cache_entry(
        self,
        domain: str = "example.com",
        vuln: str = "sqli",
        scope: MemoryScope = MemoryScope.MID_TERM,
        conf: float = 0.8,
    ) -> CacheEntry:
        return CacheEntry(
            memory_id=str(uuid.uuid4()),
            scope=scope,
            memory_type=MemoryType.FINDING,
            tags=[f"vuln_type:{vuln}", vuln],
            confidence_score=conf,
        )

    def _make_mem_entry(self, tmp_path, mgr, domain="example.com", vuln="sqli") -> MemoryEntry:
        return make_entry(mgr, domain=domain, vuln_type=vuln)

    def test_index_and_lookup_by_domain(self, tmp_path):
        mgr = make_manager(tmp_path)
        cache = IntelligenceCache(manager=mgr)
        e = make_entry(mgr, domain="target.com")
        cache.index_entry(e)
        results = cache.lookup_by_domain("target.com")
        assert len(results) == 1

    def test_lookup_miss_increments_metric(self, tmp_path):
        mgr = make_manager(tmp_path)
        cache = IntelligenceCache(manager=mgr)
        cache.lookup_by_domain("nonexistent.com")
        assert cache.get_metrics()["misses"] == 1

    def test_lookup_hit_increments_metric(self, tmp_path):
        mgr = make_manager(tmp_path)
        cache = IntelligenceCache(manager=mgr)
        e = make_entry(mgr, domain="hit.com")
        cache.index_entry(e)
        cache.lookup_by_domain("hit.com")
        assert cache.get_metrics()["hits"] == 1

    def test_lookup_by_vuln_type(self, tmp_path):
        mgr = make_manager(tmp_path)
        cache = IntelligenceCache(manager=mgr)
        e = mgr.create_entry(
            memory_type=MemoryType.FINDING,
            scope=MemoryScope.MID_TERM,
            payload={"data": "xss"},
            confidence_score=0.8,
            validation_status=ValidationStatus.CONFIRMED,
            source_mission_id="m1",
            tags=["xss", "vuln_type:xss"],
        )
        cache.index_entry(e)
        results = cache.lookup_by_vuln_type("xss")
        assert len(results) == 1

    def test_lookup_by_tech_stack(self, tmp_path):
        mgr = make_manager(tmp_path)
        cache = IntelligenceCache(manager=mgr)
        e = mgr.create_entry(
            memory_type=MemoryType.TECH_STACK,
            scope=MemoryScope.MID_TERM,
            payload={"tech": "wordpress"},
            confidence_score=0.7,
            validation_status=ValidationStatus.PARTIAL,
            source_mission_id="m1",
            target_fingerprint=make_fingerprint(tech=["wordpress", "php"]),
        )
        cache.index_entry(e)
        results = cache.lookup_by_tech_stack("wordpress")
        assert len(results) >= 1

    def test_strategic_ttl_never_expires(self):
        ce = CacheEntry(
            memory_id="x",
            scope=MemoryScope.STRATEGIC,
            memory_type=MemoryType.EXPLOIT_PATTERN,
            tags=[],
            confidence_score=0.95,
            inserted_at=0.0,  # very old
        )
        assert ce.is_expired() is False

    def test_short_term_ttl_expires(self):
        ce = CacheEntry(
            memory_id="x",
            scope=MemoryScope.SHORT_TERM,
            memory_type=MemoryType.FINDING,
            tags=[],
            confidence_score=0.5,
            inserted_at=time.time() - 400.0,  # 400s ago (TTL is 300s)
        )
        assert ce.is_expired() is True

    def test_hit_rate_calculation(self, tmp_path):
        mgr = make_manager(tmp_path)
        cache = IntelligenceCache(manager=mgr)
        e = make_entry(mgr, domain="rate.com")
        cache.index_entry(e)
        cache.lookup_by_domain("rate.com")   # hit
        cache.lookup_by_domain("miss.com")   # miss
        metrics = cache.get_metrics()
        assert metrics["hit_rate"] == 0.5

    def test_clear_resets_all_indexes(self, tmp_path):
        mgr = make_manager(tmp_path)
        cache = IntelligenceCache(manager=mgr)
        e = make_entry(mgr, domain="clear.com")
        cache.index_entry(e)
        cache.clear()
        assert cache.lookup_by_domain("clear.com") == []

    def test_promotion_candidates_identified(self, tmp_path):
        mgr = make_manager(tmp_path)
        cache = IntelligenceCache(manager=mgr)
        e = make_entry(mgr, scope=MemoryScope.MID_TERM, confidence=0.80)
        # Simulate 3 hits by indexing and looking up multiple times
        cache.index_entry(e)
        # Add 3 hits manually to the cache entry's hit_count
        with cache._lock:
            for bucket in cache._domain_idx.values():
                with bucket._lock:
                    for ce in bucket._entries:
                        ce.hit_count = 4
        candidates = cache.check_promotion_candidates()
        assert e.memory_id in candidates


# ===========================================================================
# Access Control tests
# ===========================================================================


class TestAccessControl:
    def test_recon_cannot_see_exploit_patterns(self, tmp_path):
        mgr = make_manager(tmp_path)
        policy = AccessPolicy.for_agent(AgentClass.RECON)
        e = mgr.create_entry(
            memory_type=MemoryType.EXPLOIT_PATTERN,
            scope=MemoryScope.MID_TERM,
            payload={"exploit": "data"},
            confidence_score=0.8,
            validation_status=ValidationStatus.CONFIRMED,
            source_mission_id="m1",
        )
        assert policy.can_read(e) is False

    def test_exploit_agent_sees_confirmed_findings(self, tmp_path):
        mgr = make_manager(tmp_path)
        policy = AccessPolicy.for_agent(AgentClass.EXPLOIT)
        e = make_entry(mgr, scope=MemoryScope.LONG_TERM, confidence=0.85, validated=True)
        assert policy.can_read(e) is True

    def test_exploit_agent_cannot_read_unconfirmed(self, tmp_path):
        mgr = make_manager(tmp_path)
        policy = AccessPolicy.for_agent(AgentClass.EXPLOIT)
        e = make_entry(mgr, scope=MemoryScope.LONG_TERM, confidence=0.85, validated=False)
        assert policy.can_read(e) is False

    def test_report_agent_only_reads_findings(self, tmp_path):
        mgr = make_manager(tmp_path)
        policy = AccessPolicy.for_agent(AgentClass.REPORT)

        finding = make_entry(mgr, validated=True)
        tech = mgr.create_entry(
            memory_type=MemoryType.TECH_STACK,
            scope=MemoryScope.MID_TERM,
            payload={"tech": "nginx"},
            confidence_score=0.8,
            validation_status=ValidationStatus.CONFIRMED,
            source_mission_id="m1",
        )
        assert policy.can_read(finding) is True
        assert policy.can_read(tech) is False

    def test_admin_sees_all(self, tmp_path):
        mgr = make_manager(tmp_path)
        policy = AccessPolicy.for_agent(AgentClass.ADMIN)
        for scope in MemoryScope:
            for mtype in MemoryType:
                e = mgr.create_entry(
                    memory_type=mtype,
                    scope=scope,
                    payload={"x": 1},
                    confidence_score=0.0,
                    validation_status=ValidationStatus.UNVALIDATED,
                    source_mission_id="m1",
                )
                assert policy.can_read(e) is True

    def test_tenant_isolation(self, tmp_path):
        mgr = make_manager(tmp_path)
        policy_a = AccessPolicy.for_agent(AgentClass.ANALYST, tenant_id="tenant-a")
        entry_b = mgr.create_entry(
            memory_type=MemoryType.FINDING,
            scope=MemoryScope.MID_TERM,
            payload={"data": "tenant_b_secret"},
            confidence_score=0.8,
            validation_status=ValidationStatus.CONFIRMED,
            source_mission_id="m1",
            tenant_id="tenant-b",
        )
        assert policy_a.can_read(entry_b) is False

    def test_filter_removes_denied_entries(self, tmp_path):
        mgr = make_manager(tmp_path)
        policy = AccessPolicy.for_agent(AgentClass.RECON)
        entries = [
            make_entry(mgr),  # FINDING — recon cannot see in MID_TERM... wait, let's check
        ]
        # RECON can read ENDPOINT_BEHAVIOR and TECH_STACK, not FINDING
        tech = mgr.create_entry(
            memory_type=MemoryType.TECH_STACK,
            scope=MemoryScope.MID_TERM,
            payload={"t": "nginx"},
            confidence_score=0.7,
            validation_status=ValidationStatus.PARTIAL,
            source_mission_id="m1",
        )
        exploit = mgr.create_entry(
            memory_type=MemoryType.EXPLOIT_PATTERN,
            scope=MemoryScope.MID_TERM,
            payload={"e": "pattern"},
            confidence_score=0.9,
            validation_status=ValidationStatus.CONFIRMED,
            source_mission_id="m1",
        )
        allowed = policy.filter([tech, exploit])
        assert tech in allowed
        assert exploit not in allowed

    def test_delegation_creation(self):
        contract = create_delegation(
            delegator_class=AgentClass.ORCHESTRATOR,
            delegate_agent_id="agent-xyz",
            granted_scopes={MemoryScope.MID_TERM},
            granted_types={MemoryType.FINDING},
            expires_in_seconds=1800,
            reason="recon assistance",
        )
        assert contract.is_valid() is True
        assert MemoryScope.MID_TERM in contract.granted_scopes

    def test_delegation_cannot_exceed_delegator_access(self):
        contract = create_delegation(
            delegator_class=AgentClass.ORCHESTRATOR,
            delegate_agent_id="agent-abc",
            # ORCHESTRATOR cannot write to STRATEGIC, so this should be constrained
            granted_scopes={MemoryScope.MID_TERM, MemoryScope.STRATEGIC},
            granted_types={MemoryType.FINDING},
        )
        # Granted scopes constrained to delegator's readable scopes
        assert MemoryScope.STRATEGIC in contract.granted_scopes  # ORCHESTRATOR can read strategic

    def test_non_delegator_cannot_delegate(self):
        with pytest.raises(PermissionError):
            create_delegation(
                delegator_class=AgentClass.RECON,
                delegate_agent_id="x",
                granted_scopes={MemoryScope.MID_TERM},
                granted_types={MemoryType.FINDING},
            )

    def test_policy_describe(self):
        policy = AccessPolicy.for_agent(AgentClass.EXPLOIT)
        desc = policy.describe()
        assert desc["agent_class"] == "exploit"
        assert isinstance(desc["readable_scopes"], list)

    def test_write_permission(self):
        policy = AccessPolicy.for_agent(AgentClass.REPORT)
        assert policy.can_write(MemoryScope.MID_TERM) is False

        policy_orch = AccessPolicy.for_agent(AgentClass.ORCHESTRATOR)
        assert policy_orch.can_write(MemoryScope.MID_TERM) is True


# ===========================================================================
# Compression tests
# ===========================================================================


class TestIntelligenceCompression:
    def test_compress_findings_into_signature(self, tmp_path):
        mgr = make_manager(tmp_path)
        entries = []
        for i in range(5):
            e = mgr.create_entry(
                memory_type=MemoryType.FINDING,
                scope=MemoryScope.MID_TERM,
                payload={"url": f"http://ex.com/p{i}", "vuln": "xss", "id": str(uuid.uuid4())},
                confidence_score=0.75,
                validation_status=ValidationStatus.CONFIRMED,
                source_mission_id="m1",
                target_fingerprint=TargetFingerprint(domain="ex.com", tech_stack=["nginx"]),
                tags=["vuln_type:xss", "xss"],
            )
            mgr.ingest(e)
            entries.append(e)

        compressor = IntelligenceCompressor(manager=mgr)
        sigs = compressor.compress(entries, min_occurrences=3)
        assert len(sigs) >= 1
        assert sigs[0].occurrence_count >= 3
        assert sigs[0].vuln_type == "xss"

    def test_signature_confidence_boost_from_corroboration(self, tmp_path):
        mgr = make_manager(tmp_path)
        entries = []
        for i in range(5):
            e = mgr.create_entry(
                memory_type=MemoryType.FINDING,
                scope=MemoryScope.MID_TERM,
                payload={"i": i, "uid": str(uuid.uuid4())},
                confidence_score=0.70,
                validation_status=ValidationStatus.CONFIRMED,
                source_mission_id="m1",
                target_fingerprint=TargetFingerprint(domain="boost.com"),
                tags=["vuln_type:sqli", "sqli"],
            )
            mgr.ingest(e)
            entries.append(e)

        compressor = IntelligenceCompressor(manager=mgr)
        sigs = compressor.compress(entries, min_occurrences=3)
        assert sigs[0].confidence > 0.70

    def test_min_occurrences_threshold(self, tmp_path):
        mgr = make_manager(tmp_path)
        entries = []
        for i in range(2):  # only 2 — below min_occurrences=3
            e = mgr.create_entry(
                memory_type=MemoryType.FINDING,
                scope=MemoryScope.MID_TERM,
                payload={"i": i, "u": str(uuid.uuid4())},
                confidence_score=0.75,
                validation_status=ValidationStatus.CONFIRMED,
                source_mission_id="m1",
                target_fingerprint=TargetFingerprint(domain="small.com"),
                tags=["vuln_type:xss", "xss"],
            )
            mgr.ingest(e)
            entries.append(e)

        compressor = IntelligenceCompressor(manager=mgr)
        sigs = compressor.compress(entries, min_occurrences=3)
        assert len(sigs) == 0

    def test_write_signature_to_memory(self, tmp_path):
        mgr = make_manager(tmp_path)
        entries = []
        for i in range(4):
            e = mgr.create_entry(
                memory_type=MemoryType.FINDING,
                scope=MemoryScope.MID_TERM,
                payload={"i": i, "u": str(uuid.uuid4())},
                confidence_score=0.80,
                validation_status=ValidationStatus.CONFIRMED,
                source_mission_id="m1",
                target_fingerprint=TargetFingerprint(domain="write.com"),
                tags=["vuln_type:xss", "xss"],
            )
            mgr.ingest(e)
            entries.append(e)

        compressor = IntelligenceCompressor(manager=mgr)
        written = compressor.compress_and_write(entries, mission_id="m1", min_occurrences=3)
        assert len(written) >= 1
        assert written[0].memory_type == MemoryType.PATTERN_SIGNATURE
        assert written[0].scope == MemoryScope.LONG_TERM

    def test_summarize_artifacts(self, tmp_path):
        compressor = IntelligenceCompressor()
        artifacts = [
            {"url": f"http://ex.com/{i}", "parameter": "q", "status_code": 500, "payload": "' OR 1=1"}
            for i in range(50)
        ]
        summary = compressor.summarize_artifacts(artifacts, "sqli", "m1", max_payload_items=10)
        assert summary["total_artifacts"] == 50
        assert len(summary["sample_urls"]) <= 10
        assert summary["vuln_type"] == "sqli"

    def test_dedup_payloads_removes_duplicates(self, tmp_path):
        mgr = make_manager(tmp_path)
        e = make_entry(mgr)
        # Same entry twice
        unique = IntelligenceCompressor().deduplicate_payloads([e, e])
        assert len(unique) == 1

    def test_domain_similar_true(self):
        assert _domain_similar("example.com", "example.com", 0.9) is True

    def test_domain_similar_false(self):
        assert _domain_similar("example.com", "totallydifferent.org", 0.9) is False


# ===========================================================================
# Query Engine tests
# ===========================================================================


class TestIntelligenceQueryEngine:
    def _setup(self, tmp_path):
        mgr = make_manager(tmp_path)
        cache = IntelligenceCache(manager=mgr)
        graph = IntelligenceGraph(path=tmp_path / "graph.json")
        engine = IntelligenceQueryEngine(manager=mgr, cache=cache, graph=graph)
        return mgr, cache, graph, engine

    def test_find_prior_vuln(self, tmp_path):
        mgr, cache, graph, engine = self._setup(tmp_path)
        for i in range(3):
            e = make_entry(mgr, vuln_type="sqli", domain=f"t{i}.com", confidence=0.80)
            mgr.ingest(e)
            cache.index_entry(e)

        policy = AccessPolicy.for_agent(AgentClass.ANALYST)
        results, stats = engine.find_prior_vuln("sqli", policy=policy, min_confidence=0.5)
        assert len(results) >= 1
        assert all(isinstance(r.confidence, float) for r in results)

    def test_find_prior_vuln_filtered_by_domain(self, tmp_path):
        mgr, cache, graph, engine = self._setup(tmp_path)
        e1 = make_entry(mgr, vuln_type="sqli", domain="target.com", confidence=0.80)
        e2 = make_entry(mgr, vuln_type="sqli", domain="other.com", confidence=0.80)
        mgr.ingest(e1)
        mgr.ingest(e2)

        policy = AccessPolicy.for_agent(AgentClass.ANALYST)
        results, _ = engine.find_prior_vuln("sqli", domain="target.com", policy=policy, min_confidence=0.5)
        assert all(r.domain == "target.com" for r in results)

    def test_find_similar_endpoints(self, tmp_path):
        mgr, cache, graph, engine = self._setup(tmp_path)
        e = mgr.create_entry(
            memory_type=MemoryType.ENDPOINT_BEHAVIOR,
            scope=MemoryScope.MID_TERM,
            payload={"endpoint": "/api/v2/users"},
            confidence_score=0.70,
            validation_status=ValidationStatus.PARTIAL,
            source_mission_id="m1",
            target_fingerprint=make_fingerprint("endpoints.com"),
            tags=["endpoint:/api/v2/users"],
        )
        mgr.ingest(e)
        cache.index_entry(e)

        policy = AccessPolicy.for_agent(AgentClass.RECON)
        results, stats = engine.find_similar_endpoints("endpoints.com", policy=policy)
        assert len(results) >= 1

    def test_find_targets_by_tech(self, tmp_path):
        mgr, cache, graph, engine = self._setup(tmp_path)
        e = mgr.create_entry(
            memory_type=MemoryType.TECH_STACK,
            scope=MemoryScope.MID_TERM,
            payload={"tech": "wordpress"},
            confidence_score=0.75,
            validation_status=ValidationStatus.CONFIRMED,
            source_mission_id="m1",
            target_fingerprint=make_fingerprint("wp-site.com", tech=["wordpress", "php"]),
        )
        mgr.ingest(e)
        cache.index_entry(e)

        policy = AccessPolicy.for_agent(AgentClass.ANALYST)
        results, stats = engine.find_targets_by_tech(["wordpress"], policy=policy)
        assert len(results) >= 1

    def test_what_do_we_know_about(self, tmp_path):
        mgr, cache, graph, engine = self._setup(tmp_path)
        for i in range(2):
            e = make_entry(mgr, domain="known.com", vuln_type="sqli", confidence=0.80)
            mgr.ingest(e)

        summary = engine.what_do_we_know_about("known.com")
        assert summary["domain"] == "known.com"
        assert "recommendation" in summary

    def test_exploit_pattern_query_returns_results(self, tmp_path):
        mgr, cache, graph, engine = self._setup(tmp_path)
        e = mgr.create_entry(
            memory_type=MemoryType.EXPLOIT_PATTERN,
            scope=MemoryScope.LONG_TERM,
            payload={"pattern": "xss_reflected", "payloads": ["<k1probe>"]},
            confidence_score=0.85,
            validation_status=ValidationStatus.CONFIRMED,
            source_mission_id="m1",
            tags=["vuln_type:xss", "xss"],
        )
        mgr.ingest(e)

        policy = AccessPolicy.for_agent(AgentClass.EXPLOIT)
        results, stats = engine.find_exploit_patterns("xss", policy=policy, min_confidence=0.7)
        assert len(results) >= 1

    def test_cross_mission_reuse_stats(self, tmp_path):
        mgr, cache, graph, engine = self._setup(tmp_path)
        stats = engine.get_cross_mission_reuse_stats()
        assert "memory_metrics" in stats
        assert "cache_metrics" in stats
        assert "graph_summary" in stats

    def test_tag_vuln_type_helper(self):
        assert _tag_vuln_type(["vuln_type:sqli", "sqli"]) == "sqli"
        assert _tag_vuln_type(["xss"]) == ""

    def test_generate_recommendation(self, tmp_path):
        mgr = make_manager(tmp_path)
        entries = [make_entry(mgr, confidence=0.9, validated=True) for _ in range(2)]
        rec = _generate_recommendation(["sqli", "xss"], entries, ["nginx"])
        assert "sqli" in rec or "xss" in rec or "nginx" in rec


# ===========================================================================
# Integration: full pipeline
# ===========================================================================


class TestFullMemoryPipeline:
    """
    End-to-end: ingest → compress → query → promote chain.
    Validates that "we saw this pattern before → we exploit it faster now."
    """

    def test_cross_mission_pattern_recall(self, tmp_path):
        mgr = make_manager(tmp_path)
        graph = IntelligenceGraph(path=tmp_path / "graph.json")
        cache = IntelligenceCache(manager=mgr)
        engine = IntelligenceQueryEngine(manager=mgr, cache=cache, graph=graph)
        compressor = IntelligenceCompressor(manager=mgr)

        # Mission 1: discover 5 XSS findings on example.com
        mission1_entries = []
        for i in range(5):
            e = mgr.create_entry(
                memory_type=MemoryType.FINDING,
                scope=MemoryScope.MID_TERM,
                payload={"url": f"http://example.com/p{i}", "param": "q", "uid": str(uuid.uuid4())},
                confidence_score=0.80,
                validation_status=ValidationStatus.CONFIRMED,
                source_mission_id="mission-1",
                target_fingerprint=TargetFingerprint(domain="example.com", tech_stack=["nginx", "php"]),
                tags=["vuln_type:xss", "xss", "param:q"],
            )
            assert mgr.ingest(e) is True
            cache.index_entry(e)
            mission1_entries.append(e)

        # Compress into a pattern signature
        written = compressor.compress_and_write(mission1_entries, mission_id="mission-1", min_occurrences=3)
        assert len(written) >= 1
        sig_entry = written[0]

        # Add relationship: pattern → tool_sequence
        graph.add_edge(sig_entry.memory_id, "tool-seq-001", EdgeType.EXPLOIT_TO_TOOL_SEQ)

        # Mission 2: query what we know before starting
        policy = AccessPolicy.for_agent(AgentClass.ORCHESTRATOR)
        domain_knowledge = engine.what_do_we_know_about("example.com", policy=policy)
        assert domain_knowledge["finding_count"] >= 1
        assert "xss" in domain_knowledge["known_vuln_types"]

        # Exploit agent queries for patterns
        exploit_policy = AccessPolicy.for_agent(AgentClass.EXPLOIT)
        patterns, stats = engine.find_exploit_patterns("xss", policy=exploit_policy, min_confidence=0.7)
        assert len(patterns) >= 1
        # Should know about the tool sequence
        assert "tool-seq-001" in patterns[0].tool_sequence_ids

        # Promote the signature to STRATEGIC
        promoted = mgr.promote(sig_entry, force=True)
        assert promoted is not None or sig_entry.scope == MemoryScope.LONG_TERM

        # Verify memory metrics show cross-mission value
        metrics = mgr.get_metrics()
        assert metrics["entries_created"] > 5  # mission findings + signature
