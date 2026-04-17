from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def estimate_severity(cvss_score: float) -> str:
    """Map CVSS score to HackerOne severity label."""
    if cvss_score >= 9.0:
        return "critical"
    if cvss_score >= 7.0:
        return "high"
    if cvss_score >= 4.0:
        return "medium"
    if cvss_score >= 0.1:
        return "low"
    return "none"


class ReportGenerationService:
    """Converts validated findings into submission-ready HackerOne markdown."""

    def generate_hackerone_report(
        self,
        finding: dict[str, Any],
        evidence_list: list[dict[str, Any]] | None = None,
        reproduction_steps: str | None = None,
    ) -> str:
        """Generate a HackerOne-compatible markdown report.

        Required finding fields: title, description, asset/target, vulnerability_type/vuln_type
        Optional: cvss_score, severity, impact, references, steps_to_reproduce
        """
        title = finding.get("title", "Untitled Finding")
        description = finding.get("description", "No description provided.")
        asset = finding.get("asset", finding.get("target", "Unknown"))
        vuln_type = finding.get("vulnerability_type", finding.get("vuln_type", "Unknown"))
        cvss = float(finding.get("cvss_score", 0.0))
        severity = finding.get("severity", estimate_severity(cvss))
        impact = finding.get("impact", f"This vulnerability ({vuln_type}) on {asset} "
                             f"has been rated as {severity} severity (CVSS: {cvss:.1f}).")
        references = finding.get("references", [])

        # Steps to reproduce
        steps = reproduction_steps or finding.get("steps_to_reproduce", "")
        if not steps:
            steps = (
                f"1. Navigate to {asset}\n"
                f"2. Trigger {vuln_type} vulnerability\n"
                "3. Observe the behavior described in the summary"
            )

        # Evidence section
        evidence_lines: list[str] = []
        if evidence_list:
            for i, ev in enumerate(evidence_list, 1):
                uri = ev.get("artifact_uri", ev.get("uri", "N/A"))
                etype = ev.get("evidence_type", ev.get("kind", "artifact"))
                summary = ev.get("summary", "")
                line = f"- **Evidence {i}** ({etype}): `{uri}`"
                if summary:
                    line += f" - {summary}"
                evidence_lines.append(line)
        else:
            evidence_lines.append("- No evidence artifacts attached.")

        # References section
        ref_lines: list[str] = []
        if references:
            for ref in references:
                ref_lines.append(f"- {ref}")
        else:
            ref_lines.append("- No additional references.")

        report = f"""## Summary

**Title:** {title}
**Asset:** {asset}
**Vulnerability Type:** {vuln_type}
**Severity:** {severity} (CVSS: {cvss:.1f})

{description}

## Vulnerability Details

- **Type:** {vuln_type}
- **Affected Asset:** {asset}
- **CVSS Score:** {cvss:.1f}
- **Severity:** {severity}

## Steps to Reproduce

{steps}

## Impact

{impact}

## Evidence

{chr(10).join(evidence_lines)}

## References

{chr(10).join(ref_lines)}
"""
        return report.strip()

    async def generate_from_finding_id(self, finding_id: str, db: Any) -> str:
        """Load Finding + linked StructuredEvidence records and generate report."""
        from sqlalchemy import select
        from ..models.hil import Finding
        from ..models.structured_evidence import StructuredEvidence

        result = await db.execute(
            select(Finding).where(Finding.id == finding_id)
        )
        finding_row = result.scalar_one_or_none()
        if not finding_row:
            raise ValueError(f"Finding {finding_id} not found")

        # Load linked evidence
        ev_result = await db.execute(
            select(StructuredEvidence).where(
                StructuredEvidence.finding_id == finding_id
            )
        )
        evidence_rows = ev_result.scalars().all()

        finding_dict = {
            "title": finding_row.title,
            "description": finding_row.description,
            "asset": finding_row.asset,
            "severity": finding_row.severity.value if hasattr(finding_row.severity, "value") else str(finding_row.severity),
            "cvss_score": finding_row.reproducibility_score or 0.0,
        }

        evidence_list = []
        reproduction_steps = None
        for ev in evidence_rows:
            evidence_list.append({
                "artifact_uri": ev.artifact_uri,
                "evidence_type": ev.evidence_type,
                "summary": ev.summary,
            })
            if ev.replay_reproduction_steps and not reproduction_steps:
                reproduction_steps = ev.replay_reproduction_steps

        return self.generate_hackerone_report(
            finding_dict,
            evidence_list=evidence_list,
            reproduction_steps=reproduction_steps,
        )

    @staticmethod
    def estimate_severity(cvss_score: float) -> str:
        """Map CVSS score to H1 severity label."""
        return estimate_severity(cvss_score)
