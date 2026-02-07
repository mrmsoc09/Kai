"""
Scan command for security scanning operations.

Usage:
    kai-cli scan <target> --tool nuclei
    kai-cli scan example.com --templates cves
    kai-cli scan --list-tools
"""

import click
import asyncio
import json
from typing import Optional, List
from datetime import datetime

from ..ui import (
    console,
    print_header,
    print_success,
    print_error,
    print_warning,
    print_info,
    create_progress,
    create_table,
    create_findings_table,
    confirm_action,
)


def get_api_client():
    """Get the K1 API client."""
    try:
        import httpx
        return httpx.Client(base_url="http://localhost:8000", timeout=300.0)
    except ImportError:
        return None


@click.group()
def scan():
    """Security scanning operations."""
    pass


@scan.command("run")
@click.argument("target")
@click.option("--tool", "-t", multiple=True, help="Tools to use (can specify multiple)")
@click.option("--templates", type=str, help="Nuclei template category or path")
@click.option("--severity", "-s", type=click.Choice(["info", "low", "medium", "high", "critical"]), default="medium", help="Minimum severity")
@click.option("--timeout", type=int, default=300, help="Scan timeout in seconds")
@click.option("--output", "-o", type=click.Path(), help="Output file for results")
@click.option("--format", "output_format", type=click.Choice(["json", "csv"]), default="json", help="Output format")
@click.option("--parallel", "-p", is_flag=True, help="Run tools in parallel")
def run_scan(
    target: str,
    tool: tuple,
    templates: Optional[str],
    severity: str,
    timeout: int,
    output: Optional[str],
    output_format: str,
    parallel: bool
):
    """Run a security scan on TARGET.

    Examples:
        kai-cli scan run example.com --tool nuclei
        kai-cli scan run example.com --tool nuclei --tool nmap --parallel
        kai-cli scan run example.com --templates cves --severity high
    """
    tools = list(tool) if tool else ["nuclei"]
    print_header("Security Scan", f"Target: {target} | Tools: {', '.join(tools)}")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        all_findings = []

        if parallel and len(tools) > 1:
            # Run tools in parallel
            results = asyncio.run(_run_parallel_scans(target, tools, templates, severity, timeout))
            for result in results:
                if result.get("findings"):
                    all_findings.extend(result["findings"])
        else:
            # Run tools sequentially
            with create_progress() as progress:
                task = progress.add_task("[green]Scanning...", total=len(tools))

                for t in tools:
                    print_info(f"Running {t}...")
                    result = _run_single_scan(client, target, t, templates, severity, timeout)

                    if result.get("scan", {}).get("findings"):
                        all_findings.extend(result["scan"]["findings"])

                    progress.advance(task)

        # Display results
        if all_findings:
            print_success(f"Scan complete: {len(all_findings)} findings")
            console.print(create_findings_table(all_findings))
        else:
            print_info("No findings discovered")

        # Export if output specified
        if output:
            _export_scan_results({"target": target, "findings": all_findings}, output, output_format)
            print_success(f"Results exported to {output}")

    except Exception as e:
        print_error(f"Scan error: {e}")


@scan.command("list-tools")
def list_tools():
    """List available scanning tools."""
    print_header("Available Scanning Tools")

    tools = [
        ["nuclei", "Fast vulnerability scanner", "active"],
        ["nmap", "Network discovery and security auditing", "active"],
        ["masscan", "High-speed port scanner", "active"],
        ["subfinder", "Subdomain discovery tool", "passive"],
        ["httpx", "HTTP toolkit for probing", "active"],
        ["ffuf", "Fast web fuzzer", "active"],
        ["sqlmap", "SQL injection detection", "active"],
        ["xss_hunter", "XSS vulnerability detection", "active"],
        ["nikto", "Web server scanner", "active"],
    ]

    table = create_table(
        "Scanning Tools",
        ["Tool", "Description", "Type"],
        tools,
        styles=["cyan", None, "green"]
    )

    console.print(table)


@scan.command("templates")
@click.option("--category", "-c", type=str, help="Filter by category")
def list_templates(category: Optional[str]):
    """List available Nuclei templates."""
    print_header("Nuclei Templates")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        params = {}
        if category:
            params["category"] = category

        response = client.get("/findings/detection/nuclei/templates", params=params)

        if response.status_code == 200:
            data = response.json()
            templates = data.get("templates", [])

            if templates:
                rows = [[t.get("name", ""), t.get("category", ""), t.get("severity", "")] for t in templates[:50]]
                table = create_table(
                    f"Templates ({len(templates)} total)",
                    ["Name", "Category", "Severity"],
                    rows
                )
                console.print(table)
            else:
                print_info("No templates found")
        else:
            print_error("Failed to fetch templates")

    except Exception as e:
        print_error(f"Error fetching templates: {e}")


@scan.command("status")
@click.argument("scan_id", required=False)
def scan_status(scan_id: Optional[str]):
    """Check status of a scan or list recent scans."""
    print_header("Scan Status")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.get("/findings/detection/stats")

        if response.status_code == 200:
            data = response.json()

            nuclei_stats = data.get("nuclei_stats", {})
            status = {
                "Total Scans": nuclei_stats.get("total_scans", 0),
                "Successful": nuclei_stats.get("successful_scans", 0),
                "Failed": nuclei_stats.get("failed_scans", 0),
                "Findings Found": nuclei_stats.get("total_findings", 0),
            }

            from ..ui import create_status_panel
            console.print(create_status_panel("Scan Statistics", status))
        else:
            print_error("Failed to fetch scan status")

    except Exception as e:
        print_error(f"Error fetching status: {e}")


@scan.command("validate")
def validate_setup():
    """Validate scanning tool setup."""
    print_header("Tool Validation")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.get("/findings/detection/nuclei/validate")

        if response.status_code == 200:
            data = response.json()
            validation = data.get("validation", {})

            if validation.get("is_valid"):
                print_success("Nuclei setup is valid")
                console.print(f"  Version: {validation.get('version', 'unknown')}")
                console.print(f"  Templates: {validation.get('template_count', 0)}")
            else:
                print_error("Nuclei setup is invalid")
                for issue in validation.get("issues", []):
                    print_warning(f"  - {issue}")
        else:
            print_error("Failed to validate setup")

    except Exception as e:
        print_error(f"Validation error: {e}")


# Helper functions

def _run_single_scan(client, target: str, tool: str, templates: Optional[str], severity: str, timeout: int) -> dict:
    """Run a single scan with the specified tool."""
    if tool == "nuclei":
        payload = {
            "target": target,
            "severity": severity,
            "timeout": timeout
        }
        if templates:
            payload["templates"] = templates

        response = client.post("/findings/detection/nuclei/scan", json=payload)
        if response.status_code == 200:
            return response.json()

    return {"scan": {"findings": []}}


async def _run_parallel_scans(target: str, tools: List[str], templates: Optional[str], severity: str, timeout: int) -> List[dict]:
    """Run multiple scans in parallel."""
    import asyncio

    async def run_scan(tool: str):
        try:
            import httpx
            async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=timeout) as client:
                if tool == "nuclei":
                    payload = {"target": target, "severity": severity, "timeout": timeout}
                    if templates:
                        payload["templates"] = templates
                    response = await client.post("/findings/detection/nuclei/scan", json=payload)
                    if response.status_code == 200:
                        return response.json().get("scan", {})
        except Exception as e:
            print_warning(f"Error running {tool}: {e}")
        return {"findings": []}

    tasks = [run_scan(tool) for tool in tools]
    return await asyncio.gather(*tasks)


def _export_scan_results(result: dict, output: str, format: str):
    """Export scan results to file."""
    from pathlib import Path

    output_path = Path(output)

    if format == "json":
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2, default=str)

    elif format == "csv":
        import csv
        findings = result.get("findings", [])
        if findings:
            with open(output_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=findings[0].keys())
                writer.writeheader()
                writer.writerows(findings)
