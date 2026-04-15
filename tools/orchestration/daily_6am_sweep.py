from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from tools.ai.learning_feedback_loop import LearningFeedbackLoop
from tools.intelligence.market_intelligence_engine import MarketIntelligenceEngine
from tools.orchestration.bug_bounty_detection_model import BugBountyDetectionIntelligence
from tools.orchestration.bug_bounty_success_model import BugBountySuccessPredictor, OpportunityScope
from tools.orchestration.round_robin_manager import RoundRobinCycleManager
from tools.orchestration.scan_queue_balancer import ScanQueueBalancer
from tools.orchestration.scanning_prioritization_engine import ScanningPrioritizationEngine


@dataclass(slots=True)
class OpportunityScore:
    opportunity_id: str
    opportunity_name: str
    platform: str
    confidence_score: float
    estimated_payout: float
    composite_score: float
    previously_scanned_days_ago: int
    market_intelligence_flags: list[str]
    target_archetype: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "opportunity_name": self.opportunity_name,
            "platform": self.platform,
            "confidence_score": self.confidence_score,
            "estimated_payout": self.estimated_payout,
            "composite_score": self.composite_score,
            "previously_scanned_days_ago": self.previously_scanned_days_ago,
            "market_intelligence_flags": self.market_intelligence_flags,
            "target_archetype": self.target_archetype,
        }


class OpportunityScoring:
    """Confidence + payout scoring using target profiles, recency, and learning feedback."""

    def __init__(
        self,
        *,
        profile_path: str | Path = "tools/knowledge/bug_bounty_target_detection_profile.yaml",
        learning_db_path: str | Path = "tools/ai/data/learning_feedback_db.yaml",
    ) -> None:
        self.profile_path = Path(profile_path)
        self.learning_loop = LearningFeedbackLoop(db_path=learning_db_path)
        self.profile_data = self._read_yaml(self.profile_path)

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _normalize(value: str | None) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime:
        if not date_str:
            return datetime.now(UTC) - timedelta(days=30)
        raw = date_str.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return datetime.now(UTC) - timedelta(days=30)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    @staticmethod
    def _parse_range_to_average(text: str | None, default_value: float) -> float:
        raw = (text or "").strip().replace("$", "")
        if "-" not in raw:
            try:
                return float(raw)
            except ValueError:
                return default_value
        left, right = raw.split("-", 1)
        try:
            return (float(left) + float(right)) / 2.0
        except ValueError:
            return default_value

    def _profile_for_target(self, target_archetype: str) -> dict[str, Any]:
        profiles = self.profile_data.get("bug_bounty_target_detection_profile", {}).get("target_profiles", [])
        if not isinstance(profiles, list):
            return {}
        target = self._normalize(target_archetype)
        for row in profiles:
            if not isinstance(row, dict):
                continue
            if self._normalize(str(row.get("target_type", ""))) == target:
                return row
        return {}

    def archetype_confidence_factor(self, target_archetype: str) -> float:
        mapping = {
            "early_stage_saas": 0.85,
            "established_saas": 0.74,
            "enterprise_multi_property": 0.62,
            "fintech_regulated": 0.58,
            "consumer_ecommerce": 0.79,
        }
        return mapping.get(self._normalize(target_archetype), 0.65)

    def scan_recency_factor(self, last_scanned_date: str | None) -> tuple[float, int]:
        last_scan = self._parse_date(last_scanned_date)
        days = max(0, (datetime.now(UTC) - last_scan).days)
        # 0.35 when recently scanned, rising to 1.0 around 120 days.
        factor = min(1.0, 0.35 + (days / 120.0))
        return round(factor, 4), days

    @staticmethod
    def historical_findings_factor(historical_findings_count: int) -> float:
        count = max(0, int(historical_findings_count))
        # More historical success suggests higher future hit-rate, with saturation.
        return round(min(1.0, 0.4 + (count / 20.0)), 4)

    @staticmethod
    def tech_stack_factor(tech_stack: list[str]) -> float:
        stack_blob = " ".join(str(x) for x in tech_stack).lower()
        signals = {
            "legacy": 0.78,
            "wordpress": 0.82,
            "apache": 0.73,
            "react": 0.69,
            "node": 0.72,
            "graphql": 0.75,
            "oauth": 0.74,
            "kubernetes": 0.68,
            "java": 0.63,
        }
        matched = [score for key, score in signals.items() if key in stack_blob]
        if not matched:
            return 0.62
        return round(sum(matched) / len(matched), 4)

    @staticmethod
    def market_intelligence_factor(market_flags: list[str]) -> float:
        if not market_flags:
            return 0.45
        return round(min(1.0, 0.55 + (0.1 * len(market_flags))), 4)

    @staticmethod
    def normalize_payout(value: float, min_value: float, max_value: float) -> float:
        if max_value <= min_value:
            return 1.0
        return round((value - min_value) / (max_value - min_value), 4)

    def _learning_adjustment(self, target_archetype: str) -> float:
        snapshot = self.learning_loop.get_learning_snapshot()
        factors = snapshot.get("vuln_correction_factors", {})
        if not isinstance(factors, dict) or not factors:
            return 1.0

        archetype_key = self._normalize(target_archetype)
        matched = [
            float(value)
            for key, value in factors.items()
            if archetype_key.split("_")[0] in str(key)
        ]
        if not matched:
            return 1.0
        return round(max(0.8, min(1.25, sum(matched) / len(matched))), 3)

    def estimate_payout(self, opportunity: dict[str, Any], days_since_scan: int) -> float:
        target_type = str(opportunity.get("target_archetype", "early_stage_saas"))
        profile = self._profile_for_target(target_type)

        base = self._parse_range_to_average(
            str(profile.get("estimated_total_payout_usd", "")),
            default_value=9000.0,
        )

        recency_adjustment = min(1.30, 1.0 + ((days_since_scan / 365.0) * 0.30))
        learning_adjustment = self._learning_adjustment(target_type)
        platform = self._normalize(str(opportunity.get("platform", "hackerone")))
        platform_adjustment = 1.15 if platform == "direct" else (1.05 if platform == "intigriti" else 1.0)

        return round(base * recency_adjustment * learning_adjustment * platform_adjustment, 2)

    def calculate_confidence(self, opportunity: dict[str, Any], market_flags: list[str]) -> tuple[float, int, dict[str, float]]:
        target_type = str(opportunity.get("target_archetype", "early_stage_saas"))
        recency_factor, days_since = self.scan_recency_factor(opportunity.get("last_scanned_date"))

        factors = {
            "archetype_factor": self.archetype_confidence_factor(target_type),
            "scan_recency_factor": recency_factor,
            "historical_findings_factor": self.historical_findings_factor(
                int(opportunity.get("historical_findings_count", 0))
            ),
            "tech_stack_vulnerability_factor": self.tech_stack_factor(
                opportunity.get("detected_tech_stack") or []
            ),
            "market_intelligence_factor": self.market_intelligence_factor(market_flags),
        }

        confidence = (
            factors["archetype_factor"] * 0.25
            + factors["scan_recency_factor"] * 0.25
            + factors["historical_findings_factor"] * 0.20
            + factors["tech_stack_vulnerability_factor"] * 0.20
            + factors["market_intelligence_factor"] * 0.10
        )
        return round(min(1.0, confidence), 4), days_since, factors


class DailyOrchestrationSweep:
    """
    Daily 6AM orchestration sweep.

    Actions:
    1) load and score opportunities
    2) refresh market intelligence
    3) update round-robin cycle list
    4) generate balanced daily scan schedule
    5) emit immutable sweep log record
    """

    def __init__(
        self,
        *,
        timezone_name: str = "America/Denver",
        opportunities_path: str | Path = "tools/orchestration/data/opportunities.yaml",
        sweep_log_path: str | Path = "tools/orchestration/data/daily_6am_sweep_log.jsonl",
    ) -> None:
        self.timezone = ZoneInfo(timezone_name)
        self.opportunities_path = Path(opportunities_path)
        self.opportunities_path.parent.mkdir(parents=True, exist_ok=True)

        self.sweep_log_path = Path(sweep_log_path)
        self.sweep_log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.sweep_log_path.exists():
            self.sweep_log_path.write_text("", encoding="utf-8")

        self.scoring = OpportunityScoring()
        self.round_robin_manager = RoundRobinCycleManager()
        self.market_intelligence_engine = MarketIntelligenceEngine(
            opportunities_path=self.opportunities_path,
            allow_network_fetch=False,
        )
        self.scan_queue_balancer = ScanQueueBalancer()

        predictor = BugBountySuccessPredictor(allow_local_policy_override=True)
        detection_model = BugBountyDetectionIntelligence(scope_predictor=predictor)
        self.scanning_prioritizer = ScanningPrioritizationEngine(detection_model=detection_model)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _stable_json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @staticmethod
    def _sha256(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _previous_hash(self) -> str:
        rows: list[dict[str, Any]] = []
        with self.sweep_log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if not rows:
            return "GENESIS"
        return str(rows[-1].get("record_hash", "GENESIS"))

    def log_sweep_immutably(self, sweep_record: dict[str, Any]) -> dict[str, Any]:
        row = {
            "sweep_time": self._now(),
            "previous_record_hash": self._previous_hash(),
            "payload": sweep_record,
        }
        row["record_hash"] = self._sha256(self._stable_json(row))
        row["immutable"] = True

        with self.sweep_log_path.open("a", encoding="utf-8") as f:
            f.write(self._stable_json(row) + "\n")

        return row

    def _is_6am_window(self, now_utc: datetime) -> bool:
        local = now_utc.astimezone(self.timezone)
        return local.hour == 6

    @staticmethod
    def _default_opportunities() -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        base = [
            ("opp-h1-saas-001", "Alpha SaaS", "hackerone", "early_stage_saas", ["app.alpha.example"], ["Node.js", "React", "PostgreSQL"], 12),
            ("opp-h1-saas-002", "Delta SaaS", "hackerone", "established_saas", ["api.delta.example"], ["Kubernetes", "API Gateway", "OAuth"], 21),
            ("opp-inti-ent-001", "Enterprise One", "intigriti", "enterprise_multi_property", ["portal.enterprise.example"], ["ASP.NET", "Oracle", "WAF"], 35),
            ("opp-dir-fin-001", "Fintech Direct", "direct", "fintech_regulated", ["secure.fin.example"], ["Java", "SSO", "TLS"], 18),
            ("opp-h1-ecom-001", "Ecom Public", "hackerone", "consumer_ecommerce", ["shop.ecom.example"], ["Node.js", "GraphQL", "Redis"], 9),
        ]
        out: list[dict[str, Any]] = []
        for idx, row in enumerate(base, start=1):
            opp_id, name, platform, archetype, targets, tech, last_days = row
            out.append(
                {
                    "id": opp_id,
                    "name": name,
                    "platform": platform,
                    "target_archetype": archetype,
                    "active": True,
                    "authorization_verified": True,
                    "targets": targets,
                    "exclusions": [],
                    "rules": ["detection_only", "no_dos"],
                    "detected_tech_stack": tech,
                    "historical_findings_count": 2 + idx,
                    "last_scanned_date": (now - timedelta(days=last_days)).isoformat(),
                    "downloaded_at": now.isoformat(),
                }
            )
        return out

    def load_all_opportunities(self) -> list[dict[str, Any]]:
        if not self.opportunities_path.exists():
            opportunities = self._default_opportunities()
            self.opportunities_path.write_text(
                yaml.safe_dump({"opportunities": opportunities}, sort_keys=False),
                encoding="utf-8",
            )
            return opportunities

        payload = yaml.safe_load(self.opportunities_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            return self._default_opportunities()

        opportunities = payload.get("opportunities", [])
        if not isinstance(opportunities, list) or not opportunities:
            return self._default_opportunities()

        return [x for x in opportunities if isinstance(x, dict)]

    @staticmethod
    def _opportunity_scope(opportunity: dict[str, Any]) -> OpportunityScope:
        return OpportunityScope(
            opportunity_id=str(opportunity.get("id") or opportunity.get("opportunity_id") or "unknown"),
            platform=str(opportunity.get("platform", "hackerone")),
            active=bool(opportunity.get("active", True)),
            targets=[str(x) for x in opportunity.get("targets", [])],
            authorization_verified=bool(opportunity.get("authorization_verified", True)),
            program_name=str(opportunity.get("name", "")) or None,
            scope_source="daily_6am_sweep",
            exclusions=[str(x) for x in opportunity.get("exclusions", [])],
            rules=[str(x) for x in opportunity.get("rules", [])],
            downloaded_at=str(opportunity.get("downloaded_at") or datetime.now(UTC).isoformat()),
        )

    def _build_scan_hint(self, opportunity: dict[str, Any]) -> dict[str, Any]:
        scope = self._opportunity_scope(opportunity)
        try:
            plan = self.scanning_prioritizer.optimize_scanning_order(
                opportunity_scope=scope,
                target_archetype=str(opportunity.get("target_archetype", "early_stage_saas")),
                target_hints={"industry": str(opportunity.get("industry", "saas"))},
                top_n=3,
            )
            phase = plan.recommended_scanning_order[1] if len(plan.recommended_scanning_order) > 1 else {}
            steps = phase.get("steps", []) if isinstance(phase, dict) else []
            return {
                "estimated_duration_minutes": int(plan.total_estimated_scan_time_minutes),
                "top_playbooks": [str(x.get("detection_playbook_id")) for x in steps[:3]],
                "scan_efficiency": plan.scanning_efficiency,
            }
        except Exception as exc:  # pragma: no cover - resilience path
            return {
                "estimated_duration_minutes": 35,
                "top_playbooks": [],
                "scan_efficiency": "fallback",
                "reason": f"prioritizer_unavailable: {exc}",
            }

    @staticmethod
    def _market_flags_for_opportunity(opportunity_id: str, market_intel: dict[str, Any]) -> list[str]:
        rows = market_intel.get("opportunities_with_market_intelligence", [])
        if not isinstance(rows, list):
            return []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("opportunity_id", "")) != opportunity_id:
                continue
            cves = row.get("matching_cves", [])
            return [str(x) for x in cves if str(x).strip()]
        return []

    def _score_opportunities(
        self,
        opportunities: list[dict[str, Any]],
        market_intel: dict[str, Any],
    ) -> list[dict[str, Any]]:
        scored_rows: list[dict[str, Any]] = []

        # First pass: compute confidence and payout.
        for opp in opportunities:
            oid = str(opp.get("id") or opp.get("opportunity_id") or "")
            if not oid:
                continue

            market_flags = self._market_flags_for_opportunity(oid, market_intel)
            confidence, days_since_scan, factors = self.scoring.calculate_confidence(opp, market_flags)
            payout = self.scoring.estimate_payout(opp, days_since_scan)

            scored = OpportunityScore(
                opportunity_id=oid,
                opportunity_name=str(opp.get("name", oid)),
                platform=str(opp.get("platform", "hackerone")),
                confidence_score=confidence,
                estimated_payout=payout,
                composite_score=0.0,
                previously_scanned_days_ago=days_since_scan,
                market_intelligence_flags=market_flags,
                target_archetype=str(opp.get("target_archetype", "early_stage_saas")),
            ).as_dict()
            scored["factor_breakdown"] = factors
            scored["opportunity"] = opp
            scored_rows.append(scored)

        if not scored_rows:
            return []

        min_payout = min(float(row["estimated_payout"]) for row in scored_rows)
        max_payout = max(float(row["estimated_payout"]) for row in scored_rows)

        for row in scored_rows:
            payout_norm = self.scoring.normalize_payout(float(row["estimated_payout"]), min_payout, max_payout)
            composite = (float(row["confidence_score"]) * 0.7) + (payout_norm * 0.3)
            row["composite_score"] = round(composite, 4)
            row["payout_normalized"] = payout_norm

        scored_rows.sort(
            key=lambda r: (float(r.get("composite_score", 0.0)), float(r.get("estimated_payout", 0.0))),
            reverse=True,
        )
        return scored_rows

    def _refresh_round_robin_queue(self, sorted_scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.round_robin_manager.current_round_robin_list:
            return self.round_robin_manager.initialize_round_robin_list(sorted_scored)

        if self.round_robin_manager.check_if_round_robin_cycle_complete():
            return self.round_robin_manager.renew_round_robin_cycle(sorted_scored)

        remaining_ids = {
            str(item.get("opportunity_id", ""))
            for item in self.round_robin_manager.current_round_robin_list
            if str(item.get("opportunity_id", "")).strip()
        }
        reprioritized = [row for row in sorted_scored if str(row.get("opportunity_id", "")) in remaining_ids]
        if not reprioritized:
            return self.round_robin_manager.renew_round_robin_cycle(sorted_scored)
        return self.round_robin_manager.replace_current_queue(reprioritized)

    def generate_daily_scan_schedule(
        self,
        round_robin_list: list[dict[str, Any]],
        intelligent_scan_opportunities: list[dict[str, Any]],
        *,
        opportunity_index: dict[str, dict[str, Any]],
        max_scan_slots: int = 16,
    ) -> dict[str, Any]:
        rr_scans: list[dict[str, Any]] = []
        for row in round_robin_list:
            oid = str(row.get("opportunity_id", ""))
            opp = opportunity_index.get(oid, {})
            hint = self._build_scan_hint(opp) if opp else {"estimated_duration_minutes": 35, "top_playbooks": []}
            rr_scans.append(
                {
                    "scan_id": f"rr::{oid}",
                    "opportunity_id": oid,
                    "scan_mode": "round_robin",
                    "target_archetype": row.get("target_archetype") or opp.get("target_archetype", "unknown"),
                    "estimated_duration_minutes": hint.get("estimated_duration_minutes", 35),
                    "top_playbooks": hint.get("top_playbooks", []),
                    "confidence": row.get("confidence_score", row.get("confidence", 0.0)),
                    "estimated_payout": row.get("estimated_payout", 0.0),
                }
            )

        intelligent_scans: list[dict[str, Any]] = []
        for intel in intelligent_scan_opportunities:
            if not isinstance(intel, dict):
                continue
            affected = intel.get("affected_opportunities", [])
            if not isinstance(affected, list):
                continue
            for oid in affected[:3]:  # cap per trigger to keep queue bounded
                intelligent_scans.append(
                    {
                        "scan_id": f"intel::{intel.get('trigger_cve')}::{oid}",
                        "opportunity_id": str(oid),
                        "scan_mode": "intelligent_targeted",
                        "trigger_cve": intel.get("trigger_cve"),
                        "priority": float(intel.get("priority", 0.0)),
                        "estimated_duration_minutes": 20,
                        "narrow_scan_focus": intel.get("narrow_scan_focus"),
                    }
                )

        self.scan_queue_balancer.load_round_robin_queue(rr_scans)
        self.scan_queue_balancer.load_intelligent_scan_queue(intelligent_scans)

        schedule: list[dict[str, Any]] = []
        for slot in range(max_scan_slots):
            next_item = self.scan_queue_balancer.schedule_next_scan()
            if not next_item:
                break

            scan = next_item["scan"]
            duration = float(scan.get("estimated_duration_minutes", 20.0))
            self.scan_queue_balancer.record_scan_completion(
                scan_type=str(next_item["scan_type"]),
                scan=scan,
                duration_minutes=duration,
                status="planned",
            )
            schedule.append(
                {
                    "slot": slot + 1,
                    "scan_type": next_item["scan_type"],
                    "scan": scan,
                }
            )

        return {
            "schedule": schedule,
            "queue_snapshot": self.scan_queue_balancer.queue_snapshot(),
            "time_budget_allocation": self.scan_queue_balancer.time_budget_allocation,
        }

    def execute_6am_sweep(
        self,
        *,
        run_time_utc: datetime | None = None,
        allow_manual_trigger: bool = False,
    ) -> dict[str, Any]:
        now_utc = run_time_utc or datetime.now(UTC)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=UTC)
        else:
            now_utc = now_utc.astimezone(UTC)

        if not allow_manual_trigger and not self._is_6am_window(now_utc):
            raise ValueError("Daily orchestration sweep is restricted to the 6AM local execution window.")

        all_opportunities = self.load_all_opportunities()
        market_intel = self.market_intelligence_engine.update_market_intelligence_daily(all_opportunities, days=7)
        scored_opportunities = self._score_opportunities(all_opportunities, market_intel)

        round_robin_list = self._refresh_round_robin_queue(scored_opportunities)
        intelligent_candidates = market_intel.get("intelligent_scan_candidates", [])
        if not isinstance(intelligent_candidates, list):
            intelligent_candidates = []

        opportunity_index = {
            str(opp.get("id") or opp.get("opportunity_id")): opp for opp in all_opportunities
        }
        daily_schedule = self.generate_daily_scan_schedule(
            round_robin_list,
            intelligent_candidates,
            opportunity_index=opportunity_index,
            max_scan_slots=16,
        )

        sweep_record = {
            "sweep_time": now_utc.isoformat(),
            "sweep_date": now_utc.date().isoformat(),
            "timezone": str(self.timezone),
            "actions": [
                "load_all_opportunities",
                "score_opportunities",
                "update_market_intelligence",
                "refresh_round_robin_list",
                "generate_daily_schedule",
            ],
            "total_opportunities": len(all_opportunities),
            "scored_opportunities": [
                {
                    "opportunity_id": row.get("opportunity_id"),
                    "confidence_score": row.get("confidence_score"),
                    "estimated_payout": row.get("estimated_payout"),
                    "composite_score": row.get("composite_score"),
                    "market_intelligence_flags": row.get("market_intelligence_flags", []),
                }
                for row in scored_opportunities
            ],
            "round_robin_list_size": len(round_robin_list),
            "market_intelligence": {
                "nvd_source_mode": market_intel.get("sources", {}).get("nvd", {}).get("source_mode"),
                "nvd_record_count": market_intel.get("sources", {}).get("nvd", {}).get("record_count"),
                "exploitdb_source_mode": market_intel.get("sources", {}).get("exploitdb", {}).get("source_mode"),
                "exploitdb_record_count": market_intel.get("sources", {}).get("exploitdb", {}).get("record_count"),
                "affected_opportunity_count": len(market_intel.get("opportunities_with_market_intelligence", [])),
            },
            "intelligent_scan_candidates": len(intelligent_candidates),
            "daily_scan_schedule": daily_schedule,
        }

        immutable_record = self.log_sweep_immutably(sweep_record)
        return {
            "sweep_record": sweep_record,
            "immutable_record": {
                "record_hash": immutable_record.get("record_hash"),
                "previous_record_hash": immutable_record.get("previous_record_hash"),
            },
        }


__all__ = ["DailyOrchestrationSweep", "OpportunityScoring", "OpportunityScore"]
