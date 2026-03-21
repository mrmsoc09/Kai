"""
Report Quality Engine — Structured Report Templates
=====================================================
Provides structured, submission-ready report generation for bug bounty findings.

Each report section is generated deterministically from structured finding data.
LLM is NOT called here — this module provides templates and formatting logic.
LLM-generated prose is accepted as input (from ReportSynthesisAgent) and
embedded into the structured template.

Report structure (all sections required for submission):
  1. Title           — concise, actionable
  2. Severity        — CVSS-aligned with reasoning
  3. Affected Asset  — URL, endpoint, parameter
  4. Summary         — 2-3 sentence executive summary
  5. Reproduction    — numbered steps to reproduce
  6. Request/Response samples — raw HTTP evidence
  7. Impact          — business impact explanation
  8. Remediation     — actionable fix guidance
  9. References      — CVE, CWE, OWASP links (if applicable)

Usage::

    template = ReportTemplate(finding_data)
    report = template.render()
    score = report.quality_score
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ReproductionStep:
    """A single step in the reproduction walkthrough."""

    step_number: int
    description: str
    detail: str | None = None  # command, URL, or request snippet


@dataclass
class HttpSample:
    """Raw HTTP request/response pair as evidence."""

    request: str  # raw HTTP request text
    response: str  # raw HTTP response text (may be truncated)
    note: str | None = None


@dataclass
class FindingData:
    """All data required to render a complete submission report."""

    finding_id: str
    title: str
    severity: str  # critical, high, medium, low
    cvss_score: float | None  # 0.0–10.0
    cvss_vector: str | None  # e.g. CVSS:3.1/AV:N/AC:L/...
    vuln_type: str  # xss, sqli, ssrf, ...
    cwe_id: str | None  # e.g. CWE-79
    cve_ids: list[str] = field(default_factory=list)

    # Asset
    affected_url: str = ""
    affected_parameter: str | None = None
    affected_component: str | None = None

    # Narrative (provided by LLM or operator)
    summary: str = ""
    impact: str = ""
    remediation: str = ""

    # Structured reproduction
    reproduction_steps: list[ReproductionStep] = field(default_factory=list)

    # Evidence
    http_samples: list[HttpSample] = field(default_factory=list)

    # Validation results (from VulnerabilityValidator)
    validated: bool = False
    validation_confidence: float = 0.0
    validation_evidence: list[str] = field(default_factory=list)

    # Metadata
    program_name: str | None = None
    researcher_notes: str | None = None


@dataclass
class RenderedReport:
    """A fully rendered submission report."""

    finding_id: str
    title: str
    severity: str
    markdown: str  # full markdown body
    quality_score: float  # 0.0–1.0
    missing_sections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "severity": self.severity,
            "quality_score": round(self.quality_score, 4),
            "missing_sections": self.missing_sections,
            "warnings": self.warnings,
            "markdown": self.markdown,
        }


# ---------------------------------------------------------------------------
# CVSS reasoning helpers
# ---------------------------------------------------------------------------

_SEVERITY_CVSS_RANGES: dict[str, tuple[float, float]] = {
    "critical": (9.0, 10.0),
    "high": (7.0, 8.9),
    "medium": (4.0, 6.9),
    "low": (0.1, 3.9),
}

_OWASP_MAP: dict[str, str] = {
    "xss": "https://owasp.org/www-community/attacks/xss/",
    "reflected_xss": "https://owasp.org/www-community/attacks/xss/",
    "sqli": "https://owasp.org/www-community/attacks/SQL_Injection",
    "sql_injection": "https://owasp.org/www-community/attacks/SQL_Injection",
    "ssrf": "https://owasp.org/www-community/attacks/Server_Side_Request_Forgery",
    "csrf": "https://owasp.org/www-community/attacks/csrf",
    "xxe": "https://owasp.org/www-community/vulnerabilities/XML_External_Entity_(XXE)_Processing",
    "ssti": "https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/07-Input_Validation_Testing/18-Testing_for_Server_Side_Template_Injection",
    "path_traversal": "https://owasp.org/www-community/attacks/Path_Traversal",
    "lfi": "https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/07-Input_Validation_Testing/11.1-Testing_for_Local_File_Inclusion",
    "rce": "https://owasp.org/www-community/attacks/Code_Injection",
    "idor": "https://owasp.org/www-community/attacks/Insecure_Direct_Object_Reference",
    "open_redirect": "https://owasp.org/www-community/attacks/Unvalidated_Redirects_and_Forwards_Cheat_Sheet",
}

_CWE_NAMES: dict[str, str] = {
    "CWE-79": "Improper Neutralization of Input During Web Page Generation (XSS)",
    "CWE-89": "Improper Neutralization of Special Elements used in an SQL Command",
    "CWE-918": "Server-Side Request Forgery (SSRF)",
    "CWE-22": "Improper Limitation of a Pathname to a Restricted Directory (Path Traversal)",
    "CWE-611": "Improper Restriction of XML External Entity Reference (XXE)",
    "CWE-94": "Improper Control of Generation of Code (Code Injection)",
    "CWE-862": "Missing Authorization",
    "CWE-284": "Improper Access Control",
    "CWE-352": "Cross-Site Request Forgery (CSRF)",
    "CWE-601": "URL Redirection to Untrusted Site (Open Redirect)",
}


def _cvss_severity_check(severity: str, cvss_score: float | None) -> str | None:
    """Returns a warning if CVSS score doesn't match stated severity."""
    if cvss_score is None:
        return None
    lo, hi = _SEVERITY_CVSS_RANGES.get(severity.lower(), (0, 10))
    if not (lo <= cvss_score <= hi):
        return f"CVSS score {cvss_score} does not match stated severity '{severity}' (expected {lo}–{hi})"
    return None


# ---------------------------------------------------------------------------
# Report template renderer
# ---------------------------------------------------------------------------


class ReportTemplate:
    """
    Renders a structured Markdown report from FindingData.

    All required sections are checked; missing or thin sections reduce
    the quality_score and populate missing_sections/warnings.
    """

    def __init__(self, data: FindingData) -> None:
        self._data = data

    def render(self) -> RenderedReport:
        d = self._data
        sections: list[str] = []
        missing: list[str] = []
        warnings: list[str] = []

        # --- Title ---
        sections.append(f"# {d.title}\n")

        # --- Metadata block ---
        sections.append(_render_metadata(d))

        # --- Summary ---
        if d.summary.strip():
            sections.append("## Summary\n\n" + d.summary.strip() + "\n")
        else:
            missing.append("summary")
            sections.append("## Summary\n\n_No summary provided._\n")

        # --- Affected asset ---
        sections.append(_render_asset(d))

        # --- Severity & CVSS reasoning ---
        sections.append(_render_severity(d, warnings))

        # --- Reproduction steps ---
        if d.reproduction_steps:
            sections.append(_render_reproduction(d.reproduction_steps))
        else:
            missing.append("reproduction_steps")
            sections.append("## Steps to Reproduce\n\n_No reproduction steps provided._\n")

        # --- HTTP samples ---
        if d.http_samples:
            sections.append(_render_http_samples(d.http_samples))
        else:
            missing.append("http_samples")
            warnings.append("No HTTP request/response samples provided — required by most programs")

        # --- Impact ---
        if d.impact.strip():
            sections.append("## Impact\n\n" + d.impact.strip() + "\n")
        else:
            missing.append("impact")
            sections.append("## Impact\n\n_No impact description provided._\n")

        # --- Remediation ---
        if d.remediation.strip():
            sections.append("## Suggested Remediation\n\n" + d.remediation.strip() + "\n")
        else:
            missing.append("remediation")
            sections.append("## Suggested Remediation\n\n_No remediation guidance provided._\n")

        # --- Validation evidence ---
        if d.validated and d.validation_evidence:
            ev_lines = "\n".join(f"- {e}" for e in d.validation_evidence)
            sections.append(f"## Validation Evidence\n\nThis finding was validated automatically:\n\n{ev_lines}\n")

        # --- References ---
        sections.append(_render_references(d))

        # --- Quality score ---
        quality = _compute_quality_score(d, missing, warnings)

        markdown = "\n".join(sections)
        return RenderedReport(
            finding_id=d.finding_id,
            title=d.title,
            severity=d.severity,
            markdown=markdown,
            quality_score=quality,
            missing_sections=missing,
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _render_metadata(d: FindingData) -> str:
    lines = [
        "| Field | Value |",
        "|-------|-------|",
        f"| **Severity** | {d.severity.upper()} |",
        f"| **Type** | {d.vuln_type} |",
    ]
    if d.cvss_score is not None:
        lines.append(f"| **CVSS Score** | {d.cvss_score} |")
    if d.cvss_vector:
        lines.append(f"| **CVSS Vector** | `{d.cvss_vector}` |")
    if d.cwe_id:
        cwe_name = _CWE_NAMES.get(d.cwe_id, "")
        label = f"{d.cwe_id}" + (f" — {cwe_name}" if cwe_name else "")
        lines.append(f"| **CWE** | {label} |")
    if d.cve_ids:
        lines.append(f"| **CVEs** | {', '.join(d.cve_ids)} |")
    if d.program_name:
        lines.append(f"| **Program** | {d.program_name} |")
    if d.validated:
        lines.append(f"| **Validated** | Yes (confidence: {d.validation_confidence:.0%}) |")
    return "\n".join(lines) + "\n"


def _render_asset(d: FindingData) -> str:
    lines = ["## Affected Asset", ""]
    lines.append(f"- **URL**: `{d.affected_url}`")
    if d.affected_parameter:
        lines.append(f"- **Parameter**: `{d.affected_parameter}`")
    if d.affected_component:
        lines.append(f"- **Component**: {d.affected_component}")
    lines.append("")
    return "\n".join(lines)


def _render_severity(d: FindingData, warnings: list[str]) -> str:
    lines = ["## Severity Reasoning", ""]
    lines.append(f"**Stated Severity**: {d.severity.upper()}")
    if d.cvss_score is not None:
        lines.append(f"**CVSS Score**: {d.cvss_score}/10")
        warn = _cvss_severity_check(d.severity, d.cvss_score)
        if warn:
            warnings.append(warn)
            lines.append(f"> ⚠️ {warn}")
    else:
        lines.append("_No CVSS score provided. Consider adding one for program compliance._")
    lines.append("")
    return "\n".join(lines)


def _render_reproduction(steps: list[ReproductionStep]) -> str:
    lines = ["## Steps to Reproduce", ""]
    for step in sorted(steps, key=lambda s: s.step_number):
        lines.append(f"{step.step_number}. {step.description}")
        if step.detail:
            lines.append(f"   ```\n   {step.detail}\n   ```")
    lines.append("")
    return "\n".join(lines)


def _render_http_samples(samples: list[HttpSample]) -> str:
    lines = ["## Request / Response Samples", ""]
    for i, sample in enumerate(samples, start=1):
        if len(samples) > 1:
            lines.append(f"### Sample {i}" + (f" — {sample.note}" if sample.note else ""))
        lines.append("**Request:**")
        lines.append("```http")
        lines.append(sample.request.strip())
        lines.append("```")
        lines.append("**Response:**")
        lines.append("```http")
        # Truncate very long responses
        resp = sample.response.strip()
        if len(resp) > 3000:
            resp = resp[:3000] + "\n... [truncated]"
        lines.append(resp)
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def _render_references(d: FindingData) -> str:
    lines = ["## References", ""]
    owasp = _OWASP_MAP.get(d.vuln_type.lower())
    if owasp:
        lines.append(f"- [OWASP — {d.vuln_type.upper()}]({owasp})")
    if d.cwe_id:
        lines.append(f"- [{d.cwe_id}](https://cwe.mitre.org/data/definitions/{d.cwe_id.replace('CWE-', '')}.html)")
    for cve in d.cve_ids:
        lines.append(f"- [{cve}](https://nvd.nist.gov/vuln/detail/{cve})")
    if len(lines) == 2:
        lines.append("_No external references provided._")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------


def _compute_quality_score(d: FindingData, missing: list[str], warnings: list[str]) -> float:
    """
    Score a report on completeness and quality.

    Perfect score = 1.0. Deductions for:
      - missing required sections
      - missing CVSS score
      - summary/impact too short
      - unvalidated finding
    """
    score = 1.0

    # Required section penalties
    section_penalty = {
        "summary": 0.15,
        "reproduction_steps": 0.20,
        "http_samples": 0.15,
        "impact": 0.15,
        "remediation": 0.10,
    }
    for section in missing:
        score -= section_penalty.get(section, 0.05)

    # CVSS missing
    if d.cvss_score is None:
        score -= 0.05

    # Short summary/impact (< 50 chars)
    if len(d.summary.strip()) < 50:
        score -= 0.05
    if len(d.impact.strip()) < 50:
        score -= 0.05

    # Unvalidated finding
    if not d.validated:
        score -= 0.10

    # CVSS/severity mismatch
    if _cvss_severity_check(d.severity, d.cvss_score):
        score -= 0.05

    # Warning penalties (small)
    score -= len(warnings) * 0.02

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def render_finding_report(finding_data: FindingData) -> RenderedReport:
    """Convenience function: render a report from FindingData."""
    return ReportTemplate(finding_data).render()
