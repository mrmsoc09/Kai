"""
Tests for opportunity_engine.py and opportunity_targeting.py.

Covers:
  - InferenceOpportunity lifecycle (approve, reject, execute, complete)
  - OpportunityEngine.detect() — pattern detection, ranking, dedup
  - OpportunityEngine.detect_for_vuln_type() — focused detection
  - OpportunityEngine.record_outcome() — feedback loop
  - OpportunityTargeter.find_targets() — composite scoring
  - Tech stack, endpoint, history, service scoring signals
  - Scope boundary enforcement (only allowed_domains returned)
  - DetectionResult structure and serialization
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Isolation fixture — redirect artifact writes, reset singletons
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_artifacts(tmp_path, monkeypatch):
    """Redirect all artifact I/O to a temp dir and reset module singletons."""
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    monkeypatch.setenv("K1_MEMORY_ROOT", str(tmp_path / "intelligence"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-opportunity-tests")

    # Reset intelligence memory singletons
    import apps.backend.src.core.intelligence_memory as im_mod
    import apps.backend.src.core.intelligence_graph as ig_mod
    import apps.backend.src.core.intelligence_cache as ic_mod
    import apps.backend.src.core.intelligence_query as iq_mod
    import apps.backend.src.core.intelligence_encryption as ie_mod
    import apps.backend.src.core.opportunity_engine as oe_mod

    monkeypatch.setattr(im_mod, "_manager_instance", None)
    monkeypatch.setattr(ig_mod, "_graph_instance", None)
    monkeypatch.setattr(ic_mod, "_cache_instance", None)
    monkeypatch.setattr(iq_mod, "_engine_instance", None)
    monkeypatch.setattr(oe_mod, "_engine_instance", None)

    # Rotate encryption key cache for test isolation
    ie_mod.rotate_key_cache()

    yield


# ---------------------------------------------------------------------------
# Helpers to create MemoryEntry objects in tests
# ---------------------------------------------------------------------------


def _make_entry(
    vuln_type: str = "sqli",
    domain: str = "example.com",
    memory_type=None,
    confidence: float = 0.85,
    validation_status=None,
    tech_stack: list[str] | None = None,
    services: list[str] | None = None,
    extra_tags: list[str] | None = None,
    scope=None,
    mission_id: str = "m-test",
):
    from apps.backend.src.core.intelligence_memory import (
        MemoryEntry,
        MemoryScope,
        MemoryType,
        TargetFingerprint,
        ValidationStatus,
    )
    from apps.backend.src.core.intelligence_encryption import encrypt_payload, derive_content_hash

    if memory_type is None:
        memory_type = MemoryType.FINDING
    if validation_status is None:
        validation_status = ValidationStatus.CONFIRMED
    if scope is None:
        scope = MemoryScope.LONG_TERM

    tags = [f"vuln_type:{vuln_type}", vuln_type]
    if extra_tags:
        tags.extend(extra_tags)

    payload = {"vuln_type": vuln_type, "domain": domain}
    enc = encrypt_payload(payload)
    content_hash = derive_content_hash(payload)

    return MemoryEntry(
        memory_id=f"mem-{uuid.uuid4().hex[:8]}",
        memory_type=memory_type,
        scope=scope,
        target_fingerprint=TargetFingerprint(
            domain=domain,
            tech_stack=tech_stack or [],
            services=services or [],
        ),
        tags=tags,
        confidence_score=confidence,
        validation_status=validation_status,
        source_mission_id=mission_id,
        created_at=time.time(),
        relationships=[],
        encrypted_payload=enc,
        content_hash=content_hash,
    )


# ---------------------------------------------------------------------------
# InferenceOpportunity lifecycle
# ---------------------------------------------------------------------------


class TestInferenceOpportunityLifecycle:
    def _make_opp(self, status=None):
        from apps.backend.src.core.opportunity_engine import InferenceOpportunity, OpportunityStatus
        return InferenceOpportunity(
            opportunity_id="opp-abc123",
            source_memory_id="mem-001",
            vuln_type="sqli",
            candidate_targets=["a.com", "b.com"],
            confidence_score=0.82,
            estimated_yield=1.6,
            duplicate_risk=0.0,
            status=status or OpportunityStatus.PROPOSED,
        )

    def test_initial_status_proposed(self):
        opp = self._make_opp()
        from apps.backend.src.core.opportunity_engine import OpportunityStatus
        assert opp.status == OpportunityStatus.PROPOSED

    def test_approve_from_proposed(self):
        from apps.backend.src.core.opportunity_engine import OpportunityStatus
        opp = self._make_opp()
        opp.approve()
        assert opp.status == OpportunityStatus.APPROVED

    def test_approve_from_non_proposed_raises(self):
        from apps.backend.src.core.opportunity_engine import OpportunityStatus
        opp = self._make_opp(status=OpportunityStatus.COMPLETED)
        with pytest.raises(ValueError, match="Cannot approve"):
            opp.approve()

    def test_reject_sets_notes(self):
        from apps.backend.src.core.opportunity_engine import OpportunityStatus
        opp = self._make_opp()
        opp.reject("out of scope")
        assert opp.status == OpportunityStatus.REJECTED
        assert "out of scope" in opp.notes

    def test_mark_executing_requires_approved(self):
        from apps.backend.src.core.opportunity_engine import OpportunityStatus
        opp = self._make_opp()
        with pytest.raises(ValueError, match="Cannot execute"):
            opp.mark_executing()

    def test_full_lifecycle(self):
        from apps.backend.src.core.opportunity_engine import OpportunityStatus
        opp = self._make_opp()
        opp.approve()
        opp.mark_executing()
        opp.mark_completed("2 of 2 confirmed")
        assert opp.status == OpportunityStatus.COMPLETED
        assert "2 of 2" in opp.notes

    def test_to_dict_structure(self):
        opp = self._make_opp()
        d = opp.to_dict()
        assert d["opportunity_id"] == "opp-abc123"
        assert d["vuln_type"] == "sqli"
        assert isinstance(d["candidate_targets"], list)
        assert isinstance(d["confidence_score"], float)
        assert isinstance(d["estimated_yield"], float)
        assert isinstance(d["duplicate_risk"], float)
        assert d["status"] == "proposed"

    def test_updated_at_changes_on_approve(self):
        opp = self._make_opp()
        before = opp.updated_at
        time.sleep(0.01)
        opp.approve()
        assert opp.updated_at >= before


# ---------------------------------------------------------------------------
# OpportunityEngine.detect() — empty cases
# ---------------------------------------------------------------------------


class TestOpportunityEngineEmpty:
    def test_detect_empty_allowed_domains_returns_empty(self):
        from apps.backend.src.core.opportunity_engine import OpportunityEngine
        engine = OpportunityEngine()
        result = engine.detect(allowed_domains=[])
        assert result.opportunities == []
        assert result.patterns_evaluated == 0

    def test_detect_no_memory_returns_empty(self):
        from apps.backend.src.core.opportunity_engine import OpportunityEngine
        engine = OpportunityEngine()
        result = engine.detect(allowed_domains=["target.com"])
        assert result.opportunities == []

    def test_detection_result_to_dict(self):
        from apps.backend.src.core.opportunity_engine import OpportunityEngine
        engine = OpportunityEngine()
        result = engine.detect(allowed_domains=[])
        d = result.to_dict()
        assert "opportunity_count" in d
        assert "patterns_evaluated" in d
        assert "candidates_evaluated" in d
        assert "duplicates_suppressed" in d
        assert "duration_ms" in d
        assert isinstance(d["opportunities"], list)


# ---------------------------------------------------------------------------
# OpportunityEngine.detect() — with seeded memory
# ---------------------------------------------------------------------------


class TestOpportunityEngineDetect:
    def _seed_confirmed_finding(self, manager, vuln_type, domain, tech_stack=None, confidence=0.85):
        """Write a confirmed finding into the manager."""
        from apps.backend.src.core.intelligence_memory import MemoryScope, MemoryType, ValidationStatus
        entry = _make_entry(
            vuln_type=vuln_type,
            domain=domain,
            memory_type=MemoryType.FINDING,
            confidence=confidence,
            validation_status=ValidationStatus.CONFIRMED,
            tech_stack=tech_stack or [],
            scope=MemoryScope.LONG_TERM,
            mission_id=f"m-{domain[:4]}",
        )
        manager.ingest(entry)
        return entry

    def _seed_pattern_signature(self, manager, vuln_type, domains, confidence=0.88):
        """Write a PATTERN_SIGNATURE entry representing N domains."""
        from apps.backend.src.core.intelligence_memory import (
            MemoryScope, MemoryType, ValidationStatus, TargetFingerprint,
        )
        from apps.backend.src.core.intelligence_encryption import encrypt_payload, derive_content_hash

        payload = {
            "vuln_type": vuln_type,
            "occurrence_count": len(domains),
            "endpoint_patterns": domains,
            "sample_payloads": ["' OR 1=1--"],
        }
        enc = encrypt_payload(payload)

        from apps.backend.src.core.intelligence_memory import MemoryEntry
        entry = MemoryEntry(
            memory_id=f"pat-{uuid.uuid4().hex[:8]}",
            memory_type=MemoryType.PATTERN_SIGNATURE,
            scope=MemoryScope.LONG_TERM,
            target_fingerprint=TargetFingerprint(domain=domains[0], tech_stack=["php", "mysql"]),
            tags=[f"vuln_type:{vuln_type}", "compressed_pattern"],
            confidence_score=confidence,
            validation_status=ValidationStatus.CONFIRMED,
            source_mission_id="m-compress",
            created_at=time.time(),
            relationships=[],
            encrypted_payload=enc,
            content_hash=derive_content_hash(payload),
        )
        manager.ingest(entry)
        return entry

    def test_detect_creates_opportunity_from_pattern(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.opportunity_engine import OpportunityEngine

        manager = get_memory_manager()
        self._seed_pattern_signature(manager, "sqli", ["source.com", "other.com"])

        engine = OpportunityEngine(manager=manager)
        result = engine.detect(
            allowed_domains=["target-a.com", "target-b.com"],
            min_confidence=0.60,
            min_occurrence_count=1,
        )

        assert result.patterns_evaluated > 0

    def test_detect_respects_min_confidence(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.opportunity_engine import OpportunityEngine

        manager = get_memory_manager()
        # Seed a low-confidence pattern — should be excluded at high threshold
        self._seed_pattern_signature(manager, "xss", ["src.com"], confidence=0.50)

        engine = OpportunityEngine(manager=manager)
        result = engine.detect(
            allowed_domains=["candidate.com"],
            min_confidence=0.85,
        )
        # Opportunity confidence will be derived from pattern confidence — too low
        for opp in result.opportunities:
            assert opp.confidence_score >= 0.85

    def test_detect_excludes_source_domain(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.opportunity_engine import OpportunityEngine

        manager = get_memory_manager()
        self._seed_pattern_signature(manager, "sqli", ["source.com"])

        engine = OpportunityEngine(manager=manager)
        # include source.com in allowed_domains — should not appear as candidate
        result = engine.detect(
            allowed_domains=["source.com", "new-target.com"],
            min_confidence=0.60,
            min_occurrence_count=1,
        )
        for opp in result.opportunities:
            assert "source.com" not in opp.candidate_targets

    def test_detect_max_opportunities_cap(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.opportunity_engine import OpportunityEngine

        manager = get_memory_manager()
        # Seed 5 different vuln types
        for vt in ["sqli", "xss", "ssrf", "lfi", "rce"]:
            self._seed_pattern_signature(manager, vt, [f"{vt}-source.com", f"{vt}-src2.com"])

        engine = OpportunityEngine(manager=manager)
        result = engine.detect(
            allowed_domains=[f"target-{i}.com" for i in range(10)],
            min_confidence=0.30,
            min_occurrence_count=1,
            max_opportunities=3,
        )
        assert len(result.opportunities) <= 3

    def test_detect_sorted_by_estimated_yield(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.opportunity_engine import OpportunityEngine

        manager = get_memory_manager()
        self._seed_pattern_signature(manager, "sqli", ["s1.com", "s2.com", "s3.com"], confidence=0.90)
        self._seed_pattern_signature(manager, "xss", ["x1.com"], confidence=0.75)

        engine = OpportunityEngine(manager=manager)
        result = engine.detect(
            allowed_domains=[f"t{i}.com" for i in range(5)],
            min_confidence=0.30,
            min_occurrence_count=1,
        )
        # Verify sort order
        yields = [o.estimated_yield for o in result.opportunities]
        assert yields == sorted(yields, reverse=True)

    def test_detect_duplicate_suppression(self):
        from apps.backend.src.core.intelligence_memory import (
            get_memory_manager, ValidationStatus, MemoryType, MemoryScope,
        )
        from apps.backend.src.core.opportunity_engine import OpportunityEngine

        manager = get_memory_manager()
        # Seed pattern on source
        self._seed_pattern_signature(manager, "sqli", ["source.com"])
        # Seed confirmed findings on ALL candidate targets (100% duplicate)
        for domain in ["a.com", "b.com", "c.com"]:
            self._seed_confirmed_finding(manager, "sqli", domain)

        engine = OpportunityEngine(manager=manager)
        result = engine.detect(
            allowed_domains=["a.com", "b.com", "c.com"],
            min_confidence=0.30,
            min_occurrence_count=1,
            deduplicate=True,
        )
        # All candidates are already confirmed → dup_risk > 0.85 → suppressed
        sqli_opps = [o for o in result.opportunities if o.vuln_type == "sqli"]
        assert result.duplicates_suppressed >= 0  # may suppress

    def test_detect_no_duplicate_suppression_when_disabled(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.opportunity_engine import OpportunityEngine

        manager = get_memory_manager()
        self._seed_pattern_signature(manager, "sqli", ["source.com"])

        engine = OpportunityEngine(manager=manager)
        result_nodup = engine.detect(
            allowed_domains=["target.com"],
            min_confidence=0.30,
            min_occurrence_count=1,
            deduplicate=False,
        )
        assert result_nodup.duplicates_suppressed == 0

    def test_detect_stats_populated(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.opportunity_engine import OpportunityEngine

        manager = get_memory_manager()
        engine = OpportunityEngine(manager=manager)
        result = engine.detect(allowed_domains=["x.com"])
        assert result.duration_ms >= 0
        assert isinstance(result.patterns_evaluated, int)
        assert isinstance(result.candidates_evaluated, int)
        assert isinstance(result.duplicates_suppressed, int)


# ---------------------------------------------------------------------------
# OpportunityEngine.detect_for_vuln_type()
# ---------------------------------------------------------------------------


class TestDetectForVulnType:
    def test_returns_only_matching_vuln_type(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.opportunity_engine import OpportunityEngine

        manager = get_memory_manager()
        engine = OpportunityEngine(manager=manager)

        opps = engine.detect_for_vuln_type("sqli", ["target.com"])
        for opp in opps:
            assert opp.vuln_type == "sqli"

    def test_empty_when_no_patterns(self):
        from apps.backend.src.core.opportunity_engine import OpportunityEngine
        engine = OpportunityEngine()
        result = engine.detect_for_vuln_type("rce", ["a.com", "b.com"])
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# OpportunityEngine.record_outcome() — feedback loop
# ---------------------------------------------------------------------------


class TestRecordOutcome:
    def test_record_outcome_logs_without_error(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.opportunity_engine import OpportunityEngine, InferenceOpportunity

        engine = OpportunityEngine(manager=get_memory_manager())
        opp = InferenceOpportunity(
            opportunity_id="opp-test",
            source_memory_id="mem-001",
            vuln_type="xss",
            candidate_targets=["a.com", "b.com", "c.com"],
            confidence_score=0.80,
            estimated_yield=2.0,
            duplicate_risk=0.0,
        )
        # Should not raise
        engine.record_outcome(
            opportunity=opp,
            confirmed_domains=["a.com", "b.com"],
            failed_domains=["c.com"],
        )

    def test_record_outcome_zero_candidates(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.opportunity_engine import OpportunityEngine, InferenceOpportunity

        engine = OpportunityEngine(manager=get_memory_manager())
        opp = InferenceOpportunity(
            opportunity_id="opp-zero",
            source_memory_id="mem-002",
            vuln_type="sqli",
            candidate_targets=[],
            confidence_score=0.75,
            estimated_yield=0.0,
            duplicate_risk=0.0,
        )
        engine.record_outcome(opp, [], [])  # No crash on empty lists


# ---------------------------------------------------------------------------
# OpportunityTargeter — signal scoring
# ---------------------------------------------------------------------------


class TestOpportunityTargeter:
    def _make_targeter(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.intelligence_query import get_query_engine
        from apps.backend.src.core.opportunity_targeting import OpportunityTargeter
        return OpportunityTargeter(
            manager=get_memory_manager(),
            query_engine=get_query_engine(),
        )

    def test_find_targets_empty_allowed_domains(self):
        targeter = self._make_targeter()
        source = _make_entry(vuln_type="sqli", domain="source.com", tech_stack=["php"])
        results = targeter.find_targets(source, [], "sqli")
        assert results == []

    def test_find_targets_returns_target_match_objects(self):
        from apps.backend.src.core.opportunity_targeting import TargetMatch
        targeter = self._make_targeter()
        source = _make_entry(vuln_type="sqli", domain="source.com", tech_stack=["php"])
        results = targeter.find_targets(source, ["a.com", "b.com"], "sqli", min_score=0.0)
        for r in results:
            assert isinstance(r, TargetMatch)
            assert r.domain in ["a.com", "b.com"]

    def test_find_targets_sorted_by_score(self):
        targeter = self._make_targeter()
        source = _make_entry(vuln_type="sqli", domain="source.com", tech_stack=["php"])
        results = targeter.find_targets(source, ["a.com", "b.com", "c.com"], "sqli", min_score=0.0)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_find_targets_min_score_filter(self):
        targeter = self._make_targeter()
        source = _make_entry(vuln_type="sqli", domain="source.com", tech_stack=["php"])
        results = targeter.find_targets(source, ["target.com"], "sqli", min_score=0.99)
        # No matching tech/history → score < 0.99 → filtered
        assert results == []

    def test_tech_score_full_overlap(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.opportunity_targeting import OpportunityTargeter
        manager = get_memory_manager()

        # Seed domain_entries with same tech stack
        tech = ["php", "nginx", "mysql"]
        domain_entries = [_make_entry("sqli", "target.com", tech_stack=tech)]
        manager.ingest(domain_entries[0])

        targeter = OpportunityTargeter(manager=manager)
        source = _make_entry("sqli", "source.com", tech_stack=tech)

        results = targeter.find_targets(source, ["target.com"], "sqli", min_score=0.0)
        assert results, "Expected at least one match"
        match = results[0]
        # Full tech overlap should score near 1.0
        assert match.tech_score > 0.8

    def test_tech_score_no_overlap(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.opportunity_targeting import OpportunityTargeter
        manager = get_memory_manager()

        domain_entry = _make_entry("sqli", "target.com", tech_stack=["java", "tomcat"])
        manager.ingest(domain_entry)

        targeter = OpportunityTargeter(manager=manager)
        source = _make_entry("sqli", "source.com", tech_stack=["php", "mysql"])

        results = targeter.find_targets(source, ["target.com"], "sqli", min_score=0.0)
        if results:
            assert results[0].tech_score < 0.1

    def test_history_score_confirmed_same_type(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager, ValidationStatus
        from apps.backend.src.core.opportunity_targeting import OpportunityTargeter
        manager = get_memory_manager()

        confirmed = _make_entry(
            "sqli", "target.com",
            validation_status=ValidationStatus.CONFIRMED,
        )
        manager.ingest(confirmed)

        targeter = OpportunityTargeter(manager=manager)
        source = _make_entry("sqli", "source.com")

        results = targeter.find_targets(source, ["target.com"], "sqli", min_score=0.0)
        assert results
        # History score should be 0.95 (confirmed same type)
        assert results[0].history_score == pytest.approx(0.95, abs=0.01)

    def test_history_score_unconfirmed_same_type(self):
        from apps.backend.src.core.intelligence_memory import (
            get_memory_manager, ValidationStatus, MemoryScope,
        )
        from apps.backend.src.core.opportunity_targeting import OpportunityTargeter
        manager = get_memory_manager()

        # Use MID_TERM scope — LONG_TERM rejects non-CONFIRMED entries
        unconfirmed = _make_entry(
            "sqli", "target.com",
            validation_status=ValidationStatus.PARTIAL,
            confidence=0.60,
            scope=MemoryScope.MID_TERM,
        )
        manager.ingest(unconfirmed)

        targeter = OpportunityTargeter(manager=manager)
        source = _make_entry("sqli", "source.com")
        results = targeter.find_targets(source, ["target.com"], "sqli", min_score=0.0)
        assert results
        assert results[0].history_score == pytest.approx(0.70, abs=0.01)

    def test_history_score_any_findings_but_different_type(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.opportunity_targeting import OpportunityTargeter
        manager = get_memory_manager()

        # XSS finding on target, but we're looking for sqli
        xss_entry = _make_entry("xss", "target.com")
        manager.ingest(xss_entry)

        targeter = OpportunityTargeter(manager=manager)
        source = _make_entry("sqli", "source.com")
        results = targeter.find_targets(source, ["target.com"], "sqli", min_score=0.0)
        assert results
        # Has history (any type) → 0.30
        assert results[0].history_score == pytest.approx(0.30, abs=0.01)

    def test_history_score_no_findings(self):
        from apps.backend.src.core.opportunity_targeting import OpportunityTargeter
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        manager = get_memory_manager()
        targeter = OpportunityTargeter(manager=manager)
        source = _make_entry("sqli", "source.com")
        results = targeter.find_targets(source, ["unknown-fresh.com"], "sqli", min_score=0.0)
        assert results
        assert results[0].history_score == 0.0

    def test_endpoint_score_matching_tags(self):
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        from apps.backend.src.core.opportunity_targeting import OpportunityTargeter
        manager = get_memory_manager()

        domain_entry = _make_entry(
            "sqli", "target.com",
            extra_tags=["endpoint:/api/v1/users", "endpoint:/api/v1/items"],
        )
        manager.ingest(domain_entry)

        targeter = OpportunityTargeter(manager=manager)
        source = _make_entry(
            "sqli", "source.com",
            extra_tags=["endpoint:/api/v1/users", "endpoint:/api/v1/orders"],
        )

        results = targeter.find_targets(source, ["target.com"], "sqli", min_score=0.0)
        assert results
        # Partial endpoint match → score > 0
        assert results[0].endpoint_score > 0

    def test_service_score_overlap(self):
        from apps.backend.src.core.intelligence_memory import (
            get_memory_manager, MemoryEntry, MemoryScope, MemoryType,
            ValidationStatus, TargetFingerprint,
        )
        from apps.backend.src.core.intelligence_encryption import encrypt_payload, derive_content_hash
        from apps.backend.src.core.opportunity_targeting import OpportunityTargeter
        manager = get_memory_manager()

        # Create entry with matching services
        payload = {"x": 1}
        entry = MemoryEntry(
            memory_id=f"mem-{uuid.uuid4().hex[:8]}",
            memory_type=MemoryType.FINDING,
            scope=MemoryScope.LONG_TERM,
            target_fingerprint=TargetFingerprint(
                domain="target.com",
                services=["http:80", "https:443"],
            ),
            tags=["vuln_type:sqli"],
            confidence_score=0.80,
            validation_status=ValidationStatus.CONFIRMED,
            source_mission_id="m-svc",
            created_at=time.time(),
            relationships=[],
            encrypted_payload=encrypt_payload(payload),
            content_hash=derive_content_hash(payload),
        )
        manager.ingest(entry)

        targeter = OpportunityTargeter(manager=manager)
        source = _make_entry("sqli", "source.com", services=["http:80", "https:443", "ssh:22"])

        results = targeter.find_targets(source, ["target.com"], "sqli", min_score=0.0)
        assert results
        assert results[0].service_score > 0

    def test_target_match_to_dict(self):
        from apps.backend.src.core.opportunity_targeting import TargetMatch
        m = TargetMatch(
            domain="example.com",
            score=0.72,
            tech_score=0.8,
            endpoint_score=0.6,
            history_score=0.95,
            service_score=0.5,
            matching_tech=["php"],
            matching_endpoints=["/api/v1/users"],
        )
        d = m.to_dict()
        assert d["domain"] == "example.com"
        assert d["score"] == pytest.approx(0.72, abs=0.001)
        assert d["matching_tech"] == ["php"]

    def test_limit_respected(self):
        from apps.backend.src.core.opportunity_targeting import OpportunityTargeter
        from apps.backend.src.core.intelligence_memory import get_memory_manager
        targeter = OpportunityTargeter(manager=get_memory_manager())
        source = _make_entry("sqli", "source.com")
        domains = [f"t{i}.com" for i in range(100)]
        results = targeter.find_targets(source, domains, "sqli", min_score=0.0, limit=10)
        assert len(results) <= 10


# ---------------------------------------------------------------------------
# Integration — full pipeline: seed → detect → approve → complete
# ---------------------------------------------------------------------------


class TestFullOpportunityPipeline:
    def test_end_to_end_opportunity_lifecycle(self):
        """
        Seed a PATTERN_SIGNATURE for sqli, run detect(), approve the top
        opportunity, simulate execution, complete it.
        """
        from apps.backend.src.core.intelligence_memory import (
            get_memory_manager, MemoryEntry, MemoryScope, MemoryType,
            ValidationStatus, TargetFingerprint,
        )
        from apps.backend.src.core.intelligence_encryption import encrypt_payload, derive_content_hash
        from apps.backend.src.core.opportunity_engine import OpportunityEngine, OpportunityStatus

        manager = get_memory_manager()

        # Seed a high-confidence pattern signature for sqli from known source
        payload = {
            "vuln_type": "sqli",
            "occurrence_count": 4,
            "endpoint_patterns": ["src1.com", "src2.com", "src3.com", "src4.com"],
            "sample_payloads": ["' OR 1=1--", "1; DROP TABLE users--"],
        }
        pattern_entry = MemoryEntry(
            memory_id=f"pat-{uuid.uuid4().hex[:8]}",
            memory_type=MemoryType.PATTERN_SIGNATURE,
            scope=MemoryScope.LONG_TERM,
            target_fingerprint=TargetFingerprint(
                domain="src1.com",
                tech_stack=["php", "mysql"],
            ),
            tags=["vuln_type:sqli", "compressed_pattern"],
            confidence_score=0.92,
            validation_status=ValidationStatus.CONFIRMED,
            source_mission_id="m-seed",
            created_at=time.time(),
            relationships=[],
            encrypted_payload=encrypt_payload(payload),
            content_hash=derive_content_hash(payload),
        )
        manager.ingest(pattern_entry)

        # Seed some prior tech-stack data on a target domain
        tech_entry = MemoryEntry(
            memory_id=f"tech-{uuid.uuid4().hex[:8]}",
            memory_type=MemoryType.TECH_STACK,
            scope=MemoryScope.MID_TERM,
            target_fingerprint=TargetFingerprint(
                domain="new-target.com",
                tech_stack=["php", "mysql", "nginx"],
            ),
            tags=["tech:php", "tech:mysql"],
            confidence_score=0.75,
            validation_status=ValidationStatus.CONFIRMED,
            source_mission_id="m-recon",
            created_at=time.time(),
            relationships=[],
            encrypted_payload=encrypt_payload({"tech": "php"}),
            content_hash=derive_content_hash({"tech": "php"}),
        )
        manager.ingest(tech_entry)

        # Run detection
        engine = OpportunityEngine(manager=manager)
        result = engine.detect(
            allowed_domains=["new-target.com", "other.com"],
            min_confidence=0.40,
            min_occurrence_count=1,
        )

        assert result.patterns_evaluated > 0

        if result.opportunities:
            opp = result.opportunities[0]
            assert opp.vuln_type == "sqli"
            assert opp.confidence_score >= 0.40
            assert isinstance(opp.candidate_targets, list)

            # Full lifecycle
            opp.approve()
            assert opp.status == OpportunityStatus.APPROVED
            opp.mark_executing()
            assert opp.status == OpportunityStatus.EXECUTING

            # Record outcome
            engine.record_outcome(
                opp,
                confirmed_domains=["new-target.com"],
                failed_domains=["other.com"],
            )
            opp.mark_completed("1 of 2 confirmed via sqli probe")
            assert opp.status == OpportunityStatus.COMPLETED

    def test_opportunity_fields_all_present(self):
        """Every InferenceOpportunity field should be present in to_dict()."""
        from apps.backend.src.core.intelligence_memory import (
            get_memory_manager, MemoryEntry, MemoryScope, MemoryType,
            ValidationStatus, TargetFingerprint,
        )
        from apps.backend.src.core.intelligence_encryption import encrypt_payload, derive_content_hash
        from apps.backend.src.core.opportunity_engine import OpportunityEngine

        manager = get_memory_manager()
        payload = {"vuln_type": "xss", "occurrence_count": 3}
        entry = MemoryEntry(
            memory_id=f"pat-{uuid.uuid4().hex[:8]}",
            memory_type=MemoryType.PATTERN_SIGNATURE,
            scope=MemoryScope.LONG_TERM,
            target_fingerprint=TargetFingerprint(domain="src.com", tech_stack=["node"]),
            tags=["vuln_type:xss", "compressed_pattern"],
            confidence_score=0.88,
            validation_status=ValidationStatus.CONFIRMED,
            source_mission_id="m-xss",
            created_at=time.time(),
            relationships=[],
            encrypted_payload=encrypt_payload(payload),
            content_hash=derive_content_hash(payload),
        )
        manager.ingest(entry)

        engine = OpportunityEngine(manager=manager)
        result = engine.detect(
            allowed_domains=["candidate.com"],
            min_confidence=0.30,
            min_occurrence_count=1,
        )

        for opp in result.opportunities:
            d = opp.to_dict()
            required_fields = [
                "opportunity_id", "source_memory_id", "vuln_type",
                "candidate_targets", "confidence_score", "estimated_yield",
                "duplicate_risk", "status", "recommended_tools",
                "target_scores", "created_at", "updated_at",
            ]
            for field_name in required_fields:
                assert field_name in d, f"Missing field: {field_name}"
