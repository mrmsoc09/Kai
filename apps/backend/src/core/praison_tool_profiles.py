"""
K1 Tool and Prompt Profiles for Adaptive Execution
=====================================================
Pre-approved tool configuration variants and prompt templates that agents
can select from during bounded adaptive execution.

Profile concepts:
  passive_recon         — stealth, no active probing
  balanced_recon        — mix of passive and safe active scanning
  high_recall           — broad scope, accept noise for coverage
  high_precision        — narrow scope, reduce false positives
  conservative_analysis — careful analysis, low-risk conclusions
  aggressive_validation — deeper validation of findings, Band 2 tools
  stealth_preferred     — minimize detectable footprint
  time_boxed            — strict time limits, prioritize speed

Each profile is a frozen dataclass (ToolProfile or PromptProfile from
praison_adaptive.py) pre-defined here for consistent reuse across missions.

Security:
  - Profiles are defined at module level (not by agents at runtime)
  - Agents SELECT among profiles; they cannot CREATE new ones
  - Profile selection is validated by validate_plan_patch()
  - High-risk profiles trigger governance escalation
"""

from __future__ import annotations

from apps.backend.src.core.praison_adaptive import PromptProfile, ToolProfile


# ── Tool Profiles ────────────────────────────────────────────────────────────

PASSIVE_RECON = ToolProfile(
    profile_id="tp_passive_recon",
    tool_id="subfinder",
    profile_name="passive_recon",
    parameters={"passive_only": True, "rate_limit": 10, "timeout": 300},
    description="Passive reconnaissance only. No active probing. DNS, CT, WHOIS.",
    risk_level="low",
)

BALANCED_RECON = ToolProfile(
    profile_id="tp_balanced_recon",
    tool_id="httpx",
    profile_name="balanced_recon",
    parameters={"threads": 25, "follow_redirects": True, "timeout": 30},
    description="Balanced active recon. HTTP probing with moderate rate. Band 1.",
    risk_level="low",
)

HIGH_RECALL_SCAN = ToolProfile(
    profile_id="tp_high_recall",
    tool_id="nuclei",
    profile_name="high_recall",
    parameters={
        "severity": "info,low,medium,high,critical",
        "rate_limit": 50,
        "bulk_size": 25,
        "concurrency": 10,
    },
    description="Broad nuclei scan for maximum coverage. Accepts higher noise.",
    risk_level="medium",
)

HIGH_PRECISION_SCAN = ToolProfile(
    profile_id="tp_high_precision",
    tool_id="nuclei",
    profile_name="high_precision",
    parameters={
        "severity": "high,critical",
        "rate_limit": 25,
        "bulk_size": 10,
        "concurrency": 5,
        "validate": True,
    },
    description="Precision nuclei scan. High/critical only, with validation.",
    risk_level="low",
)

AGGRESSIVE_VALIDATION = ToolProfile(
    profile_id="tp_aggressive_validation",
    tool_id="ffuf",
    profile_name="aggressive_validation",
    parameters={
        "threads": 40,
        "rate_limit": 100,
        "recursion": True,
        "recursion_depth": 2,
    },
    description="Deep fuzzing validation. Band 2 tool — requires governance approval.",
    risk_level="high",
)

STEALTH_PREFERRED = ToolProfile(
    profile_id="tp_stealth_preferred",
    tool_id="nmap",
    profile_name="stealth_preferred",
    parameters={
        "scan_type": "SYN",
        "timing": "T2",
        "rate_limit": 5,
        "decoy": True,
    },
    description="Low-footprint nmap scan. SYN stealth with T2 timing.",
    risk_level="medium",
)

TIME_BOXED_SCAN = ToolProfile(
    profile_id="tp_time_boxed",
    tool_id="katana",
    profile_name="time_boxed",
    parameters={
        "depth": 2,
        "concurrency": 20,
        "timeout": 120,
        "max_duration": 300,
    },
    description="Time-boxed crawling. Strict 5-minute limit, shallow depth.",
    risk_level="low",
)

CONSERVATIVE_ANALYSIS = ToolProfile(
    profile_id="tp_conservative_analysis",
    tool_id="severity_classify",
    profile_name="conservative_analysis",
    parameters={
        "confidence_threshold": 0.8,
        "require_evidence": True,
        "max_false_positive_rate": 0.05,
    },
    description="Conservative analysis. High confidence threshold, evidence required.",
    risk_level="low",
)


# ── All tool profiles indexed by profile_id ──────────────────────────────────

ALL_TOOL_PROFILES: dict[str, ToolProfile] = {
    p.profile_id: p
    for p in [
        PASSIVE_RECON,
        BALANCED_RECON,
        HIGH_RECALL_SCAN,
        HIGH_PRECISION_SCAN,
        AGGRESSIVE_VALIDATION,
        STEALTH_PREFERRED,
        TIME_BOXED_SCAN,
        CONSERVATIVE_ANALYSIS,
    ]
}


def get_tool_profile(profile_id: str) -> ToolProfile | None:
    """Look up a tool profile by ID. Returns None if not found."""
    return ALL_TOOL_PROFILES.get(profile_id)


def tool_profiles_for_agent(agent_id: str) -> list[ToolProfile]:
    """
    Return the list of tool profiles applicable to a given agent.
    Default mapping based on agent role in the taxonomy.
    """
    _AGENT_PROFILES: dict[str, list[str]] = {
        "SurfaceMapper": ["tp_passive_recon", "tp_balanced_recon", "tp_stealth_preferred"],
        "ReconSpecialist": [
            "tp_balanced_recon",
            "tp_high_recall",
            "tp_high_precision",
            "tp_stealth_preferred",
            "tp_time_boxed",
        ],
        "EvidenceAnalyst": ["tp_conservative_analysis", "tp_high_precision"],
        "ReportSynthesisAgent": ["tp_conservative_analysis"],
        "VulnerabilityTriageAgent": [
            "tp_high_precision",
            "tp_conservative_analysis",
            "tp_aggressive_validation",
        ],
    }
    profile_ids = _AGENT_PROFILES.get(agent_id, [])
    return [ALL_TOOL_PROFILES[pid] for pid in profile_ids if pid in ALL_TOOL_PROFILES]


# ── Prompt Profiles ──────────────────────────────────────────────────────────

THOROUGH_ANALYSIS = PromptProfile(
    profile_id="pp_thorough_analysis",
    profile_name="thorough_analysis",
    template=(
        "You are {persona}. Perform an exhaustive analysis of all available data.\n"
        "Phase: {phase}. Mission: {mission_id}.\n"
        "Examine every artifact carefully. Flag ALL potential issues, even low-confidence ones.\n"
        "Prioritize completeness over speed. Document your reasoning for each finding."
    ),
    context_keys=("persona", "phase", "mission_id"),
    description="Deep, exhaustive analysis. Prioritizes completeness.",
)

FAST_TRIAGE = PromptProfile(
    profile_id="pp_fast_triage",
    profile_name="fast_triage",
    template=(
        "You are {persona}. Perform rapid triage of findings.\n"
        "Phase: {phase}. Mission: {mission_id}.\n"
        "Focus on critical and high severity findings ONLY. Skip info/low.\n"
        "Spend no more than 30 seconds per finding. Output structured JSON immediately."
    ),
    context_keys=("persona", "phase", "mission_id"),
    description="Speed-optimized triage. Critical/high only.",
)

DEEP_VALIDATION = PromptProfile(
    profile_id="pp_deep_validation",
    profile_name="deep_validation",
    template=(
        "You are {persona}. Validate each finding with maximum rigor.\n"
        "Phase: {phase}. Mission: {mission_id}.\n"
        "For each finding:\n"
        "  1. Verify the evidence chain is complete\n"
        "  2. Check for false positive indicators\n"
        "  3. Assess exploitability with concrete reasoning\n"
        "  4. Assign confidence: high (>90%), medium (60-90%), low (<60%)\n"
        "Reject any finding with insufficient evidence."
    ),
    context_keys=("persona", "phase", "mission_id"),
    description="Rigorous finding validation. Rejects weak evidence.",
)

STEALTH_RECON = PromptProfile(
    profile_id="pp_stealth_recon",
    profile_name="stealth_recon",
    template=(
        "You are {persona}. Execute reconnaissance with minimal footprint.\n"
        "Phase: {phase}. Mission: {mission_id}.\n"
        "RULES:\n"
        "  - Use ONLY passive techniques first (DNS, CT logs, WHOIS)\n"
        "  - Active probing ONLY if passive yields insufficient coverage\n"
        "  - Rate-limit all active probes to avoid triggering WAF/IDS\n"
        "  - Log justification for every active technique used"
    ),
    context_keys=("persona", "phase", "mission_id"),
    description="Stealth-first reconnaissance approach.",
)

REPORT_SUBMISSION = PromptProfile(
    profile_id="pp_report_submission",
    profile_name="report_submission",
    template=(
        "You are {persona}. Synthesize validated findings into a submission-ready report.\n"
        "Phase: {phase}. Mission: {mission_id}.\n"
        "For each finding include:\n"
        "  - Title, severity (CVSS where applicable), target\n"
        "  - Clear reproduction steps (numbered, executable)\n"
        "  - Impact statement (business + technical)\n"
        "  - Remediation recommendation\n"
        "  - Supporting evidence (screenshots, request/response pairs)\n"
        "Output in platform-standard JSON format."
    ),
    context_keys=("persona", "phase", "mission_id"),
    description="Submission-ready report synthesis.",
)

COVERAGE_MAXIMIZER = PromptProfile(
    profile_id="pp_coverage_maximizer",
    profile_name="coverage_maximizer",
    template=(
        "You are {persona}. Maximize attack surface coverage.\n"
        "Phase: {phase}. Mission: {mission_id}.\n"
        "Enumerate ALL:\n"
        "  - Subdomains (passive + active brute)\n"
        "  - Live hosts and open ports\n"
        "  - Technology stack fingerprints\n"
        "  - API endpoints and parameters\n"
        "  - Login pages and admin panels\n"
        "Breadth over depth. Annotate each discovered asset with confidence level."
    ),
    context_keys=("persona", "phase", "mission_id"),
    description="Maximum coverage enumeration strategy.",
)


# ── All prompt profiles indexed by profile_id ────────────────────────────────

ALL_PROMPT_PROFILES: dict[str, PromptProfile] = {
    p.profile_id: p
    for p in [
        THOROUGH_ANALYSIS,
        FAST_TRIAGE,
        DEEP_VALIDATION,
        STEALTH_RECON,
        REPORT_SUBMISSION,
        COVERAGE_MAXIMIZER,
    ]
}


def get_prompt_profile(profile_id: str) -> PromptProfile | None:
    """Look up a prompt profile by ID. Returns None if not found."""
    return ALL_PROMPT_PROFILES.get(profile_id)


def prompt_profiles_for_agent(agent_id: str) -> list[PromptProfile]:
    """Return the list of prompt profiles applicable to a given agent."""
    _AGENT_PROFILES: dict[str, list[str]] = {
        "SurfaceMapper": ["pp_stealth_recon", "pp_coverage_maximizer"],
        "ReconSpecialist": ["pp_stealth_recon", "pp_coverage_maximizer"],
        "EvidenceAnalyst": ["pp_thorough_analysis", "pp_fast_triage", "pp_deep_validation"],
        "ReportSynthesisAgent": ["pp_report_submission", "pp_thorough_analysis"],
        "GovernanceDirector": ["pp_thorough_analysis"],
        "VulnerabilityTriageAgent": ["pp_fast_triage", "pp_deep_validation"],
    }
    profile_ids = _AGENT_PROFILES.get(agent_id, [])
    return [ALL_PROMPT_PROFILES[pid] for pid in profile_ids if pid in ALL_PROMPT_PROFILES]
