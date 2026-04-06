"""
Simulation Fixture Library for K1 / Kai Platform
===================================================
Deterministic fixture builders for all simulation modes.

Provides:
  - Node-level state fixtures for graph_only
  - Tool result mock fixtures for tool_mock
  - Specialist output fixtures for DeepAgents simulation
  - Artifact fixtures with provenance tracking
  - Scenario packs for common mission patterns
  - Approval/escalation fixtures for governance testing

Fixtures are:
  - Typed and structured (not random strings)
  - Deterministic (same seed → same output)
  - Provenance-tracked (every fixture records its origin)
  - Scenario-aware (different profiles produce different data)

Fixture naming convention:
  fixture_{node_type}_{scenario}
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# -- Fixture provenance --------------------------------------------------------


@dataclass(frozen=True)
class FixtureProvenance:
    """Tracks the origin of a fixture value."""

    fixture_id: str
    fixture_type: str  # "node_output", "tool_result", "specialist_output", "artifact", "approval"
    profile: str  # fixture profile name
    scenario_pack: str = ""
    node_id: str = ""
    tool_name: str = ""
    specialist_type: str = ""
    deterministic_seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "fixture_id": self.fixture_id,
            "fixture_type": self.fixture_type,
            "profile": self.profile,
            "source": "simulation_fixture",
        }
        if self.scenario_pack:
            result["scenario_pack"] = self.scenario_pack
        if self.node_id:
            result["node_id"] = self.node_id
        if self.tool_name:
            result["tool_name"] = self.tool_name
        if self.specialist_type:
            result["specialist_type"] = self.specialist_type
        if self.deterministic_seed is not None:
            result["deterministic_seed"] = self.deterministic_seed
        return result


def _make_fixture_id(seed: int | None, category: str, key: str) -> str:
    """Generate a deterministic fixture ID from seed + category + key."""
    if seed is not None:
        raw = f"{seed}:{category}:{key}"
        return "fix-" + hashlib.sha256(raw.encode()).hexdigest()[:16]
    return "fix-" + uuid.uuid4().hex[:16]


# -- Node output fixtures ------------------------------------------------------


def fixture_governance_admission(
    profile: str = "default",
    scenario_pack: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    """Fixture for governance_admission node output."""
    fid = _make_fixture_id(seed, "governance_admission", profile)
    decision = "approved"  # default: mission passes governance gate
    if scenario_pack == "blocked_mission":
        decision = "blocked"

    return {
        "governance_decision": decision,
        "phase": "governance",
        "policy_events": [{
            "type": "governance_admission_simulated",
            "decision": decision,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "_fixture": FixtureProvenance(
                fixture_id=fid,
                fixture_type="node_output",
                profile=profile,
                scenario_pack=scenario_pack,
                node_id="governance_admission",
                deterministic_seed=seed,
            ).to_dict(),
        }],
    }


def fixture_mission_director(
    profile: str = "default",
    scenario_pack: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    """Fixture for mission_director node output."""
    fid = _make_fixture_id(seed, "mission_director", profile)
    return {
        "phase": "recon",
        "governance_decision": "",
        "phase_complete": False,
        "events": [{
            "event_type": "mission_directed",
            "target_phase": "recon",
            "_fixture_id": fid,
        }],
    }


def fixture_phase_coordinator(
    phase_name: str = "recon",
    profile: str = "default",
    scenario_pack: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    """Fixture for phase_coordinator node output."""
    fid = _make_fixture_id(seed, f"phase_coordinator_{phase_name}", profile)
    return {
        "phase": phase_name,
        "events": [{
            "event_type": "phase_coordinated",
            "phase": phase_name,
            "_fixture_id": fid,
        }],
    }


def fixture_specialist_cluster(
    cluster_name: str = "surface_scan",
    profile: str = "default",
    scenario_pack: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    """Fixture for specialist_cluster node output."""
    fid = _make_fixture_id(seed, f"specialist_cluster_{cluster_name}", profile)

    # Build scenario-aware artifacts
    artifacts = _build_cluster_artifacts(cluster_name, profile, scenario_pack, fid)
    findings = _build_cluster_findings(cluster_name, profile, scenario_pack, fid)

    # Determine artifact type for routing
    artifact_type = "recon_surface"
    if scenario_pack == "high_signal" or profile == "high_signal":
        artifact_type = "vulnerability_signal"
    elif cluster_name == "active_recon":
        artifact_type = "pentest_evidence"

    return {
        "artifacts": artifacts,
        "findings": findings,
        "last_artifact_type": artifact_type,
        "cluster_status": {
            cluster_name: {
                "phase": "recon",
                "success": True,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "_fixture_id": fid,
            }
        },
        "events": [{
            "event_type": "specialist_cluster_completed",
            "cluster_name": cluster_name,
            "artifact_count": len(artifacts),
            "finding_count": len(findings),
            "_fixture_id": fid,
        }],
    }


def fixture_evidence_analysis(
    profile: str = "default",
    scenario_pack: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    """Fixture for evidence_analysis node output."""
    fid = _make_fixture_id(seed, "evidence_analysis", profile)
    has_signal = scenario_pack in ("high_signal", "exploit_heavy") or profile == "high_signal"

    findings = []
    if has_signal:
        findings = [
            {
                "finding_id": _make_fixture_id(seed, "finding", "xss"),
                "severity": "high",
                "category": "xss",
                "title": "[SIMULATED] Reflected XSS in search parameter",
                "confidence": 0.85,
                "_fixture_id": fid,
            },
            {
                "finding_id": _make_fixture_id(seed, "finding", "sqli"),
                "severity": "critical",
                "category": "sql_injection",
                "title": "[SIMULATED] SQL injection in login form",
                "confidence": 0.72,
                "_fixture_id": fid,
            },
        ]
    else:
        findings = [
            {
                "finding_id": _make_fixture_id(seed, "finding", "info"),
                "severity": "info",
                "category": "information_disclosure",
                "title": "[SIMULATED] Server version header exposed",
                "confidence": 0.95,
                "_fixture_id": fid,
            },
        ]

    artifact_type = "vulnerability_signal" if has_signal else "recon_surface"

    return {
        "findings": findings,
        "last_artifact_type": artifact_type,
        "artifacts": [{
            "artifact_id": _make_fixture_id(seed, "artifact", "evidence"),
            "artifact_type": "evidence_summary",
            "content": {
                "finding_count": len(findings),
                "high_severity_count": sum(1 for f in findings if f.get("severity") in ("critical", "high")),
            },
            "_simulation": True,
            "_fixture_id": fid,
        }],
    }


def fixture_governance_review(
    profile: str = "default",
    scenario_pack: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    """Fixture for governance_review node output."""
    fid = _make_fixture_id(seed, "governance_review", profile)

    decision = "approved"
    approvals = []
    if scenario_pack in ("approval_heavy", "blocked_review"):
        decision = "pending"
        approval_id = _make_fixture_id(seed, "approval", "review")
        approvals = [{
            "approval_id": approval_id,
            "node_id": "governance_review",
            "reason": "[SIMULATED] Findings require governance approval",
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "_fixture_id": fid,
        }]

    return {
        "governance_decision": decision,
        "approvals_required": approvals,
        "policy_events": [{
            "type": f"governance_review_{'requested' if decision == 'pending' else 'passed'}",
            "node_id": "governance_review",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "_fixture_id": fid,
        }],
    }


def fixture_report_synthesis(
    profile: str = "default",
    scenario_pack: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    """Fixture for report_synthesis node output."""
    fid = _make_fixture_id(seed, "report_synthesis", profile)
    report_id = _make_fixture_id(seed, "artifact", "report")

    return {
        "final_report_id": report_id,
        "artifacts": [{
            "artifact_id": report_id,
            "artifact_type": "final_report",
            "content": {
                "title": "[SIMULATED] Mission Report",
                "sections": ["executive_summary", "findings", "recommendations"],
                "finding_count": 3,
            },
            "_simulation": True,
            "_fixture_id": fid,
        }],
    }


def fixture_handoff_liaison(
    profile: str = "default",
    scenario_pack: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    """Fixture for handoff_liaison node output."""
    fid = _make_fixture_id(seed, "handoff_liaison", profile)
    return {
        "completed": True,
        "progress": 1.0,
        "events": [{
            "event_type": "mission_handoff_completed",
            "_fixture_id": fid,
        }],
    }


# -- Tool result fixtures ------------------------------------------------------


def fixture_tool_result(
    tool_name: str,
    profile: str = "default",
    scenario_pack: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    """
    Return a mock tool result for tool_mock mode.

    Produces realistic-looking but clearly simulated tool output.
    """
    fid = _make_fixture_id(seed, f"tool_{tool_name}", profile)
    provenance = FixtureProvenance(
        fixture_id=fid,
        fixture_type="tool_result",
        profile=profile,
        scenario_pack=scenario_pack,
        tool_name=tool_name,
        deterministic_seed=seed,
    ).to_dict()

    # Tool-specific fixtures
    generators = _TOOL_FIXTURE_GENERATORS.get(tool_name)
    if generators:
        result = generators(profile, scenario_pack, seed)
        result["_fixture"] = provenance
        return result

    # Default tool fixture
    return {
        "tool_name": tool_name,
        "success": True,
        "output": f"[SIMULATED] {tool_name} completed successfully",
        "raw_output": "",
        "_simulation": True,
        "_fixture": provenance,
    }


def _fixture_nmap(profile: str, scenario_pack: str, seed: int | None) -> dict[str, Any]:
    """Mock nmap scan result."""
    ports = [
        {"port": 80, "protocol": "tcp", "state": "open", "service": "http"},
        {"port": 443, "protocol": "tcp", "state": "open", "service": "https"},
        {"port": 22, "protocol": "tcp", "state": "filtered", "service": "ssh"},
    ]
    if scenario_pack == "high_signal":
        ports.append({"port": 3306, "protocol": "tcp", "state": "open", "service": "mysql"})
        ports.append({"port": 6379, "protocol": "tcp", "state": "open", "service": "redis"})

    return {
        "tool_name": "nmap",
        "success": True,
        "output": f"[SIMULATED] Discovered {len(ports)} ports",
        "structured_output": {"hosts": [{"ip": "[SIMULATED]", "ports": ports}]},
        "_simulation": True,
    }


def _fixture_subfinder(profile: str, scenario_pack: str, seed: int | None) -> dict[str, Any]:
    """Mock subfinder subdomain discovery result."""
    subdomains = [
        "www.example.com", "api.example.com", "staging.example.com",
    ]
    if scenario_pack == "noisy_false_positive":
        subdomains.extend([
            "cdn.example.com", "old.example.com", "test.example.com",
            "dev.example.com", "internal.example.com",
        ])
    return {
        "tool_name": "subfinder",
        "success": True,
        "output": f"[SIMULATED] Discovered {len(subdomains)} subdomains",
        "structured_output": {"subdomains": subdomains},
        "_simulation": True,
    }


def _fixture_nuclei(profile: str, scenario_pack: str, seed: int | None) -> dict[str, Any]:
    """Mock nuclei vulnerability scan result."""
    findings = []
    if scenario_pack == "high_signal":
        findings = [
            {"severity": "critical", "template": "cve-2024-0001", "matched_at": "[SIMULATED]"},
            {"severity": "high", "template": "xss-reflected", "matched_at": "[SIMULATED]"},
        ]
    elif scenario_pack == "noisy_false_positive":
        findings = [
            {"severity": "info", "template": "tech-detect", "matched_at": "[SIMULATED]"},
            {"severity": "low", "template": "header-missing", "matched_at": "[SIMULATED]"},
        ]
    return {
        "tool_name": "nuclei",
        "success": True,
        "output": f"[SIMULATED] Found {len(findings)} results",
        "structured_output": {"findings": findings},
        "_simulation": True,
    }


def _fixture_httpx(profile: str, scenario_pack: str, seed: int | None) -> dict[str, Any]:
    """Mock httpx probe result."""
    return {
        "tool_name": "httpx",
        "success": True,
        "output": "[SIMULATED] HTTP probe completed",
        "structured_output": {
            "results": [
                {"url": "https://example.com", "status_code": 200, "title": "Example Domain"},
                {"url": "https://api.example.com", "status_code": 200, "title": "API"},
            ]
        },
        "_simulation": True,
    }


_TOOL_FIXTURE_GENERATORS: dict[str, Any] = {
    "nmap": _fixture_nmap,
    "subfinder": _fixture_subfinder,
    "nuclei": _fixture_nuclei,
    "httpx": _fixture_httpx,
}


# -- Specialist output fixtures ------------------------------------------------


def fixture_specialist_output(
    specialist_type: str,
    profile: str = "default",
    scenario_pack: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    """
    Return a mock specialist DeepAgent output for simulation.

    Each specialist type produces a structurally appropriate fixture.
    """
    fid = _make_fixture_id(seed, f"specialist_{specialist_type}", profile)
    provenance = FixtureProvenance(
        fixture_id=fid,
        fixture_type="specialist_output",
        profile=profile,
        scenario_pack=scenario_pack,
        specialist_type=specialist_type,
        deterministic_seed=seed,
    ).to_dict()

    generators = _SPECIALIST_FIXTURE_GENERATORS.get(specialist_type)
    if generators:
        result = generators(profile, scenario_pack, seed)
        result["_fixture"] = provenance
        return result

    return {
        "text": f"[SIMULATED] {specialist_type} analysis complete",
        "success": True,
        "_simulation": True,
        "_fixture": provenance,
    }


def _fixture_evidence_analyst(profile: str, scenario_pack: str, seed: int | None) -> dict[str, Any]:
    return {
        "text": "[SIMULATED] Evidence analysis identified potential vulnerabilities",
        "success": True,
        "artifacts_produced": [{
            "artifact_id": _make_fixture_id(seed, "artifact", "evidence_analysis"),
            "artifact_type": "evidence_summary",
            "content": {"finding_count": 3 if scenario_pack == "high_signal" else 1},
        }],
        "_simulation": True,
    }


def _fixture_triage_specialist(profile: str, scenario_pack: str, seed: int | None) -> dict[str, Any]:
    return {
        "text": "[SIMULATED] Triage complete — findings categorized and prioritized",
        "success": True,
        "severity": "high" if scenario_pack == "high_signal" else "info",
        "category": "xss" if scenario_pack == "high_signal" else "information_disclosure",
        "confidence": 0.85,
        "_simulation": True,
    }


def _fixture_exploit_assessor(profile: str, scenario_pack: str, seed: int | None) -> dict[str, Any]:
    exploitable = scenario_pack == "exploit_heavy"
    return {
        "text": f"[SIMULATED] Exploit assessment — {'exploitable' if exploitable else 'not exploitable'}",
        "success": True,
        "exploitable": exploitable,
        "confidence": 0.7 if exploitable else 0.3,
        "_simulation": True,
    }


def _fixture_report_synthesizer(profile: str, scenario_pack: str, seed: int | None) -> dict[str, Any]:
    return {
        "text": "[SIMULATED] Report synthesized from all findings",
        "success": True,
        "artifacts_produced": [{
            "artifact_id": _make_fixture_id(seed, "artifact", "report"),
            "artifact_type": "final_report",
            "content": {"title": "[SIMULATED] Vulnerability Assessment Report"},
        }],
        "_simulation": True,
    }


def _fixture_knowledge_curator(profile: str, scenario_pack: str, seed: int | None) -> dict[str, Any]:
    return {
        "text": "[SIMULATED] Knowledge lessons extracted",
        "success": True,
        "knowledge_lessons_generated": [{
            "lesson_id": _make_fixture_id(seed, "lesson", "curated"),
            "lesson_type": "technique_discovery",
            "content": "[SIMULATED] New technique identified",
        }],
        "_simulation": True,
    }


_SPECIALIST_FIXTURE_GENERATORS: dict[str, Any] = {
    "evidence_analyst": _fixture_evidence_analyst,
    "triage_specialist": _fixture_triage_specialist,
    "exploit_assessor": _fixture_exploit_assessor,
    "report_synthesizer": _fixture_report_synthesizer,
    "knowledge_curator": _fixture_knowledge_curator,
}


# -- Approval / governance fixtures -------------------------------------------


def fixture_approval_decision(
    approval_id: str = "",
    scenario_pack: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    """Fixture for approval resolution."""
    fid = _make_fixture_id(seed, "approval", approval_id or "default")
    decision = "approved"
    if scenario_pack == "blocked_review":
        decision = "denied"

    return {
        "approval_id": approval_id or fid,
        "decision": decision,
        "resolved_by": "simulation_fixture",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "_fixture_id": fid,
    }


def fixture_plan_patch(
    scenario_pack: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    """Fixture for an adaptive plan patch proposal."""
    fid = _make_fixture_id(seed, "plan_patch", "proposal")
    accepted = scenario_pack != "rejected_patch"

    return {
        "patch_id": fid,
        "change_type": "add_scan_step",
        "description": "[SIMULATED] Proposed additional scanning phase",
        "accepted": accepted,
        "_fixture_id": fid,
    }


# -- Scenario packs ------------------------------------------------------------


SCENARIO_PACKS: dict[str, dict[str, Any]] = {
    "default": {
        "description": "Standard passive recon with low-signal results",
        "fixture_profile": "default",
    },
    "high_signal": {
        "description": "Mission discovers high/critical severity vulnerabilities",
        "fixture_profile": "high_signal",
    },
    "noisy_false_positive": {
        "description": "Many results but mostly info/low — tests signal filtering",
        "fixture_profile": "noisy",
    },
    "approval_heavy": {
        "description": "Multiple approval gates triggered — tests governance flow",
        "fixture_profile": "default",
    },
    "blocked_mission": {
        "description": "Mission blocked at governance admission — tests denial path",
        "fixture_profile": "default",
    },
    "exploit_heavy": {
        "description": "Exploit assessment phase dominates — tests deep analysis path",
        "fixture_profile": "exploit_focused",
    },
    "report_heavy": {
        "description": "Large report synthesis with many findings",
        "fixture_profile": "report_focused",
    },
    "blocked_review": {
        "description": "Governance review blocks findings — tests rejection path",
        "fixture_profile": "default",
    },
    "rejected_patch": {
        "description": "Adaptive plan patch is rejected — tests patch rejection path",
        "fixture_profile": "default",
    },
}


# -- Fixture registry ----------------------------------------------------------


class FixtureRegistry:
    """
    Central registry for simulation fixtures.

    Provides type-safe access to fixtures with fallback behavior
    controlled by fixture_strictness config.
    """

    def __init__(
        self,
        profile: str = "default",
        scenario_pack: str = "",
        seed: int | None = None,
        strictness: str = "lenient",
    ) -> None:
        self._profile = profile
        self._scenario_pack = scenario_pack
        self._seed = seed
        self._strictness = strictness

    def get_node_fixture(self, node_id: str) -> dict[str, Any]:
        """Get fixture output for a graph node."""
        generators: dict[str, Any] = {
            "governance_admission": fixture_governance_admission,
            "mission_director": fixture_mission_director,
            "GovernanceDirector": fixture_governance_admission,
            "MissionDirector": fixture_mission_director,
            "PhaseCoordinator": lambda **kw: fixture_phase_coordinator(**kw),
            "phase_coordinator_recon": lambda **kw: fixture_phase_coordinator(phase_name="recon", **kw),
            "SurfaceMapper": lambda **kw: fixture_specialist_cluster(cluster_name="surface_scan", **kw),
            "specialist_cluster_surface_scan": lambda **kw: fixture_specialist_cluster(cluster_name="surface_scan", **kw),
            "ReconSpecialist": lambda **kw: fixture_specialist_cluster(cluster_name="active_recon", **kw),
            "specialist_cluster_active_recon": lambda **kw: fixture_specialist_cluster(cluster_name="active_recon", **kw),
            "OSINTIntelligenceAgent": lambda **kw: fixture_specialist_cluster(cluster_name="osint", **kw),
            "specialist_cluster_osintintelligenceagent": lambda **kw: fixture_specialist_cluster(cluster_name="osint", **kw),
            "DarkWebIntelAgent": lambda **kw: fixture_specialist_cluster(cluster_name="darkweb", **kw),
            "specialist_cluster_darkwebintelagent": lambda **kw: fixture_specialist_cluster(cluster_name="darkweb", **kw),
            "SecretScannerAgent": lambda **kw: fixture_specialist_cluster(cluster_name="secrets", **kw),
            "specialist_cluster_secretscanneragent": lambda **kw: fixture_specialist_cluster(cluster_name="secrets", **kw),
            "ContentDiscoveryAgent": lambda **kw: fixture_specialist_cluster(cluster_name="content_discovery", **kw),
            "specialist_cluster_contentdiscoveryagent": lambda **kw: fixture_specialist_cluster(cluster_name="content_discovery", **kw),
            "VulnerabilityAgent": lambda **kw: fixture_specialist_cluster(cluster_name="vulnerability_validation", **kw),
            "specialist_cluster_vulnerabilityagent": lambda **kw: fixture_specialist_cluster(cluster_name="vulnerability_validation", **kw),
            "APISecurityAgent": lambda **kw: fixture_specialist_cluster(cluster_name="api_security", **kw),
            "specialist_cluster_apisecurityagent": lambda **kw: fixture_specialist_cluster(cluster_name="api_security", **kw),
            "FaradayCoordinatorAgent": lambda **kw: fixture_specialist_cluster(cluster_name="faraday_aggregation", **kw),
            "specialist_cluster_faradaycoordinatoragent": lambda **kw: fixture_specialist_cluster(cluster_name="faraday_aggregation", **kw),
            "EvidenceAnalyst": fixture_evidence_analysis,
            "evidence_analysis": fixture_evidence_analysis,
            "governance_review": fixture_governance_review,
            "report_synthesis": fixture_report_synthesis,
            "ReportSynthesisAgent": fixture_report_synthesis,
            "handoff_liaison": fixture_handoff_liaison,
            "HandoffLiaison": fixture_handoff_liaison,
        }

        gen = generators.get(node_id)
        if gen is None:
            return self._handle_missing("node_output", node_id)

        return gen(
            profile=self._profile,
            scenario_pack=self._scenario_pack,
            seed=self._seed,
        )

    def get_tool_fixture(self, tool_name: str) -> dict[str, Any]:
        """Get mock tool result."""
        return fixture_tool_result(
            tool_name=tool_name,
            profile=self._profile,
            scenario_pack=self._scenario_pack,
            seed=self._seed,
        )

    def get_specialist_fixture(self, specialist_type: str) -> dict[str, Any]:
        """Get mock specialist output."""
        return fixture_specialist_output(
            specialist_type=specialist_type,
            profile=self._profile,
            scenario_pack=self._scenario_pack,
            seed=self._seed,
        )

    def _handle_missing(self, fixture_type: str, key: str) -> dict[str, Any]:
        """Handle missing fixture based on strictness."""
        msg = f"No fixture found for {fixture_type}:{key} (profile={self._profile})"
        if self._strictness == "strict":
            raise KeyError(msg)
        if self._strictness == "warn":
            logger.warning(msg)
        return {
            "events": [{"event_type": "fixture_missing", "key": key, "type": fixture_type}],
            "_fixture_missing": True,
        }


# -- Internal helpers ----------------------------------------------------------


def _build_cluster_artifacts(
    cluster_name: str,
    profile: str,
    scenario_pack: str,
    fixture_id: str,
) -> list[dict[str, Any]]:
    """Build cluster artifacts based on scenario."""
    aid = _make_fixture_id(None, "artifact", cluster_name)
    artifacts = [{
        "artifact_id": aid,
        "artifact_type": "scan_result" if "scan" in cluster_name else "recon_result",
        "producer": cluster_name,
        "content": {"type": cluster_name, "result_count": 5},
        "_simulation": True,
        "_fixture_id": fixture_id,
    }]
    return artifacts


def _build_cluster_findings(
    cluster_name: str,
    profile: str,
    scenario_pack: str,
    fixture_id: str,
) -> list[dict[str, Any]]:
    """Build cluster findings based on scenario."""
    if scenario_pack == "high_signal" or profile == "high_signal":
        return [{
            "finding_id": _make_fixture_id(None, "finding", cluster_name),
            "severity": "high",
            "category": "vulnerability",
            "title": f"[SIMULATED] {cluster_name} finding",
            "_fixture_id": fixture_id,
        }]
    return []
