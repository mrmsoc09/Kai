from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from .opportunity_catalog import Opportunity


@dataclass
class OpportunityScore:
    opportunity_id: str
    score: float
    factors: Dict[str, float]
    reasoning: List[str]
    vulnerability_pressure_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "score": round(self.score, 4),
            "vulnerability_pressure_score": round(self.vulnerability_pressure_score, 4),
            "factors": {k: round(v, 4) for k, v in self.factors.items()},
            "reasoning": self.reasoning,
        }


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


# Static exploitation pressure weights per vulnerability family.
# Calibrated from EPSS percentile distributions and CVE publication rates.
# RCE and auth bypass consistently show the highest real-world exploitation rates.
_VULN_PRESSURE: Dict[str, float] = {
    "rce":         0.90,
    "auth_bypass": 0.85,
    "ssrf":        0.78,
    "sqli":        0.72,
    "oauth":       0.70,
    "idor":        0.65,
    "logic":       0.60,
    "xss":         0.50,
}


def _vulnerability_pressure(vuln_types: List[str], epss_boost: float = 0.0) -> float:
    """
    Compute a vulnerability pressure score from vuln type weights and an optional
    EPSS-derived boost (0–1 representing average EPSS across program-related CVEs).
    """
    if not vuln_types:
        base = 0.30  # unknown scope — assume moderate
    else:
        weights = [_VULN_PRESSURE.get(v.lower(), 0.40) for v in vuln_types]
        # Use max rather than mean — worst-case pressure matters most
        base = max(weights)
    # Blend with EPSS boost: 70% static, 30% live EPSS signal
    return _clamp01(0.70 * base + 0.30 * epss_boost)


def _coverage_score(vuln_types: List[str]) -> float:
    # Baseline high-value vulnerability family coverage.
    high_value = {"xss", "sqli", "idor", "ssrf", "rce", "auth_bypass", "oauth", "logic"}
    return _clamp01(len(set(v.lower() for v in vuln_types) & high_value) / 8.0)


def _effort_score(scope_domains: List[str], response_sla_days: int, vdp_only: bool) -> float:
    scope_pressure = _clamp01(len(scope_domains) / 20.0)
    sla_penalty = _clamp01((response_sla_days or 30) / 90.0)
    vdp_penalty = 0.25 if vdp_only else 0.0
    return _clamp01(0.55 * scope_pressure + 0.30 * sla_penalty + 0.15 * vdp_penalty)


def _duplicate_risk(opportunity: Opportunity, prior_reports: List[Dict[str, Any]]) -> float:
    if not prior_reports:
        return 0.0

    org = opportunity.organization.lower()
    name = opportunity.name.lower()
    platform = opportunity.platform.lower()
    risk = 0.0
    for report in prior_reports:
        title = str(report.get("title") or "").lower()
        report_platform = str(report.get("platform") or "").lower()
        if org and org in title:
            risk += 0.30
        if name and any(token and token in title for token in name.split()):
            risk += 0.25
        if platform and report_platform and platform == report_platform:
            risk += 0.15
    return _clamp01(risk)


def score_opportunity(
    opportunity: Opportunity,
    *,
    prior_reports: List[Dict[str, Any]] | None = None,
    effort_bias: float = 0.5,
    epss_boost: float = 0.0,
) -> OpportunityScore:
    """
    Score a single opportunity.

    Args:
        opportunity: The opportunity to score.
        prior_reports: Previously submitted reports (used for duplicate risk).
        effort_bias: 0.0 = prefer low-effort; 1.0 = ignore effort.
        epss_boost: Average EPSS score (0–1) across CVEs associated with the program's
                    vuln types, if available. Callers can fetch this from EPSSClient.
    """
    reports = prior_reports or []
    avg_payout = (opportunity.min_payout_usd + opportunity.max_payout_usd) / 2.0
    payout_norm = _clamp01(math.log10(avg_payout + 1.0) / math.log10(50_001.0))
    coverage = _coverage_score(opportunity.vuln_types)
    vuln_pressure = _vulnerability_pressure(opportunity.vuln_types, epss_boost=epss_boost)
    # Incorporate vuln_pressure into success probability (15% weight)
    success_prob = _clamp01(
        0.40 * opportunity.priority_score
        + 0.30 * coverage
        + 0.15 * vuln_pressure
        + 0.15 * (1.0 - effort_bias)
    )
    expected_value = _clamp01(payout_norm * success_prob)
    effort = _effort_score(opportunity.scope_domains, opportunity.response_sla_days, opportunity.vdp_only)
    duplicate = _duplicate_risk(opportunity, reports)
    adjusted = _clamp01(expected_value * (1.0 - 0.6 * duplicate) * (1.0 - 0.5 * effort))

    reasoning = [
        f"expected_value={expected_value:.3f} from payout_norm={payout_norm:.3f} and success_prob={success_prob:.3f}",
        f"vuln_pressure={vuln_pressure:.3f} (epss_boost={epss_boost:.3f})",
        f"duplicate_risk={duplicate:.3f} reduced score by {(0.6 * duplicate):.3f} weight",
        f"effort_score={effort:.3f} reduced score by {(0.5 * effort):.3f} weight",
    ]
    return OpportunityScore(
        opportunity_id=opportunity.id,
        score=adjusted,
        vulnerability_pressure_score=vuln_pressure,
        factors={
            "expected_value": expected_value,
            "payout_norm": payout_norm,
            "success_probability": success_prob,
            "coverage_score": coverage,
            "vulnerability_pressure": vuln_pressure,
            "duplicate_risk": duplicate,
            "effort_score": effort,
        },
        reasoning=reasoning,
    )


def rank_opportunities_v1(
    opportunities: Iterable[Opportunity],
    *,
    prior_reports: List[Dict[str, Any]] | None = None,
    effort_bias: float = 0.5,
    epss_scores: Optional[Dict[str, float]] | None = None,
) -> List[OpportunityScore]:
    """
    Rank opportunities by composite score.

    Args:
        epss_scores: Optional dict mapping opportunity_id → average EPSS boost (0–1).
                     Callers with async context can pre-fetch EPSS data and pass it here.
    """
    epss_map = epss_scores or {}
    scored = [
        score_opportunity(
            opp,
            prior_reports=prior_reports,
            effort_bias=effort_bias,
            epss_boost=epss_map.get(opp.id, 0.0),
        )
        for opp in opportunities
    ]
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored
