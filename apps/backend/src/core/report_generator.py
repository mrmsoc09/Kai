"""
Report Generator
Generate comprehensive post-review reports for auto-applied fixes
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


async def generate_post_review_report(
    target: str,
    findings: List[Dict[str, Any]],
    repairs: List[Any],  # VulnerabilityRepair objects
    auto_applied: bool,
    budget_spent: float,
    timestamp: datetime
) -> Dict[str, Any]:
    """
    Generate comprehensive post-review report for auto-applied fixes.

    Includes:
    - Executive summary of changes
    - Each vulnerability with before/after code
    - Validation results and confidence scores
    - Cost breakdown (local vs paid API usage)
    - Rollback instructions if needed
    - Next steps and recommendations
    """

    logger.info(f"Generating post-review report for {target}")

    # Calculate statistics
    total_vulnerabilities = len(findings)
    total_repairs = len(repairs)
    repairs_applied = sum(1 for r in repairs if r.fix_applied)

    # Calculate cost breakdown
    analysis_cost = sum(f.get("analysis_cost", 0.0) for f in findings)
    repair_cost = sum(r.cost_cents for r in repairs)
    total_cost = analysis_cost + repair_cost

    # Calculate model usage split
    if total_cost > 0:
        paid_percentage = (total_cost / (total_cost + 0.01)) * 100  # Avoid division by zero
        local_percentage = 100 - paid_percentage
    else:
        local_percentage = 100.0
        paid_percentage = 0.0

    # Build change records
    changes = []
    for repair in repairs:
        change = {
            "file": repair.file_path,
            "vulnerability": repair.vulnerability_type,
            "severity": repair.severity,
            "before_code": repair.original_code,
            "after_code": repair.fixed_code,
            "validation": {
                "is_valid": repair.validation_result.get("is_valid", False),
                "confidence": repair.validation_result.get("confidence", 0.0),
                "issues": repair.validation_result.get("issues", [])
            },
            "applied": repair.fix_applied,
            "rollback_command": f"git checkout {repair.file_path}" if repair.fix_applied else None
        }
        changes.append(change)

    # Build report
    report = {
        "header": f"[AI-GENERATED CODE CHANGES: {'AUTO-APPLIED WITH POST-REVIEW' if auto_applied else 'REVIEW REQUIRED'}]",
        "timestamp": timestamp.isoformat(),
        "target": target,

        "summary": {
            "vulnerabilities_found": total_vulnerabilities,
            "repairs_generated": total_repairs,
            "repairs_applied": repairs_applied if auto_applied else 0,
            "total_cost_usd": total_cost / 100,
            "local_model_usage_percent": local_percentage,
            "paid_api_usage_percent": paid_percentage,
            "auto_applied": auto_applied
        },

        "changes": changes,

        "cost_breakdown": {
            "discovery_cost_usd": 0.0,  # Always local
            "analysis_cost_usd": analysis_cost / 100,
            "repair_cost_usd": repair_cost / 100,
            "validation_cost_usd": 0.0,  # Always local
            "total_cost_usd": total_cost / 100
        },

        "validation_summary": {
            "total_validations": len(repairs),
            "passed_validations": sum(
                1 for r in repairs
                if r.validation_result.get("is_valid", False)
            ),
            "average_confidence": sum(
                r.validation_result.get("confidence", 0.0)
                for r in repairs
            ) / len(repairs) if repairs else 0.0
        },

        "next_steps": [
            "Review all changes in git diff",
            "Run full test suite to verify fixes",
            "Perform manual security review of critical changes",
            "Deploy to staging environment for testing",
            "Monitor for any regressions or issues",
            "Document security improvements in changelog"
        ],

        "rollback_instructions": {
            "individual_files": [
                {
                    "file": change["file"],
                    "command": change["rollback_command"]
                }
                for change in changes if change.get("rollback_command")
            ],
            "full_rollback": "git reset --hard HEAD~1"
        } if auto_applied else None,

        "recommendations": _generate_recommendations(findings, repairs, total_cost)
    }

    logger.info(f"✓ Report generated: {total_repairs} repairs, ${total_cost/100:.2f} cost")

    return report


def _generate_recommendations(
    findings: List[Dict[str, Any]],
    repairs: List[Any],
    total_cost: float
) -> List[str]:
    """Generate recommendations based on findings and repairs"""

    recommendations = []

    # Cost-based recommendations
    if total_cost > 500:  # > $5
        recommendations.append(
            f"High repair cost (${total_cost/100:.2f}) - consider batch processing "
            "similar vulnerabilities to optimize costs"
        )

    # Severity-based recommendations
    high_severity = sum(1 for f in findings if f.get("severity") == "high")
    if high_severity > 0:
        recommendations.append(
            f"{high_severity} high-severity vulnerabilities found - "
            "prioritize deployment and consider security audit"
        )

    # Validation-based recommendations
    low_confidence = sum(
        1 for r in repairs
        if r.validation_result.get("confidence", 1.0) < 0.7
    )
    if low_confidence > 0:
        recommendations.append(
            f"{low_confidence} repairs have low confidence (<70%) - "
            "perform manual code review before deployment"
        )

    # Pattern-based recommendations
    vuln_types = {}
    for finding in findings:
        vuln_type = finding.get("type", "unknown")
        vuln_types[vuln_type] = vuln_types.get(vuln_type, 0) + 1

    if len(vuln_types) > 1:
        most_common = max(vuln_types.items(), key=lambda x: x[1])
        recommendations.append(
            f"Most common vulnerability: {most_common[0]} ({most_common[1]} instances) - "
            "consider implementing automated detection in CI/CD"
        )

    # General recommendations
    recommendations.extend([
        "Set up automated security scanning in pre-commit hooks",
        "Enable SAST/DAST tools in CI/CD pipeline",
        "Schedule regular security training for development team",
        "Implement security champions program"
    ])

    return recommendations


async def generate_markdown_report(report: Dict[str, Any]) -> str:
    """Generate markdown-formatted report"""

    md = f"""# {report['header']}

**Generated:** {report['timestamp']}
**Target:** {report['target']}

---

## Executive Summary

- **Vulnerabilities Found:** {report['summary']['vulnerabilities_found']}
- **Repairs Generated:** {report['summary']['repairs_generated']}
- **Repairs Applied:** {report['summary']['repairs_applied']}
- **Total Cost:** ${report['summary']['total_cost_usd']:.4f}
- **Model Usage:** {report['summary']['local_model_usage_percent']:.1f}% local, {report['summary']['paid_api_usage_percent']:.1f}% paid APIs

---

## Changes Applied

"""

    for i, change in enumerate(report['changes'], 1):
        md += f"""### {i}. {change['file']} - {change['vulnerability']} ({change['severity']})

**Validation:**
- Valid: {change['validation']['is_valid']}
- Confidence: {change['validation']['confidence']:.1%}
- Issues: {', '.join(change['validation']['issues']) if change['validation']['issues'] else 'None'}

**Before:**
```
{change['before_code']}
```

**After:**
```
{change['after_code']}
```

{"**Rollback:** `" + change['rollback_command'] + "`" if change.get('rollback_command') else '**Status:** Not applied (review mode)'}

---

"""

    md += f"""## Cost Breakdown

- Discovery: ${report['cost_breakdown']['discovery_cost_usd']:.4f} (local)
- Analysis: ${report['cost_breakdown']['analysis_cost_usd']:.4f}
- Repair: ${report['cost_breakdown']['repair_cost_usd']:.4f}
- Validation: ${report['cost_breakdown']['validation_cost_usd']:.4f} (local)
- **Total: ${report['cost_breakdown']['total_cost_usd']:.4f}**

---

## Validation Summary

- Total Validations: {report['validation_summary']['total_validations']}
- Passed: {report['validation_summary']['passed_validations']}
- Average Confidence: {report['validation_summary']['average_confidence']:.1%}

---

## Next Steps

"""

    for step in report['next_steps']:
        md += f"- {step}\n"

    md += "\n---\n\n## Recommendations\n\n"

    for rec in report['recommendations']:
        md += f"- {rec}\n"

    if report.get('rollback_instructions'):
        md += "\n---\n\n## Rollback Instructions\n\n"
        md += "**Individual Files:**\n\n"
        for file_rollback in report['rollback_instructions']['individual_files']:
            md += f"- `{file_rollback['command']}`\n"
        md += f"\n**Full Rollback:** `{report['rollback_instructions']['full_rollback']}`\n"

    md += "\n---\n\n*Generated by Kaison K1 Vulnerability Repair Pipeline*\n"

    return md


async def generate_bbp_report(
    scan_id: str,
    program: Dict[str, Any],
    scan_result: Any
) -> str:
    """
    Generate comprehensive BBP findings report

    Args:
        scan_id: Scan ID
        program: BBP program details
        scan_result: Full scan result

    Returns:
        str: Path to generated report
    """

    from pathlib import Path
    import json

    # Create reports directory
    reports_dir = Path("var/lib/kai/reports/bbp")
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Generate report filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_filename = f"{scan_id}_{timestamp}_report.md"
    report_path = reports_dir / report_filename

    # Extract findings
    findings = []
    for phase in scan_result.phases:
        if hasattr(phase, 'phase') and phase.phase == "analysis":
            findings = phase.output.get("findings", [])
            break

    # Generate markdown report
    program_name = program.get("name", "Unknown Program")
    target = scan_result.target

    report_content = f"""# Security Findings Report
## {program_name}

**Generated by:** Kaison K1 Platform
**Scan ID:** `{scan_id}`
**Target:** {target}
**Date:** {scan_result.started_at.strftime('%Y-%m-%d %H:%M UTC')}

---

## Executive Summary

- **Total Findings:** {scan_result.total_findings}
- **Critical:** {scan_result.critical_findings}
- **High:** {scan_result.high_findings}
- **Medium:** {scan_result.medium_findings}
- **Low:** {scan_result.low_findings}
- **Total Cost:** ${scan_result.total_cost_cents/100:.2f}

---

## Detailed Findings

"""

    # Add each finding
    for i, finding in enumerate(findings, 1):
        severity = finding.get("severity", "unknown").upper()
        finding_type = finding.get("type", "Unknown").replace("_", " ").title()
        url = finding.get("url", "N/A")
        cvss = finding.get("cvss", 0.0)
        description = finding.get("description", "No description provided")

        report_content += f"""
### Finding {i}: {finding_type}

**Severity:** {severity}
**CVSS Score:** {cvss:.1f}
**URL:** `{url}`

**Description:**
{description}

**Recommendation:**
Implement proper input validation and output encoding.

---

"""

    # Add footer
    completed_duration = 0
    if scan_result.completed_at:
        completed_duration = (scan_result.completed_at - scan_result.started_at).total_seconds()

    report_content += f"""
## Scan Details

**Scan Duration:** {completed_duration:.1f} seconds
**Phases Completed:** {len(scan_result.phases)}
**Status:** {scan_result.status}

---

**Report Generated:** {datetime.utcnow().isoformat()}
**Platform:** Kaison K1 v7.6
"""

    # Write report to file
    report_path.write_text(report_content)

    logger.info(f"✓ BBP report generated: {report_path}")

    return str(report_path)
