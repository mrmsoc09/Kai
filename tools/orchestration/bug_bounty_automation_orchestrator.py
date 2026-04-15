from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tools.intelligence.finding_categorization import FindingCategorizer
from tools.intelligence.finding_correlation_engine import FindingCorrelationEngine
from tools.intelligence.finding_deduplicator import FindingDeduplicator
from tools.intelligence.remediation_guidance_engine import RemediationGuidanceEngine
from tools.intelligence.severity_payout_estimator import SeverityPayoutEstimator
from tools.orchestration.bug_bounty_detection_model import BugBountyDetectionIntelligence
from tools.orchestration.bug_bounty_success_model import (
    BugBountySuccessPredictor,
    OpportunityScope,
    PlatformPolicyViolation,
    ScopeViolationError,
)
from tools.orchestration.scanning_prioritization_engine import ScanningPrioritizationEngine


class AuthorizationError(RuntimeError):
    pass


class DetectionPolicyError(RuntimeError):
    pass


FORBIDDEN_OPERATION_KEYWORDS = {
    "exploit",
    "exploitation",
    "persistence",
    "destruction",
    "evasion",
    "lateral",
}


@dataclass(slots=True)
class WorkflowResult:
    status: str
    target_type: str
    scope_validated: bool
    raw_findings_count: int
    deduplicated_findings_count: int
    duplicate_reduction_percent: float
    enriched_findings: list[dict[str, Any]]
    correlation_clusters: dict[str, Any]
    submission_ready_report: dict[str, Any]
    workflow_metrics: dict[str, Any]
    validation_log: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "target_type": self.target_type,
            "scope_validated": self.scope_validated,
            "raw_findings_count": self.raw_findings_count,
            "deduplicated_findings_count": self.deduplicated_findings_count,
            "duplicate_reduction_percent": self.duplicate_reduction_percent,
            "enriched_findings": self.enriched_findings,
            "correlation_clusters": self.correlation_clusters,
            "submission_ready_report": self.submission_ready_report,
            "workflow_metrics": self.workflow_metrics,
            "validation_log": self.validation_log,
        }


@dataclass(slots=True)
class ScenarioBenchmark:
    scenario_name: str
    target_type: str
    total_time_minutes: int
    detection_time_minutes: int
    raw_findings: int
    deduplicated_findings: int
    duplicate_reduction_percent: float
    estimated_total_payout_usd: int
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "target_type": self.target_type,
            "total_time_minutes": self.total_time_minutes,
            "detection_time_minutes": self.detection_time_minutes,
            "raw_findings": self.raw_findings,
            "deduplicated_findings": self.deduplicated_findings,
            "duplicate_reduction_percent": self.duplicate_reduction_percent,
            "estimated_total_payout_usd": self.estimated_total_payout_usd,
            "status": self.status,
        }


class BugBountyAutomationOrchestrator:
    """
    End-to-end detection-only orchestrator.

    Workflow:
    authorization -> fingerprint -> classify -> prioritize -> detect ->
    deduplicate -> categorize+enrich -> correlate -> report.

    Safety constraints:
    - Scope validation is mandatory and first.
    - Detection-only playbooks are enforced.
    - No exploitation/persistence/destructive operations are performed.
    """

    def __init__(
        self,
        *,
        opportunity_scope: OpportunityScope,
        opportunity_metadata: dict[str, Any] | None = None,
        allow_local_policy_override: bool = False,
        top_n_detection_playbooks: int = 10,
    ) -> None:
        self.scope = opportunity_scope
        self.metadata = opportunity_metadata or {}
        self.top_n_detection_playbooks = max(1, int(top_n_detection_playbooks))

        self.validation_log: list[str] = []
        self.workflow_metrics: dict[str, Any] = {}

        self.scope_predictor = BugBountySuccessPredictor(
            allow_local_policy_override=allow_local_policy_override
        )
        self.detection_model = BugBountyDetectionIntelligence(scope_predictor=self.scope_predictor)
        batching_efficiency_factor = float(self.metadata.get("batching_efficiency_factor", 0.58))
        self.scanning_prioritizer = ScanningPrioritizationEngine(
            detection_model=self.detection_model,
            batching_efficiency_factor=batching_efficiency_factor,
        )

        self.categorizer = FindingCategorizer()
        self.deduplicator = FindingDeduplicator()
        self.severity_estimator = SeverityPayoutEstimator()
        self.correlation_engine = FindingCorrelationEngine()
        self.remediation_engine = RemediationGuidanceEngine()

    @staticmethod
    def _is_forbidden_operation_text(text: str) -> bool:
        value = text.lower()
        return any(k in value for k in FORBIDDEN_OPERATION_KEYWORDS)

    def validate_opportunity_authorization(self) -> None:
        try:
            self.scope_predictor.verify_scope_authorized(self.scope)
        except (ScopeViolationError, PlatformPolicyViolation) as exc:
            self.validation_log.append(f"authorization_failed: {exc}")
            raise AuthorizationError(str(exc)) from exc

        self.validation_log.append("authorization_passed")

    def _quick_fingerprint(self, primary_target: str, target_hints: dict[str, Any]) -> dict[str, Any]:
        target_type = self.metadata.get("target_archetype") or "early_stage_saas"

        default_stack = {
            "early_stage_saas": ["Node.js", "React", "PostgreSQL", "AWS"],
            "established_saas": ["Kubernetes", "API Gateway", "OAuth2", "PostgreSQL"],
            "enterprise_multi_property": ["ASP.NET", "Oracle", "WAF", "SSO Federation"],
            "fintech_regulated": ["Java", "Strong IAM", "HSM", "Transaction Controls"],
            "consumer_ecommerce": ["Nginx", "Node.js", "Redis", "CDN"],
        }

        host = primary_target
        if "://" in primary_target:
            host = urlparse(primary_target).hostname or primary_target

        stack = target_hints.get("tech_stack") or default_stack.get(str(target_type), default_stack["early_stage_saas"])

        return {
            "target": host,
            "web_server": target_hints.get("web_server", "nginx"),
            "backend_framework": target_hints.get("backend_framework", stack[0] if stack else "unknown"),
            "database": target_hints.get("database", "postgresql"),
            "cloud": target_hints.get("cloud", "unknown"),
            "waf": target_hints.get("waf", "unknown"),
            "tech_stack": stack,
        }

    def _ensure_detection_only_plan(self, scanning_plan: dict[str, Any]) -> None:
        steps = []
        for phase in scanning_plan.get("recommended_scanning_order", []):
            steps.extend(phase.get("steps", []))

        for step in steps:
            name = str(step.get("playbook_name", ""))
            pid = str(step.get("detection_playbook_id", ""))
            ptype = str(step.get("playbook_type", "detection_only")).lower()

            if ptype != "detection_only":
                raise DetectionPolicyError(f"Non detection playbook in plan: {pid}")
            if step.get("forbidden_operations_present", False):
                raise DetectionPolicyError(f"Forbidden operation marker set: {pid}")
            if self._is_forbidden_operation_text(name) or self._is_forbidden_operation_text(pid):
                raise DetectionPolicyError(f"Forbidden operation keyword found: {pid}")

        self.validation_log.append("detection_only_plan_verified")

    def _generate_raw_findings(self, scanning_plan: dict[str, Any], target_type: str) -> list[dict[str, Any]]:
        target = self.scope.targets[0]
        target_host = urlparse(target).hostname if "://" in target else target

        phase_steps = []
        for phase in scanning_plan.get("recommended_scanning_order", []):
            if phase.get("phase") == "prioritized_detection_scans":
                phase_steps = phase.get("steps", [])
                break

        if not phase_steps:
            return []

        scenario_bands = {
            "early_stage_saas": 8,
            "established_saas": 6,
            "enterprise_multi_property": 4,
            "fintech_regulated": 3,
            "consumer_ecommerce": 7,
        }
        raw_count = scenario_bands.get(target_type, 5)

        findings: list[dict[str, Any]] = []
        for i in range(raw_count):
            step = phase_steps[i % len(phase_steps)]
            vuln = str(step.get("vulnerability_type", "Information Disclosure"))
            endpoint = f"https://{target_host}/api/v1/resource/{(i % 4) + 1}"
            findings.append(
                {
                    "finding_id": f"RF-{i+1:03d}",
                    "vulnerability_type": vuln,
                    "target_endpoint": endpoint,
                    "vulnerable_parameter": ["id", "q", "token", "redirect"][i % 4],
                    "detection_method": "optimized_detection_scan",
                    "detection_playbook_id": step.get("detection_playbook_id", "unknown"),
                    "proof_of_concept": {
                        "request_id": f"REQ-{i+1:03d}",
                        "signal": "safe-validation-signal",
                    },
                    "reproduction_steps": [
                        "issue baseline request",
                        "issue safe validation probe",
                        "observe deterministic indicator",
                    ],
                    "confidence": "HIGH",
                    "target_system": target_host,
                    "evidence_id": f"EV-{i+1:03d}",
                }
            )

        # Inject deliberate overlap to validate deduplication quality path.
        if len(findings) >= 4:
            dup_exact = dict(findings[1])
            dup_exact["finding_id"] = f"RF-{len(findings)+1:03d}"
            dup_exact["detection_method"] = "secondary_probe"
            findings.append(dup_exact)

            dup_semantic = dict(findings[2])
            dup_semantic["finding_id"] = f"RF-{len(findings)+1:03d}"
            dup_semantic["vulnerable_parameter"] = ""
            dup_semantic["detection_method"] = "alternate_signature"
            findings.append(dup_semantic)

        # Correlated pair on same endpoint for cluster quality.
        corr_a = {
            "finding_id": f"RF-{len(findings)+1:03d}",
            "vulnerability_type": "Cross-Site Scripting (XSS)",
            "target_endpoint": f"https://{target_host}/profile/update",
            "vulnerable_parameter": "bio",
            "detection_method": "dom_probe",
            "detection_playbook_id": "det_xss_discovery_v1",
            "proof_of_concept": {"request_id": "REQ-XSS-001", "signal": "reflection"},
            "reproduction_steps": ["safe payload", "observe reflection"],
            "confidence": "MEDIUM",
            "target_system": target_host,
            "evidence_id": "EV-XSS-001",
        }
        corr_b = {
            "finding_id": f"RF-{len(findings)+2:03d}",
            "vulnerability_type": "CSRF",
            "target_endpoint": f"https://{target_host}/profile/update",
            "vulnerable_parameter": "csrf_token",
            "detection_method": "state_change_without_token",
            "detection_playbook_id": "det_auth_bypass_v1",
            "proof_of_concept": {"request_id": "REQ-CSRF-001", "signal": "accepted_state_change"},
            "reproduction_steps": ["replay without token", "observe accepted state change"],
            "confidence": "MEDIUM",
            "target_system": target_host,
            "evidence_id": "EV-CSRF-001",
        }
        findings.extend([corr_a, corr_b])

        return findings

    def _filter_findings_in_scope(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        allowed_targets = [t.lower() for t in self.scope.targets]
        excluded_targets = [x.lower() for x in self.scope.exclusions]

        filtered: list[dict[str, Any]] = []
        for finding in findings:
            endpoint = str(finding.get("target_endpoint", "")).lower()
            host = urlparse(endpoint).hostname or ""

            in_allowed = any(host == t or host.endswith(f".{t}") for t in allowed_targets)
            in_excluded = any(host == x or host.endswith(f".{x}") for x in excluded_targets)

            if in_allowed and not in_excluded:
                filtered.append(finding)

        self.validation_log.append(
            f"scope_filter_applied: kept={len(filtered)} dropped={len(findings)-len(filtered)}"
        )
        return filtered

    def _target_context(self, target_type: str, fingerprint: dict[str, Any]) -> dict[str, Any]:
        return {
            "target_type": target_type,
            "program_type": self.metadata.get("program_type", "platform"),
            "industry": self.metadata.get("industry", "saas"),
            "tech_stack": fingerprint.get("tech_stack", []),
        }

    def _build_submission_report(
        self,
        *,
        target_type: str,
        enriched_findings: list[dict[str, Any]],
        correlation: dict[str, Any],
        dedup_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        total_estimated_payout = sum(
            int(f.get("payout", {}).get("estimated_payout_usd", 0)) for f in enriched_findings
        )

        severity_breakdown = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for finding in enriched_findings:
            level = str(finding.get("severity", {}).get("severity_level", "MEDIUM"))
            severity_breakdown[level] = severity_breakdown.get(level, 0) + 1

        return {
            "report_version": "1.0",
            "generated_at": datetime.now(UTC).isoformat(),
            "operation_mode": "detection_only",
            "target_type": target_type,
            "scope_id": self.scope.opportunity_id,
            "findings_total": len(enriched_findings),
            "severity_breakdown": severity_breakdown,
            "estimated_total_payout_usd": total_estimated_payout,
            "deduplication_metrics": dedup_metrics,
            "correlation_summary": {
                "cluster_count": correlation.get("cluster_count", 0),
                "multi_finding_clusters": correlation.get("multi_finding_clusters", 0),
            },
            "findings": enriched_findings,
            "submission_notes": [
                "All findings are detection-only and non-destructive.",
                "Scope validation executed before scanning workflow.",
                "Out-of-scope endpoints excluded from final report.",
            ],
        }

    def run_complete_workflow(self) -> WorkflowResult:
        phase_minutes: dict[str, int] = {}

        # PHASE 0: authorization
        self.validate_opportunity_authorization()
        phase_minutes["phase_0_authorization"] = 1

        # PHASE 1: fingerprinting
        hints = self.metadata.get("target_hints", {}) if isinstance(self.metadata.get("target_hints", {}), dict) else {}
        fingerprint = self._quick_fingerprint(self.scope.targets[0], hints)
        phase_minutes["phase_1_fingerprinting"] = int(self.metadata.get("fingerprinting_minutes", 3))

        # PHASE 2: classification
        archetype_hint = self.metadata.get("target_archetype")
        target_type = self.detection_model.classify_opportunity_for_detection(archetype_hint, hints=fingerprint)
        phase_minutes["phase_2_classification"] = int(self.metadata.get("classification_minutes", 1))

        # PHASE 3: prioritization
        scanning_plan = self.scanning_prioritizer.optimize_scanning_order(
            opportunity_scope=self.scope,
            target_archetype=target_type,
            target_hints=fingerprint,
            top_n=self.top_n_detection_playbooks,
        )
        scanning_plan_dict = scanning_plan.as_dict()
        self._ensure_detection_only_plan(scanning_plan_dict)
        phase_minutes["phase_3_prioritization"] = 1

        # PHASE 4: optimized detection (simulated, non-destructive)
        raw_findings = self._generate_raw_findings(scanning_plan_dict, target_type)
        scoped_findings = self._filter_findings_in_scope(raw_findings)

        detection_multiplier = {
            "early_stage_saas": 0.9,
            "established_saas": 0.95,
            "enterprise_multi_property": 1.0,
            "fintech_regulated": 1.05,
            "consumer_ecommerce": 0.92,
        }.get(target_type, 1.0)
        phase_minutes["phase_4_detection"] = int(round(scanning_plan.total_estimated_scan_time_minutes * detection_multiplier))

        # PHASE 5: deduplication
        dedup = self.deduplicator.deduplicate_findings(scoped_findings)
        dedup_groups = dedup.get("dedup_groups", [])
        dedup_metrics = dedup.get("metrics", {})
        canonical_findings = [g["canonical_finding"] for g in dedup_groups]
        phase_minutes["phase_5_deduplication"] = 1

        # PHASE 6: categorization + enrichment
        categorized = self.categorizer.categorize_findings(canonical_findings)
        target_context = self._target_context(target_type, fingerprint)
        enriched_findings: list[dict[str, Any]] = []
        for finding in categorized:
            enriched = self.severity_estimator.enrich_finding(finding, target_context)
            enriched["remediation_guidance"] = self.remediation_engine.generate_remediation_guidance(
                enriched,
                target_context,
            )
            enriched_findings.append(enriched)

        correlation = self.correlation_engine.correlate_findings(enriched_findings)
        phase_minutes["phase_6_enrichment"] = 2

        # PHASE 7: reporting
        submission_report = self._build_submission_report(
            target_type=target_type,
            enriched_findings=enriched_findings,
            correlation=correlation,
            dedup_metrics=dedup_metrics,
        )
        phase_minutes["phase_7_report_generation"] = 4

        total_minutes = sum(phase_minutes.values())
        baseline_minutes = 165
        reduction_percent = round(((baseline_minutes - total_minutes) / baseline_minutes) * 100, 2)

        self.workflow_metrics = {
            "phase_minutes": phase_minutes,
            "total_workflow_minutes": total_minutes,
            "baseline_workflow_minutes": baseline_minutes,
            "time_reduction_percent": reduction_percent,
            "raw_findings_count": len(scoped_findings),
            "deduplicated_findings_count": len(canonical_findings),
            "duplicate_reduction_percent": dedup_metrics.get("duplicate_percentage", 0.0),
            "detection_only_verified": True,
            "scope_validated": True,
        }

        return WorkflowResult(
            status="success",
            target_type=target_type,
            scope_validated=True,
            raw_findings_count=len(scoped_findings),
            deduplicated_findings_count=len(canonical_findings),
            duplicate_reduction_percent=float(dedup_metrics.get("duplicate_percentage", 0.0)),
            enriched_findings=enriched_findings,
            correlation_clusters=correlation,
            submission_ready_report=submission_report,
            workflow_metrics=self.workflow_metrics,
            validation_log=self.validation_log,
        )


def build_demo_scope(
    *,
    opportunity_id: str,
    platform: str,
    target: str,
    exclusions: list[str] | None = None,
    rules: list[str] | None = None,
) -> OpportunityScope:
    return OpportunityScope(
        opportunity_id=opportunity_id,
        platform=platform,
        active=True,
        targets=[target],
        authorization_verified=True,
        program_name="Demo Program",
        scope_source=f"{platform}_api",
        exclusions=exclusions or [],
        rules=rules or ["rate-limited testing only", "report findings responsibly"],
        downloaded_at=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
    )


def run_benchmark_suite() -> dict[str, Any]:
    scenarios = [
        {
            "name": "early_stage_saas",
            "scope": build_demo_scope(
                opportunity_id="h1-early-001",
                platform="hackerone",
                target="app.startup-example.com",
                exclusions=["admin.startup-example.com"],
            ),
            "metadata": {
                "target_archetype": "early_stage_saas",
                "industry": "saas",
                "program_type": "platform",
                "target_hints": {
                    "tech_stack": ["Node.js", "React", "PostgreSQL", "AWS"],
                    "web_server": "nginx",
                    "database": "postgresql",
                },
                "fingerprinting_minutes": 3,
                "classification_minutes": 1,
            },
        },
        {
            "name": "enterprise_multi_property",
            "scope": build_demo_scope(
                opportunity_id="bc-ent-001",
                platform="bugcrowd",
                target="portal.enterprise-example.com",
                exclusions=["internal.enterprise-example.com"],
            ),
            "metadata": {
                "target_archetype": "enterprise_multi_property",
                "industry": "enterprise",
                "program_type": "platform",
                "target_hints": {
                    "tech_stack": ["ASP.NET", "Oracle", "WAF", "SSO Federation"],
                    "web_server": "iis",
                    "database": "oracle",
                    "waf": "present",
                },
                "fingerprinting_minutes": 4,
                "classification_minutes": 2,
            },
        },
        {
            "name": "fintech_regulated",
            "scope": build_demo_scope(
                opportunity_id="int-fin-001",
                platform="intigriti",
                target="api.fintech-example.com",
                exclusions=["payments.fintech-example.com"],
            ),
            "metadata": {
                "target_archetype": "fintech_regulated",
                "industry": "fintech",
                "program_type": "direct",
                "target_hints": {
                    "tech_stack": ["Java", "Strong IAM", "HSM", "Transaction Controls"],
                    "web_server": "envoy",
                    "database": "postgresql",
                    "waf": "present",
                },
                "fingerprinting_minutes": 4,
                "classification_minutes": 2,
            },
        },
    ]

    benchmark_rows: list[ScenarioBenchmark] = []
    details: dict[str, Any] = {}

    for scenario in scenarios:
        orchestrator = BugBountyAutomationOrchestrator(
            opportunity_scope=scenario["scope"],
            opportunity_metadata=scenario["metadata"],
            allow_local_policy_override=True,
            top_n_detection_playbooks=10,
        )
        result = orchestrator.run_complete_workflow()

        metrics = result.workflow_metrics
        row = ScenarioBenchmark(
            scenario_name=scenario["name"],
            target_type=result.target_type,
            total_time_minutes=int(metrics["total_workflow_minutes"]),
            detection_time_minutes=int(metrics["phase_minutes"]["phase_4_detection"]),
            raw_findings=result.raw_findings_count,
            deduplicated_findings=result.deduplicated_findings_count,
            duplicate_reduction_percent=result.duplicate_reduction_percent,
            estimated_total_payout_usd=int(result.submission_ready_report["estimated_total_payout_usd"]),
            status=result.status,
        )
        benchmark_rows.append(row)
        details[scenario["name"]] = result.as_dict()

    avg_total = round(sum(r.total_time_minutes for r in benchmark_rows) / len(benchmark_rows), 2)
    avg_detection = round(sum(r.detection_time_minutes for r in benchmark_rows) / len(benchmark_rows), 2)
    avg_dedup = round(sum(r.duplicate_reduction_percent for r in benchmark_rows) / len(benchmark_rows), 2)

    baseline_detection_low, baseline_detection_high = 90, 120
    reduction_low = round(((baseline_detection_low - avg_detection) / baseline_detection_low) * 100, 2)
    reduction_high = round(((baseline_detection_high - avg_detection) / baseline_detection_high) * 100, 2)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "scenarios": [r.as_dict() for r in benchmark_rows],
        "aggregate": {
            "average_total_workflow_minutes": avg_total,
            "average_detection_phase_minutes": avg_detection,
            "average_deduplication_reduction_percent": avg_dedup,
            "average_detection_reduction_percent_vs_90m_baseline": reduction_low,
            "average_detection_reduction_percent_vs_120m_baseline": reduction_high,
            "detection_only_verified": True,
            "scope_enforcement_verified": True,
        },
        "details": details,
    }


__all__ = [
    "AuthorizationError",
    "DetectionPolicyError",
    "BugBountyAutomationOrchestrator",
    "WorkflowResult",
    "ScenarioBenchmark",
    "build_demo_scope",
    "run_benchmark_suite",
]
