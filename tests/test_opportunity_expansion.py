from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from uuid import uuid4

from apps.backend.src.core.intelligence_encryption import derive_content_hash, encrypt_payload
from apps.backend.src.core.intelligence_memory import (
    MemoryEntry,
    MemoryScope,
    MemoryType,
    TargetFingerprint,
    ValidationStatus,
)
from apps.backend.src.core.opportunity_actions import OpportunityActionService
from apps.backend.src.core.opportunity_catalog import Opportunity
from apps.backend.src.core.opportunity_expansion import (
    ExpansionCandidate,
    ExpansionSource,
    OpportunityExpansionEngine,
    OpportunityExpansionResult,
    TargetBatch,
)
from apps.backend.src.core.scope_guardrails import ScopePolicy
from apps.backend.src.core.target_similarity_engine import SimilaritySource, TargetSimilarityEngine


@dataclass
class _FakeMissionHandle:
    mission_id: str


class _FakeRuntime:
    def __init__(self) -> None:
        self._created: list[str] = []

    def create_mission(self, **kwargs):
        mission_id = f"mission-{len(self._created) + 1}"
        self._created.append(mission_id)
        return _FakeMissionHandle(mission_id=mission_id)

    def start_mission(self, mission_id, tenant_id):
        del mission_id, tenant_id
        return None

    def get_status(self, mission_id, tenant_id):
        del mission_id, tenant_id

        class _Status:
            state = "completed"

        return _Status()

    def get_state(self, mission_id):
        del mission_id
        return {"findings": [], "validated_findings": []}


def _entry(*, domain: str, vuln_type: str, tech: list[str], services: list[str], tags: list[str] | None = None) -> MemoryEntry:
    payload = {"domain": domain, "vuln_type": vuln_type}
    entry_tags = [f"vuln_type:{vuln_type}", vuln_type, "endpoint:/api/login", "header:server:nginx"]
    if tags:
        entry_tags.extend(tags)
    return MemoryEntry(
        memory_id=f"mem-{uuid.uuid4().hex[:10]}",
        memory_type=MemoryType.FINDING,
        scope=MemoryScope.LONG_TERM,
        target_fingerprint=TargetFingerprint(domain=domain, tech_stack=tech, services=services),
        tags=entry_tags,
        confidence_score=0.86,
        validation_status=ValidationStatus.CONFIRMED,
        source_mission_id="mission-expansion",
        created_at=time.time(),
        relationships=[],
        encrypted_payload=encrypt_payload(payload),
        content_hash=derive_content_hash(payload),
    )


def _sample_opportunity(scope_domains: list[str]) -> Opportunity:
    return Opportunity(
        id="hackerone:expansion_program",
        name="Expansion Program",
        organization="Expansion Org",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://example.com/program",
        scope_url="https://example.com/scope",
        scope_summary="expansion scope",
        scope_domains=scope_domains,
        max_payout_usd=25000,
        min_payout_usd=250,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api"],
        vuln_types=["xss"],
        priority_score=0.84,
        notes="",
    )


def test_target_similarity_engine_ranks_closest_target(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_MEMORY_ROOT", str(tmp_path / "memory"))
    monkeypatch.setenv("K1_REPORT_ENGINE_STATE_PATH", str(tmp_path / "reports.json"))
    monkeypatch.setenv("K1_REPORT_ENGINE_ARTIFACT_DIR", str(tmp_path / "reports"))
    import apps.backend.src.core.intelligence_memory as memory_mod
    import apps.backend.src.core.intelligence_query as query_mod
    import apps.backend.src.core.report_engine as report_mod

    memory_mod._manager_instance = None
    query_mod._engine_instance = None
    report_mod._engine_instance = None

    manager = memory_mod.get_memory_manager()
    manager.ingest(_entry(domain="api.source.example.com", vuln_type="xss", tech=["react", "nginx"], services=["https"]))
    manager.ingest(_entry(domain="api-a.example.com", vuln_type="xss", tech=["react", "nginx"], services=["https"], tags=["endpoint:/api/login"]))
    manager.ingest(_entry(domain="api-b.example.com", vuln_type="xss", tech=["php"], services=["http"], tags=["endpoint:/legacy"]))

    engine = TargetSimilarityEngine(manager=manager)
    ranked = engine.rank_targets(
        SimilaritySource(
            source_type="validated_finding",
            source_object_id="mem-source",
            vuln_type="xss",
            source_target="api.source.example.com",
            confidence=0.9,
            tech_stack=["react", "nginx"],
            endpoint_shapes=["/api/login"],
            pattern_tags=["xss"],
            service_fingerprints=["https"],
            headers=["server:nginx"],
        ),
        ["api-a.example.com", "api-b.example.com"],
    )

    assert ranked
    assert ranked[0].target == "api-a.example.com"
    assert ranked[0].similarity_score >= ranked[-1].similarity_score


def test_opportunity_expansion_generates_ranked_batches(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_MEMORY_ROOT", str(tmp_path / "memory"))
    monkeypatch.setenv("K1_REPORT_ENGINE_STATE_PATH", str(tmp_path / "reports.json"))
    monkeypatch.setenv("K1_REPORT_ENGINE_ARTIFACT_DIR", str(tmp_path / "reports"))
    import apps.backend.src.core.intelligence_memory as memory_mod
    import apps.backend.src.core.intelligence_query as query_mod
    import apps.backend.src.core.report_engine as report_mod

    memory_mod._manager_instance = None
    query_mod._engine_instance = None
    report_mod._engine_instance = None

    manager = memory_mod.get_memory_manager()
    manager.ingest(_entry(domain="app1.example.com", vuln_type="xss", tech=["react", "nginx"], services=["https"]))
    manager.ingest(_entry(domain="app2.example.com", vuln_type="xss", tech=["react", "nginx"], services=["https"], tags=["endpoint:/api/login"]))
    manager.ingest(_entry(domain="portal.example.com", vuln_type="xss", tech=["react"], services=["https"]))

    engine = OpportunityExpansionEngine(
        manager=manager,
        policy=ScopePolicy(allowlist=["*.example.com"], denylist=["admin.example.com"]),
    )
    result = engine.expand(
        source=ExpansionSource(
            source_type="validated_finding",
            source_object_id="mem-source",
            vuln_type="xss",
            source_target="app1.example.com",
            confidence=0.87,
            tech_stack=["react", "nginx"],
            headers=["server:nginx"],
            endpoint_shapes=["/api/login"],
            pattern_tags=["xss"],
            service_fingerprints=["https"],
            expected_yield=2.0,
        ),
        candidate_targets=["app2.example.com", "portal.example.com", "admin.example.com", "external.test"],
        max_candidates=10,
        max_batch_size=3,
    )

    assert result.expansion_candidates
    assert result.target_batches
    blocked_targets = {row["target"] for row in result.blocked_targets}
    assert "external.test" in blocked_targets
    assert "admin.example.com" in blocked_targets
    assert result.expansion_candidates[0].expansion_score >= result.expansion_candidates[-1].expansion_score


def test_action_service_applies_expansion_and_executes_reviewed_subset(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_OPPORTUNITY_ACTION_STATE_PATH", str(tmp_path / "action_state.json"))
    monkeypatch.setenv("K1_AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("K1_REPORT_ENGINE_STATE_PATH", str(tmp_path / "report_state.json"))
    monkeypatch.setenv("K1_REPORT_ENGINE_ARTIFACT_DIR", str(tmp_path / "reports"))

    events: list[str] = []
    runtime = _FakeRuntime()
    service = OpportunityActionService(
        runtime_provider=lambda: runtime,
        event_emitter=lambda event: events.append(event.event_type),
        target_cap=10,
    )
    service._policy = ScopePolicy()

    opp = _sample_opportunity(["app1.example.com", "app2.example.com", "portal.example.com"])
    tenant_id = str(uuid4())
    actor = "analyst-expansion"

    expansion = OpportunityExpansionResult(
        source_type="validated_finding",
        source_object_id="mem-source",
        source_vuln_type="xss",
        source_target="app1.example.com",
        expansion_candidates=[
            ExpansionCandidate(
                target="app1.example.com",
                similarity_score=0.92,
                confidence=0.88,
                memory_match_strength=0.8,
                duplicate_risk=0.2,
                target_importance=0.75,
                expected_report_quality=0.81,
                expansion_score=0.86,
                estimated_yield=1.4,
                risk_band="medium",
                matching_factors=["tech_stack_overlap"],
                rationale="high match",
            ),
            ExpansionCandidate(
                target="app2.example.com",
                similarity_score=0.84,
                confidence=0.83,
                memory_match_strength=0.7,
                duplicate_risk=0.25,
                target_importance=0.72,
                expected_report_quality=0.79,
                expansion_score=0.8,
                estimated_yield=1.2,
                risk_band="medium",
                matching_factors=["endpoint_shape_overlap"],
                rationale="strong match",
            ),
        ],
        target_batches=[
            TargetBatch(
                batch_id="batch-1",
                targets=["app1.example.com", "app2.example.com"],
                expected_yield=2.6,
                risk_band="medium",
                rationale="balanced medium risk batch",
            )
        ],
        blocked_targets=[],
        expansion_score=0.83,
        expected_yield=2.6,
        duplicate_risk=0.21,
        confidence=0.86,
        expected_report_quality=0.8,
        recommended_execution_order=["batch-1"],
        expansion_rationale="validated xss expanded across similar apps",
    )
    updated = service.apply_expansion(
        opp,
        tenant_id=tenant_id,
        actor=actor,
        source_type="validated_finding",
        source_object_id="mem-source",
        source_memory_id="mem-source",
        source_pattern_id=None,
        expansion=expansion,
    )
    assert updated.expansion_candidates
    assert "opportunity_expansion_created" in events
    assert "opportunity_batch_ready" in events

    approved = service.approve(
        opp,
        tenant_id=tenant_id,
        actor=actor,
        reason="reviewed targets only",
        approved_targets=["app2.example.com"],
    )
    assert approved.approved_targets == ["app2.example.com"]

    executing = service.execute(opp, tenant_id=tenant_id, actor=actor, reason="execute reviewed")
    selected_targets = executing.execution_metadata.get("selected_targets", [])
    assert selected_targets == ["app2.example.com"]
