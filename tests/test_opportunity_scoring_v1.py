from __future__ import annotations

from apps.backend.src.core.opportunity_catalog import Opportunity
from apps.backend.src.core.opportunity_scoring import rank_opportunities_v1, score_opportunity


def _opp(
    oid: str,
    *,
    payout: int,
    priority: float,
    scope_count: int,
    vdp_only: bool = False,
) -> Opportunity:
    return Opportunity(
        id=oid,
        name=oid,
        organization=oid,
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://example.com",
        scope_url="https://example.com/scope",
        scope_summary="scope",
        scope_domains=[f"a{i}.example.com" for i in range(scope_count)],
        max_payout_usd=payout,
        min_payout_usd=max(100, payout // 10),
        vdp_only=vdp_only,
        response_sla_days=30,
        tags=["web"],
        vuln_types=["xss", "idor", "ssrf"],
        priority_score=priority,
        notes="",
    )


def test_v1_scoring_penalizes_duplicates():
    opp = _opp("acme", payout=20000, priority=0.8, scope_count=3)
    clean = score_opportunity(opp, prior_reports=[])
    dup = score_opportunity(
        opp,
        prior_reports=[{"title": "Acme portal auth bypass report", "platform": "hackerone"}],
    )
    assert dup.score < clean.score
    assert dup.factors["duplicate_risk"] > 0


def test_v1_scoring_penalizes_effort():
    easy = _opp("easy", payout=10000, priority=0.7, scope_count=2)
    hard = _opp("hard", payout=10000, priority=0.7, scope_count=25)
    s_easy = score_opportunity(easy, prior_reports=[])
    s_hard = score_opportunity(hard, prior_reports=[])
    assert s_easy.score > s_hard.score
    assert s_hard.factors["effort_score"] >= s_easy.factors["effort_score"]


def test_rank_opportunities_v1_sorted_desc():
    a = _opp("a", payout=5000, priority=0.5, scope_count=3)
    b = _opp("b", payout=30000, priority=0.8, scope_count=3)
    ranked = rank_opportunities_v1([a, b], prior_reports=[])
    assert ranked[0].score >= ranked[1].score
