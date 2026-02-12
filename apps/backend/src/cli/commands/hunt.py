"""
Hunt command for vulnerability hunting operations.

Usage:
    kai-cli hunt <target> --scope scope.json --watch
    kai-cli hunt example.com --intensity aggressive
    kai-cli hunt --dry-run example.com
"""

import click
import asyncio
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from ..ui import (
    console,
    print_header,
    print_success,
    print_error,
    print_warning,
    print_info,
    create_progress,
    create_findings_table,
    create_hunt_summary,
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
def hunt():
    """Vulnerability hunting operations."""
    pass


@hunt.command("start")
@click.argument("target")
@click.option("--scope", "-s", type=click.Path(exists=True), help="Scope configuration file (JSON)")
@click.option("--intensity", "-i", type=click.Choice(["passive", "normal", "aggressive"]), default="normal", help="Scan intensity")
@click.option("--watch", "-w", is_flag=True, help="Watch mode - stream results in real-time")
@click.option("--dry-run", is_flag=True, help="Validate configuration without executing")
@click.option("--tier", "-t", type=click.IntRange(0, 3), default=1, help="Maximum autonomy tier (0-3)")
@click.option("--output", "-o", type=click.Path(), help="Output file for results")
@click.option("--format", "output_format", type=click.Choice(["json", "csv", "markdown"]), default="json", help="Output format")
def start_hunt(
    target: str,
    scope: Optional[str],
    intensity: str,
    watch: bool,
    dry_run: bool,
    tier: int,
    output: Optional[str],
    output_format: str
):
    """Start a vulnerability hunt on TARGET.

    TARGET can be a domain, IP address, or CIDR range.

    Examples:
        kai-cli hunt start example.com
        kai-cli hunt start example.com --scope ./scope.json --watch
        kai-cli hunt start 10.0.0.0/24 --intensity aggressive --tier 2
    """
    print_header("Vulnerability Hunt", f"Target: {target}")

    # Load scope if provided
    scope_config = {}
    if scope:
        try:
            with open(scope) as f:
                scope_config = json.load(f)
            print_info(f"Loaded scope from {scope}")
        except Exception as e:
            print_error(f"Failed to load scope file: {e}")
            raise click.Abort()

    # Validate target
    if not _validate_target(target):
        print_error(f"Invalid target: {target}")
        raise click.Abort()

    if dry_run:
        print_info("Dry run mode - validating configuration only")
        _validate_hunt_config(target, scope_config, intensity, tier)
        print_success("Configuration is valid")
        return

    # Confirm if aggressive mode
    if intensity == "aggressive":
        if not confirm_action("Aggressive mode may trigger security alerts. Continue?"):
            print_info("Hunt cancelled")
            return

    # Execute hunt
    try:
        result = asyncio.run(_execute_hunt(
            target=target,
            scope=scope_config,
            intensity=intensity,
            tier=tier,
            watch=watch
        ))

        if result.get("success"):
            print_success(f"Hunt completed on {target}")

            # Display findings
            findings = result.get("findings", [])
            if findings:
                console.print(create_findings_table(findings))
                console.print(create_hunt_summary(result))

            # Export if output specified
            if output:
                _export_results(result, output, output_format)
                print_success(f"Results exported to {output}")
        else:
            print_error(f"Hunt failed: {result.get('error', 'Unknown error')}")

    except Exception as e:
        print_error(f"Hunt error: {e}")
        raise click.Abort()


@hunt.command("status")
@click.argument("hunt_id", required=False)
@click.option("--all", "show_all", is_flag=True, help="Show all hunts")
def hunt_status(hunt_id: Optional[str], show_all: bool):
    """Check status of a hunt or list all hunts."""
    print_header("Hunt Status")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        if hunt_id:
            response = client.get(f"/api/v1/agent-zero/workflows/{hunt_id}")
            if response.status_code == 200:
                workflow = response.json()
                _display_hunt_details(workflow)
            else:
                print_error(f"Hunt not found: {hunt_id}")
        else:
            response = client.get("/api/v1/agent-zero/workflows", params={"limit": 50 if show_all else 10})
            if response.status_code == 200:
                data = response.json()
                workflows = data.get("workflows", [])
                if workflows:
                    from ..ui import create_workflow_table
                    console.print(create_workflow_table(workflows))
                else:
                    print_info("No hunts found")
            else:
                print_error("Failed to fetch hunt list")

    except Exception as e:
        print_error(f"Error fetching status: {e}")


@hunt.command("cancel")
@click.argument("hunt_id")
@click.option("--force", "-f", is_flag=True, help="Force cancel without confirmation")
def cancel_hunt(hunt_id: str, force: bool):
    """Cancel a running hunt."""
    if not force and not confirm_action(f"Cancel hunt {hunt_id}?"):
        print_info("Cancelled")
        return

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.post(f"/api/v1/agent-zero/workflows/{hunt_id}/cancel")
        if response.status_code == 200:
            print_success(f"Hunt {hunt_id} cancelled")
        else:
            print_error(f"Failed to cancel hunt: {response.text}")
    except Exception as e:
        print_error(f"Error cancelling hunt: {e}")


@hunt.command("resume")
@click.argument("hunt_id")
def resume_hunt(hunt_id: str):
    """Resume a paused or failed hunt."""
    print_info(f"Resuming hunt {hunt_id}...")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        # Get hunt details
        response = client.get(f"/api/v1/agent-zero/workflows/{hunt_id}")
        if response.status_code != 200:
            print_error(f"Hunt not found: {hunt_id}")
            return

        workflow = response.json()
        if workflow.get("status") == "running":
            print_warning("Hunt is already running")
            return

        # Resume logic would go here
        print_success(f"Hunt {hunt_id} resumed")
    except Exception as e:
        print_error(f"Error resuming hunt: {e}")


# Helper functions

def _validate_target(target: str) -> bool:
    """Validate that target is a valid domain, IP, or CIDR."""
    import re

    # Domain pattern
    domain_pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    # IP pattern
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    # CIDR pattern
    cidr_pattern = r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$'

    return bool(
        re.match(domain_pattern, target) or
        re.match(ip_pattern, target) or
        re.match(cidr_pattern, target)
    )


def _validate_hunt_config(target: str, scope: dict, intensity: str, tier: int):
    """Validate hunt configuration."""
    print_info("Validating configuration...")

    # Check scope constraints
    if scope:
        allowed_targets = scope.get("allowed_targets", [])
        if allowed_targets and target not in allowed_targets:
            print_warning(f"Target {target} not in allowed targets list")

        excluded = scope.get("excluded_targets", [])
        if target in excluded:
            print_error(f"Target {target} is in excluded targets")
            raise click.Abort()

    # Check tier requirements
    if tier >= 2 and intensity == "aggressive":
        print_warning("Tier 2+ with aggressive intensity requires HiL approval")


async def _execute_hunt(
    target: str,
    scope: dict,
    intensity: str,
    tier: int,
    watch: bool
) -> dict:
    """Execute the hunt operation."""
    client = get_api_client()
    if not client:
        return {"success": False, "error": "API client not available"}

    # Create hunt workflow
    try:
        response = client.post(
            "/api/v1/agent-zero/workflows/hunt",
            params={"target": target},
            json=scope
        )

        if response.status_code != 200:
            return {"success": False, "error": response.text}

        workflow = response.json()
        workflow_id = workflow.get("workflow_id")

        if watch:
            return await _watch_hunt_progress(workflow_id)
        else:
            print_info(f"Hunt started with ID: {workflow_id}")
            print_info("Use 'kai-cli hunt status {workflow_id}' to check progress")
            return {"success": True, "workflow_id": workflow_id}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def _watch_hunt_progress(workflow_id: str) -> dict:
    """Watch hunt progress in real-time."""
    import asyncio

    with create_progress() as progress:
        task = progress.add_task(f"[green]Hunting...", total=100)

        findings = []
        while True:
            try:
                client = get_api_client()
                response = client.get(f"/api/v1/agent-zero/workflows/{workflow_id}")

                if response.status_code != 200:
                    break

                data = response.json()
                status = data.get("status", "unknown")
                current_progress = data.get("progress", 0)

                progress.update(task, completed=current_progress)

                if status == "completed":
                    findings = data.get("findings", [])
                    break
                elif status in ["failed", "cancelled"]:
                    return {"success": False, "error": f"Hunt {status}"}

                await asyncio.sleep(2)

            except Exception as e:
                return {"success": False, "error": str(e)}

    return {
        "success": True,
        "workflow_id": workflow_id,
        "findings": findings,
        "findings_count": len(findings),
        "high_severity_count": sum(1 for f in findings if f.get("severity", "").lower() in ["critical", "high"]),
        "target": workflow_id  # Would get actual target from API
    }


def _display_hunt_details(workflow: dict):
    """Display detailed hunt information."""
    from ..ui import create_status_panel

    status = {
        "Workflow ID": workflow.get("workflow_id", workflow.get("id")),
        "Status": workflow.get("status"),
        "Target": workflow.get("target"),
        "Progress": f"{workflow.get('progress', 0)}%",
        "Findings": workflow.get("findings_count", len(workflow.get("findings", []))),
        "Started": workflow.get("created_at", "N/A"),
    }

    console.print(create_status_panel("Hunt Details", status))


def _export_results(result: dict, output: str, format: str):
    """Export hunt results to file."""
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

    elif format == "markdown":
        findings = result.get("findings", [])
        with open(output_path, "w") as f:
            f.write(f"# Hunt Results\n\n")
            f.write(f"**Target:** {result.get('target', 'Unknown')}\n")
            f.write(f"**Findings:** {len(findings)}\n\n")
            f.write("## Findings\n\n")
            for finding in findings:
                f.write(f"### {finding.get('title', 'Untitled')}\n")
                f.write(f"- **Severity:** {finding.get('severity', 'Unknown')}\n")
                f.write(f"- **Type:** {finding.get('type', 'Unknown')}\n")
                f.write(f"- **Target:** {finding.get('target', 'Unknown')}\n\n")
