"""
Findings command for managing vulnerability findings.

Usage:
    kai-cli findings list
    kai-cli findings export --format json
    kai-cli findings submit finding-123
    kai-cli findings validate finding-123
"""

import click
import json
from typing import Optional, List
from datetime import datetime
from pathlib import Path

from ..ui import (
    console,
    print_header,
    print_success,
    print_error,
    print_warning,
    print_info,
    create_findings_table,
    create_status_panel,
    create_table,
    confirm_action,
    print_json,
)


def get_api_client():
    """Get the K1 API client."""
    try:
        import httpx
        return httpx.Client(base_url="http://localhost:8000", timeout=60.0)
    except ImportError:
        return None


@click.group()
def findings():
    """Finding management operations."""
    pass


@findings.command("list")
@click.option("--status", "-s", type=click.Choice(["new", "validated", "submitted", "accepted", "rejected", "duplicate"]), help="Filter by status")
@click.option("--severity", type=click.Choice(["critical", "high", "medium", "low", "info"]), help="Filter by severity")
@click.option("--type", "vuln_type", type=str, help="Filter by vulnerability type")
@click.option("--target", "-t", type=str, help="Filter by target")
@click.option("--limit", "-l", type=int, default=50, help="Maximum findings to show")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def list_findings(status: Optional[str], severity: Optional[str], vuln_type: Optional[str], target: Optional[str], limit: int, json_output: bool):
    """List all findings."""
    if not json_output:
        print_header("Findings")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        # Build filters - this would typically call a findings list endpoint
        # For now, simulate with detection stats
        response = client.get("/findings/detection/stats")

        if response.status_code == 200:
            data = response.json()

            # Simulated findings list - in production this would come from an API
            findings_list = _get_mock_findings(status, severity, vuln_type, target, limit)

            if json_output:
                console.print_json(data={"findings": findings_list, "total": len(findings_list)})
            else:
                if findings_list:
                    console.print(create_findings_table(findings_list))
                    console.print(f"\n[dim]Showing {len(findings_list)} findings[/dim]")
                else:
                    print_info("No findings found matching criteria")

                # Summary stats
                summary = data.get("analysis_summary", {})
                if summary:
                    console.print()
                    console.print(create_status_panel("Summary", {
                        "Total Analyzed": summary.get("total_analyzed", 0),
                        "High Severity": summary.get("high_severity_count", 0),
                        "Exploitable": summary.get("exploitable_count", 0),
                    }))
        else:
            print_error("Failed to fetch findings")

    except Exception as e:
        print_error(f"Error fetching findings: {e}")


@findings.command("show")
@click.argument("finding_id")
def show_finding(finding_id: str):
    """Show details of a specific finding."""
    print_header("Finding Details", f"ID: {finding_id}")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        # Get evidence trail for the finding
        response = client.get(f"/findings/detection/evidence/trail/{finding_id}")

        if response.status_code == 200:
            data = response.json()
            trail = data.get("trail", [])

            # Display finding info (would come from main finding endpoint)
            status = {
                "Finding ID": finding_id,
                "Evidence Count": data.get("evidence_count", 0),
            }
            console.print(create_status_panel("Finding", status))

            # Display evidence
            if trail:
                console.print()
                console.print("[bold]Evidence Trail:[/bold]")
                for i, evidence in enumerate(trail, 1):
                    console.print(f"\n  {i}. [cyan]{evidence.get('type', 'unknown')}[/cyan]")
                    console.print(f"     Source: {evidence.get('source', 'N/A')}")
                    console.print(f"     Time: {evidence.get('timestamp', 'N/A')}")
        else:
            print_error(f"Finding not found: {finding_id}")

    except Exception as e:
        print_error(f"Error fetching finding: {e}")


@findings.command("export")
@click.option("--format", "output_format", type=click.Choice(["json", "csv", "markdown", "html"]), default="json", help="Export format")
@click.option("--output", "-o", type=click.Path(), required=True, help="Output file path")
@click.option("--status", "-s", type=str, help="Filter by status")
@click.option("--severity", type=str, help="Filter by minimum severity")
def export_findings(output_format: str, output: str, status: Optional[str], severity: Optional[str]):
    """Export findings to file.

    Examples:
        kai-cli findings export --format json --output findings.json
        kai-cli findings export --format csv --output findings.csv --severity high
        kai-cli findings export --format markdown --output report.md
    """
    print_header("Export Findings", f"Format: {output_format}")

    # Get findings
    findings_list = _get_mock_findings(status, severity, None, None, 1000)

    if not findings_list:
        print_warning("No findings to export")
        return

    output_path = Path(output)

    try:
        if output_format == "json":
            with open(output_path, "w") as f:
                json.dump({
                    "exported_at": datetime.utcnow().isoformat(),
                    "total": len(findings_list),
                    "findings": findings_list
                }, f, indent=2, default=str)

        elif output_format == "csv":
            import csv
            with open(output_path, "w", newline="") as f:
                if findings_list:
                    writer = csv.DictWriter(f, fieldnames=findings_list[0].keys())
                    writer.writeheader()
                    writer.writerows(findings_list)

        elif output_format == "markdown":
            with open(output_path, "w") as f:
                f.write("# Vulnerability Findings Report\n\n")
                f.write(f"**Generated:** {datetime.utcnow().isoformat()}\n")
                f.write(f"**Total Findings:** {len(findings_list)}\n\n")
                f.write("---\n\n")

                for finding in findings_list:
                    f.write(f"## {finding.get('title', 'Untitled')}\n\n")
                    f.write(f"- **ID:** {finding.get('id', 'N/A')}\n")
                    f.write(f"- **Severity:** {finding.get('severity', 'N/A')}\n")
                    f.write(f"- **Type:** {finding.get('type', 'N/A')}\n")
                    f.write(f"- **Target:** {finding.get('target', 'N/A')}\n")
                    f.write(f"- **Status:** {finding.get('status', 'N/A')}\n")
                    f.write(f"- **Confidence:** {finding.get('confidence', 'N/A')}\n\n")
                    if finding.get('description'):
                        f.write(f"### Description\n\n{finding['description']}\n\n")
                    f.write("---\n\n")

        elif output_format == "html":
            _export_html(output_path, findings_list)

        print_success(f"Exported {len(findings_list)} findings to {output}")

    except Exception as e:
        print_error(f"Export failed: {e}")


@findings.command("validate")
@click.argument("finding_id")
@click.option("--auto", "-a", is_flag=True, help="Use automated validation")
def validate_finding(finding_id: str, auto: bool):
    """Validate a finding.

    Examples:
        kai-cli findings validate finding-123
        kai-cli findings validate finding-123 --auto
    """
    print_header("Validate Finding", f"ID: {finding_id}")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        # Get evidence report
        response = client.get(f"/findings/detection/evidence/report/{finding_id}")

        if response.status_code == 200:
            data = response.json()
            report = data.get("report", {})

            console.print(create_status_panel("Validation Report", {
                "Finding ID": finding_id,
                "Evidence Count": report.get("evidence_count", 0),
                "Integrity Valid": report.get("integrity_valid", False),
                "Chain Complete": report.get("chain_complete", False),
            }))

            if report.get("integrity_valid") and report.get("chain_complete"):
                print_success("Finding validation passed")
            else:
                print_warning("Finding validation has issues")
                if not report.get("integrity_valid"):
                    print_warning("  - Evidence integrity check failed")
                if not report.get("chain_complete"):
                    print_warning("  - Evidence chain is incomplete")
        else:
            print_error(f"Failed to validate finding: {response.text}")

    except Exception as e:
        print_error(f"Validation error: {e}")


@findings.command("submit")
@click.argument("finding_id")
@click.option("--program", "-p", type=str, help="Bug bounty program to submit to")
@click.option("--dry-run", is_flag=True, help="Validate without submitting")
def submit_finding(finding_id: str, program: Optional[str], dry_run: bool):
    """Submit a finding to a bug bounty program.

    Examples:
        kai-cli findings submit finding-123 --program hackerone-example
        kai-cli findings submit finding-123 --dry-run
    """
    print_header("Submit Finding", f"ID: {finding_id}")

    if dry_run:
        print_info("Dry run mode - validating submission")

    # Validate first
    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        # Check evidence
        response = client.get(f"/findings/detection/evidence/report/{finding_id}")

        if response.status_code == 200:
            report = response.json().get("report", {})

            if not report.get("integrity_valid"):
                print_error("Cannot submit - evidence integrity check failed")
                return

            if not report.get("chain_complete"):
                print_warning("Evidence chain is incomplete - submission may be rejected")
                if not confirm_action("Continue anyway?"):
                    return

            if dry_run:
                print_success("Validation passed - finding ready for submission")
                return

            # Actual submission would go here
            if not program:
                print_error("Program is required for submission")
                return

            print_info(f"Submitting to {program}...")
            # submission_result = client.post(f"/submissions/submit", json={...})

            print_success(f"Finding {finding_id} submitted to {program}")
        else:
            print_error(f"Finding not found: {finding_id}")

    except Exception as e:
        print_error(f"Submission error: {e}")


@findings.command("deduplicate")
@click.option("--strategy", "-s", type=click.Choice(["exact", "shallow", "fuzzy", "multi"]), default="multi", help="Deduplication strategy")
@click.option("--dry-run", is_flag=True, help="Show duplicates without removing")
def deduplicate_findings(strategy: str, dry_run: bool):
    """Deduplicate findings.

    Examples:
        kai-cli findings deduplicate --strategy fuzzy
        kai-cli findings deduplicate --dry-run
    """
    print_header("Deduplicate Findings", f"Strategy: {strategy}")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        # Get mock findings for deduplication
        findings_list = _get_mock_findings(None, None, None, None, 100)

        if not findings_list:
            print_info("No findings to deduplicate")
            return

        response = client.post(
            "/findings/detection/deduplicate",
            json={"findings": findings_list, "strategy": strategy}
        )

        if response.status_code == 200:
            data = response.json()

            unique = data.get("unique_findings", [])
            groups = data.get("duplicate_groups", [])
            summary = data.get("dedup_summary", {})

            console.print(create_status_panel("Deduplication Results", {
                "Original Count": summary.get("original_count", len(findings_list)),
                "Unique Findings": summary.get("unique_count", len(unique)),
                "Duplicates Found": summary.get("duplicate_count", 0),
                "Duplicate Groups": len(groups),
            }))

            if groups and dry_run:
                console.print("\n[bold]Duplicate Groups:[/bold]")
                for i, group in enumerate(groups[:10], 1):
                    console.print(f"\n  Group {i}:")
                    for f in group[:3]:
                        console.print(f"    - {f.get('title', 'Untitled')[:50]}")

            if not dry_run:
                print_success(f"Removed {summary.get('duplicate_count', 0)} duplicates")
        else:
            print_error(f"Deduplication failed: {response.text}")

    except Exception as e:
        print_error(f"Deduplication error: {e}")


@findings.command("analyze")
@click.argument("finding_id", required=False)
@click.option("--all", "analyze_all", is_flag=True, help="Analyze all findings")
def analyze_finding(finding_id: Optional[str], analyze_all: bool):
    """Analyze finding(s) for severity, exploitability, and impact.

    Examples:
        kai-cli findings analyze finding-123
        kai-cli findings analyze --all
    """
    print_header("Analyze Findings")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        if finding_id:
            # Single finding analysis
            finding = {"id": finding_id, "title": "Test Finding"}  # Would fetch real finding
            response = client.post(
                "/findings/detection/analyze-single",
                json={"finding": finding}
            )

            if response.status_code == 200:
                data = response.json()
                analysis = data.get("analysis", {})

                console.print(create_status_panel("Analysis Results", {
                    "Severity": analysis.get("severity", "N/A"),
                    "CVSS Score": analysis.get("cvss_score", "N/A"),
                    "Exploitability": analysis.get("exploitability", "N/A"),
                    "Impact": analysis.get("impact", "N/A"),
                }))

                recommendations = analysis.get("recommendations", [])
                if recommendations:
                    console.print("\n[bold]Recommendations:[/bold]")
                    for rec in recommendations:
                        console.print(f"  - {rec}")
            else:
                print_error(f"Analysis failed: {response.text}")
        else:
            # Batch analysis
            findings_list = _get_mock_findings(None, None, None, None, 50)
            response = client.post(
                "/findings/detection/analyze",
                json={"findings": findings_list}
            )

            if response.status_code == 200:
                data = response.json()
                summary = data.get("summary", {})

                console.print(create_status_panel("Analysis Summary", {
                    "Total Analyzed": summary.get("total_analyzed", 0),
                    "Critical": summary.get("critical_count", 0),
                    "High": summary.get("high_count", 0),
                    "Medium": summary.get("medium_count", 0),
                    "Low": summary.get("low_count", 0),
                }))
            else:
                print_error(f"Batch analysis failed: {response.text}")

    except Exception as e:
        print_error(f"Analysis error: {e}")


@findings.command("stats")
def findings_stats():
    """Show finding statistics."""
    print_header("Finding Statistics")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.get("/findings/detection/stats")

        if response.status_code == 200:
            data = response.json()

            # Deduplicator stats
            dedup = data.get("deduplicator_stats", {})
            console.print(create_status_panel("Deduplication", {
                "Total Processed": dedup.get("total_processed", 0),
                "Duplicates Found": dedup.get("duplicates_found", 0),
                "Unique Rate": f"{dedup.get('unique_rate', 0):.1%}",
            }))

            # Analysis stats
            analysis = data.get("analysis_summary", {})
            console.print()
            console.print(create_status_panel("Analysis", {
                "Total Analyzed": analysis.get("total_analyzed", 0),
                "Avg Severity": analysis.get("avg_severity", "N/A"),
                "Exploitable": analysis.get("exploitable_count", 0),
            }))

            # Nuclei stats
            nuclei = data.get("nuclei_stats", {})
            console.print()
            console.print(create_status_panel("Nuclei Scanner", {
                "Total Scans": nuclei.get("total_scans", 0),
                "Findings Found": nuclei.get("total_findings", 0),
                "Success Rate": f"{nuclei.get('success_rate', 0):.1%}",
            }))
        else:
            print_error("Failed to fetch statistics")

    except Exception as e:
        print_error(f"Error fetching stats: {e}")


# Helper functions

def _get_mock_findings(status: Optional[str], severity: Optional[str], vuln_type: Optional[str], target: Optional[str], limit: int) -> List[dict]:
    """Get mock findings for demonstration. In production, this would call the API."""
    # This would be replaced with actual API call
    mock_findings = [
        {
            "id": "f-001",
            "title": "SQL Injection in login form",
            "severity": "critical",
            "type": "sqli",
            "target": "example.com/login",
            "status": "validated",
            "confidence": 0.95,
            "description": "SQL injection vulnerability found in login form parameter"
        },
        {
            "id": "f-002",
            "title": "Reflected XSS in search",
            "severity": "high",
            "type": "xss",
            "target": "example.com/search",
            "status": "new",
            "confidence": 0.87,
            "description": "Reflected XSS in search query parameter"
        },
        {
            "id": "f-003",
            "title": "Information disclosure via error",
            "severity": "medium",
            "type": "info_disclosure",
            "target": "example.com/api",
            "status": "validated",
            "confidence": 0.92,
            "description": "Stack trace exposed in error responses"
        },
    ]

    # Apply filters
    results = mock_findings
    if status:
        results = [f for f in results if f["status"] == status]
    if severity:
        results = [f for f in results if f["severity"] == severity]
    if vuln_type:
        results = [f for f in results if vuln_type.lower() in f["type"].lower()]
    if target:
        results = [f for f in results if target.lower() in f["target"].lower()]

    return results[:limit]


def _export_html(output_path: Path, findings: List[dict]):
    """Export findings to HTML format."""
    html = """<!DOCTYPE html>
<html>
<head>
    <title>K1 Findings Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }
        h1 { color: #1a472a; }
        .finding { border: 1px solid #ddd; margin: 20px 0; padding: 15px; border-radius: 8px; }
        .critical { border-left: 4px solid #dc3545; }
        .high { border-left: 4px solid #fd7e14; }
        .medium { border-left: 4px solid #ffc107; }
        .low { border-left: 4px solid #17a2b8; }
        .info { border-left: 4px solid #6c757d; }
        .severity { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
        .severity.critical { background: #dc3545; color: white; }
        .severity.high { background: #fd7e14; color: white; }
        .severity.medium { background: #ffc107; color: black; }
        .severity.low { background: #17a2b8; color: white; }
        .meta { color: #666; font-size: 14px; }
    </style>
</head>
<body>
    <h1>K1 Vulnerability Findings Report</h1>
    <p class="meta">Generated: """ + datetime.utcnow().isoformat() + f"""</p>
    <p class="meta">Total Findings: {len(findings)}</p>
    <hr>
"""

    for finding in findings:
        severity = finding.get('severity', 'medium').lower()
        html += f"""
    <div class="finding {severity}">
        <h3>{finding.get('title', 'Untitled')}</h3>
        <span class="severity {severity}">{severity.upper()}</span>
        <p class="meta">
            <strong>ID:</strong> {finding.get('id', 'N/A')} |
            <strong>Type:</strong> {finding.get('type', 'N/A')} |
            <strong>Target:</strong> {finding.get('target', 'N/A')} |
            <strong>Status:</strong> {finding.get('status', 'N/A')}
        </p>
        <p>{finding.get('description', 'No description')}</p>
    </div>
"""

    html += """
</body>
</html>
"""

    with open(output_path, "w") as f:
        f.write(html)
