"""
Workflow command for managing hunting workflows.

Usage:
    kai-cli workflow list
    kai-cli workflow run recon-full --target example.com
    kai-cli workflow cancel workflow-123
    kai-cli workflow templates
"""

import click
import asyncio
import json
from typing import Optional
from datetime import datetime, timezone

from ..ui import (
    console,
    print_header,
    print_success,
    print_error,
    print_warning,
    print_info,
    create_workflow_table,
    create_status_panel,
    create_table,
    create_progress,
    confirm_action,
)


def get_api_client():
    """Get the K1 API client."""
    try:
        import httpx
        return httpx.Client(base_url="http://localhost:8080", timeout=300.0)
    except ImportError:
        return None


@click.group()
def workflow():
    """Workflow management operations."""
    pass


@workflow.command("list")
@click.option("--status", "-s", type=click.Choice(["pending", "running", "completed", "failed", "cancelled"]), help="Filter by status")
@click.option("--limit", "-l", type=int, default=20, help="Maximum workflows to show")
def list_workflows(status: Optional[str], limit: int):
    """List all workflows."""
    print_header("Workflows")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        params = {"limit": limit}
        if status:
            params["status"] = status

        response = client.get("/api/v1/orchestration/workflows", params=params)

        if response.status_code == 200:
            data = response.json()
            workflows = data.get("workflows", [])

            if workflows:
                console.print(create_workflow_table(workflows))
                console.print(f"\n[dim]Total: {data.get('total', len(workflows))} workflows[/dim]")
            else:
                print_info("No workflows found")
        else:
            print_error("Failed to fetch workflows")

    except Exception as e:
        print_error(f"Error fetching workflows: {e}")


@workflow.command("run")
@click.argument("template")
@click.option("--target", "-t", required=True, help="Target for the workflow")
@click.option("--scope", "-s", type=click.Path(exists=True), help="Scope configuration file")
@click.option("--watch", "-w", is_flag=True, help="Watch workflow progress")
@click.option("--params", "-p", type=str, help="Additional parameters as JSON")
def run_workflow(template: str, target: str, scope: Optional[str], watch: bool, params: Optional[str]):
    """Run a workflow from a template.

    TEMPLATE is the workflow template name.

    Examples:
        kai-cli workflow run recon-full --target example.com
        kai-cli workflow run web-app-scan --target example.com --watch
        kai-cli workflow run custom --target example.com --params '{"depth": 3}'
    """
    print_header("Run Workflow", f"Template: {template} | Target: {target}")

    # Load scope if provided
    scope_config = {}
    if scope:
        try:
            with open(scope) as f:
                scope_config = json.load(f)
            print_info(f"Loaded scope from {scope}")
        except Exception as e:
            print_error(f"Failed to load scope: {e}")
            return

    # Parse additional params
    extra_params = {}
    if params:
        try:
            extra_params = json.loads(params)
        except json.JSONDecodeError:
            print_error("Invalid JSON in params")
            return

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        # Create workflow
        payload = {
            "template": template,
            "target": target,
            "scope": scope_config,
            **extra_params
        }

        response = client.post("/api/v1/orchestration/workflows/hunt", params={"target": target}, json=scope_config)

        if response.status_code == 200:
            data = response.json()
            workflow_id = data.get("workflow_id")
            print_success(f"Workflow created: {workflow_id}")

            if watch:
                asyncio.run(_watch_workflow(workflow_id))
            else:
                print_info(f"Use 'kai-cli workflow status {workflow_id}' to check progress")
        else:
            print_error(f"Failed to create workflow: {response.text}")

    except Exception as e:
        print_error(f"Error creating workflow: {e}")


@workflow.command("status")
@click.argument("workflow_id")
@click.option("--watch", "-w", is_flag=True, help="Watch workflow progress")
def workflow_status(workflow_id: str, watch: bool):
    """Check status of a workflow."""
    if watch:
        asyncio.run(_watch_workflow(workflow_id))
        return

    print_header("Workflow Status", f"ID: {workflow_id}")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.get(f"/api/v1/orchestration/workflows/{workflow_id}")

        if response.status_code == 200:
            data = response.json()
            _display_workflow_details(data)
        else:
            print_error(f"Workflow not found: {workflow_id}")

    except Exception as e:
        print_error(f"Error fetching workflow: {e}")


@workflow.command("cancel")
@click.argument("workflow_id")
@click.option("--force", "-f", is_flag=True, help="Force cancel without confirmation")
def cancel_workflow(workflow_id: str, force: bool):
    """Cancel a running workflow."""
    if not force and not confirm_action(f"Cancel workflow {workflow_id}?"):
        print_info("Cancelled")
        return

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.post(f"/api/v1/orchestration/workflows/{workflow_id}/cancel")

        if response.status_code == 200:
            print_success(f"Workflow {workflow_id} cancelled")
        else:
            print_error(f"Failed to cancel workflow: {response.text}")

    except Exception as e:
        print_error(f"Error cancelling workflow: {e}")


@workflow.command("templates")
@click.option("--category", "-c", type=str, help="Filter by category")
def list_templates(category: Optional[str]):
    """List available workflow templates."""
    print_header("Workflow Templates")

    # Built-in templates
    templates = [
        ["recon-full", "Full reconnaissance workflow", "recon", "TIER 0"],
        ["recon-passive", "Passive reconnaissance only", "recon", "TIER 0"],
        ["web-app-scan", "Web application vulnerability scan", "scanning", "TIER 0-1"],
        ["api-scan", "API security scan", "scanning", "TIER 0-1"],
        ["nuclei-all", "Run all Nuclei templates", "scanning", "TIER 1"],
        ["nuclei-cves", "Run CVE Nuclei templates", "scanning", "TIER 1"],
        ["sqli-hunt", "SQL injection hunting", "exploitation", "TIER 2"],
        ["xss-hunt", "XSS vulnerability hunting", "exploitation", "TIER 2"],
        ["full-hunt", "Complete vulnerability hunt", "full", "TIER 0-2"],
        ["validation", "Finding validation workflow", "validation", "TIER 1"],
        ["chain-analysis", "Exploit chain analysis", "analysis", "TIER 1"],
    ]

    if category:
        templates = [t for t in templates if category.lower() in t[2].lower()]

    table = create_table(
        "Available Templates",
        ["Name", "Description", "Category", "Tier"],
        templates,
        styles=["cyan", None, "green", "yellow"]
    )

    console.print(table)


@workflow.command("create")
@click.argument("name")
@click.option("--description", "-d", type=str, help="Workflow description")
@click.option("--steps", "-s", type=str, required=True, help="Workflow steps as JSON array")
@click.option("--save", type=click.Path(), help="Save workflow to file")
def create_workflow(name: str, description: Optional[str], steps: str, save: Optional[str]):
    """Create a custom workflow.

    Examples:
        kai-cli workflow create my-workflow --steps '[{"tool": "nmap"}, {"tool": "nuclei"}]'
    """
    print_header("Create Workflow", f"Name: {name}")

    try:
        steps_data = json.loads(steps)
    except json.JSONDecodeError:
        print_error("Invalid JSON in steps")
        return

    workflow_def = {
        "name": name,
        "description": description or f"Custom workflow: {name}",
        "steps": steps_data,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    if save:
        try:
            with open(save, "w") as f:
                json.dump(workflow_def, f, indent=2)
            print_success(f"Workflow saved to {save}")
        except Exception as e:
            print_error(f"Failed to save workflow: {e}")
            return

    # Display workflow
    console.print(f"\n[bold]Workflow:[/bold] {name}")
    console.print(f"[bold]Steps:[/bold]")
    for i, step in enumerate(steps_data, 1):
        console.print(f"  {i}. {step.get('tool', step.get('action', 'Unknown'))}")

    print_success("Workflow created")


@workflow.command("graph")
@click.argument("workflow_id")
def show_workflow_graph(workflow_id: str):
    """Show workflow execution graph."""
    print_header("Workflow Graph", f"ID: {workflow_id}")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.get(f"/api/v1/orchestration/workflows/{workflow_id}")

        if response.status_code == 200:
            data = response.json()
            steps = data.get("steps", [])

            if steps:
                console.print("\n[bold]Execution Graph:[/bold]\n")
                for i, step in enumerate(steps):
                    status = step.get("status", "pending")
                    status_color = {
                        "completed": "green",
                        "running": "yellow",
                        "failed": "red",
                        "pending": "dim"
                    }.get(status, "white")

                    connector = " --> " if i < len(steps) - 1 else ""
                    console.print(f"  [{status_color}][{step.get('name', f'Step {i+1}')}][/{status_color}]{connector}", end="")
                console.print()
            else:
                print_info("No steps in workflow")
        else:
            print_error(f"Workflow not found: {workflow_id}")

    except Exception as e:
        print_error(f"Error fetching workflow: {e}")


# Helper functions

async def _watch_workflow(workflow_id: str):
    """Watch workflow progress in real-time."""
    print_header("Watching Workflow", f"ID: {workflow_id}")

    with create_progress() as progress:
        task = progress.add_task("[green]Running workflow...", total=100)

        while True:
            try:
                client = get_api_client()
                response = client.get(f"/api/v1/orchestration/workflows/{workflow_id}")

                if response.status_code != 200:
                    print_error(f"Failed to fetch workflow status")
                    break

                data = response.json()
                status = data.get("status", "unknown")
                current_progress = data.get("progress", 0)

                progress.update(task, completed=current_progress, description=f"[green]{status}...")

                if status == "completed":
                    print_success("Workflow completed")
                    _display_workflow_details(data)
                    break
                elif status in ["failed", "cancelled"]:
                    print_error(f"Workflow {status}")
                    break

                await asyncio.sleep(2)

            except Exception as e:
                print_error(f"Error: {e}")
                break


def _display_workflow_details(data: dict):
    """Display detailed workflow information."""
    status = {
        "Workflow ID": data.get("workflow_id", data.get("id")),
        "Name": data.get("name", "N/A"),
        "Status": data.get("status"),
        "Target": data.get("target"),
        "Progress": f"{data.get('progress', 0)}%",
        "Created": data.get("created_at", "N/A"),
    }

    console.print(create_status_panel("Workflow Details", status))

    # Steps
    steps = data.get("steps", [])
    if steps:
        console.print()
        step_rows = [
            [
                str(i + 1),
                s.get("name", f"Step {i + 1}"),
                s.get("status", "pending"),
                s.get("duration", "N/A")
            ]
            for i, s in enumerate(steps)
        ]
        console.print(create_table("Steps", ["#", "Name", "Status", "Duration"], step_rows))

    # Findings
    findings = data.get("findings", [])
    if findings:
        console.print()
        console.print(f"[bold]Findings:[/bold] {len(findings)}")
