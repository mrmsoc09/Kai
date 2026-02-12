"""
Orchestrator command for managing the KaiOrchestrator.

Usage:
    kai-cli orchestrator status
    kai-cli orchestrator scope show
    kai-cli orchestrator approvals pending
"""

import click
import json
from typing import Optional
from datetime import datetime

from ..ui import (
    console,
    print_header,
    print_success,
    print_error,
    print_warning,
    print_info,
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
def orchestrator():
    """KaiOrchestrator management operations."""
    pass


@orchestrator.command("status")
def orchestrator_status():
    """Show KaiOrchestrator status."""
    print_header("KaiOrchestrator Status")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.get("/api/orchestrator/status")

        if response.status_code == 200:
            data = response.json()

            status = {
                "Status": data.get("status", "unknown"),
                "Scope Loaded": data.get("scope_loaded", False),
                "Permission Slips": data.get("permission_slip_count", 0),
                "Active Operations": data.get("active_operations", 0),
                "Audit Entries": data.get("audit_entries", 0),
            }

            console.print(create_status_panel("Orchestrator", status))

            # Component status
            components = data.get("components", {})
            if components:
                console.print()
                console.print(create_status_panel("Components", {
                    "ScopeGuardian": components.get("scope_guardian", "N/A"),
                    "IntentValidator": components.get("intent_validator", "N/A"),
                    "AuditLogger": components.get("audit_logger", "N/A"),
                    "PermissionManager": components.get("permission_manager", "N/A"),
                }))
        else:
            # Try healthz as fallback
            response = client.get("/healthz")
            if response.status_code == 200:
                print_success("K1 API is healthy")
                print_info("Use 'kai-cli orchestrator scope show' to check scope configuration")
            else:
                print_error("Failed to fetch orchestrator status")

    except Exception as e:
        print_error(f"Error fetching status: {e}")


@orchestrator.command("health")
def health_check():
    """Perform comprehensive health check."""
    print_header("Health Check")

    client = get_api_client()
    if not client:
        print_error("API client not available - is the K1 server running?")
        return

    checks = []

    # Check main API
    try:
        response = client.get("/healthz")
        checks.append(["API Server", "healthy" if response.status_code == 200 else "unhealthy", response.status_code])
    except Exception as e:
        checks.append(["API Server", "unreachable", str(e)])

    # Check Agent Zero
    try:
        response = client.get("/api/v1/agent-zero/health")
        checks.append(["Agent Zero", "healthy" if response.status_code == 200 else "degraded", response.status_code])
    except:
        checks.append(["Agent Zero", "unavailable", "-"])

    # Check Autonomous System
    try:
        response = client.get("/api/autonomous/status")
        checks.append(["Autonomous System", "healthy" if response.status_code == 200 else "degraded", response.status_code])
    except:
        checks.append(["Autonomous System", "unavailable", "-"])

    # Check Detection Module
    try:
        response = client.get("/findings/detection/stats")
        checks.append(["Detection Module", "healthy" if response.status_code == 200 else "degraded", response.status_code])
    except:
        checks.append(["Detection Module", "unavailable", "-"])

    # Display results
    table = create_table(
        "Health Check Results",
        ["Component", "Status", "Code"],
        [[c[0], f"[green]{c[1]}[/green]" if c[1] == "healthy" else f"[red]{c[1]}[/red]", str(c[2])] for c in checks]
    )
    console.print(table)

    healthy_count = sum(1 for c in checks if c[1] == "healthy")
    total = len(checks)

    if healthy_count == total:
        print_success(f"All {total} components healthy")
    else:
        print_warning(f"{healthy_count}/{total} components healthy")


@orchestrator.group("scope")
def scope():
    """Scope management operations."""
    pass


@scope.command("show")
def show_scope():
    """Show current scope configuration."""
    print_header("Scope Configuration")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.get("/api/orchestrator/scope")

        if response.status_code == 200:
            data = response.json()

            # Allowed targets
            allowed = data.get("allowed_targets", [])
            if allowed:
                console.print("\n[bold]Allowed Targets:[/bold]")
                for target in allowed[:20]:
                    console.print(f"  [green]+[/green] {target}")
                if len(allowed) > 20:
                    console.print(f"  [dim]... and {len(allowed) - 20} more[/dim]")

            # Excluded targets
            excluded = data.get("excluded_targets", [])
            if excluded:
                console.print("\n[bold]Excluded Targets:[/bold]")
                for target in excluded[:10]:
                    console.print(f"  [red]-[/red] {target}")

            # Allowed operations
            operations = data.get("allowed_operations", [])
            if operations:
                console.print("\n[bold]Allowed Operations:[/bold]")
                for op in operations:
                    tier = op.get("tier", "N/A")
                    console.print(f"  [cyan]{op.get('name', 'Unknown')}[/cyan] (Tier {tier})")

            # Constraints
            constraints = data.get("constraints", {})
            if constraints:
                console.print()
                console.print(create_status_panel("Constraints", constraints))
        else:
            print_warning("No scope configuration found")
            print_info("Use 'kai-cli orchestrator scope load <file>' to load a scope")

    except Exception as e:
        print_error(f"Error fetching scope: {e}")


@scope.command("load")
@click.argument("scope_file", type=click.Path(exists=True))
def load_scope(scope_file: str):
    """Load a scope configuration file."""
    print_header("Load Scope", f"File: {scope_file}")

    try:
        with open(scope_file) as f:
            scope_config = json.load(f)
    except Exception as e:
        print_error(f"Failed to read scope file: {e}")
        return

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.post("/api/orchestrator/scope", json=scope_config)

        if response.status_code == 200:
            print_success("Scope configuration loaded")

            # Show summary
            targets = len(scope_config.get("allowed_targets", []))
            excluded = len(scope_config.get("excluded_targets", []))
            console.print(f"  Allowed targets: {targets}")
            console.print(f"  Excluded targets: {excluded}")
        else:
            print_error(f"Failed to load scope: {response.text}")

    except Exception as e:
        print_error(f"Error loading scope: {e}")


@scope.command("validate")
@click.argument("target")
def validate_target(target: str):
    """Validate if a target is in scope."""
    print_header("Validate Target", f"Target: {target}")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.post("/api/orchestrator/validate-target", json={"target": target})

        if response.status_code == 200:
            data = response.json()

            if data.get("in_scope"):
                print_success(f"Target {target} is IN SCOPE")
                if data.get("constraints"):
                    console.print("\n[bold]Constraints:[/bold]")
                    for key, value in data["constraints"].items():
                        console.print(f"  {key}: {value}")
            else:
                print_error(f"Target {target} is OUT OF SCOPE")
                reason = data.get("reason", "Not in allowed targets")
                console.print(f"  Reason: {reason}")
        else:
            print_error(f"Validation failed: {response.text}")

    except Exception as e:
        print_error(f"Error validating target: {e}")


@orchestrator.group("approvals")
def approvals():
    """Approval workflow management."""
    pass


@approvals.command("pending")
def list_pending_approvals():
    """List pending approval requests."""
    print_header("Pending Approvals")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.get("/api/v1/approvals/pending")

        if response.status_code == 200:
            data = response.json()
            pending = data.get("pending_requests", [])

            if pending:
                rows = [
                    [
                        r.get("request_id", "")[:8],
                        r.get("operation_type", "N/A"),
                        str(r.get("tier", "N/A")),
                        r.get("target", "N/A")[:30],
                        r.get("created_at", "N/A")[:19],
                    ]
                    for r in pending
                ]

                table = create_table(
                    f"Pending Approvals ({len(pending)})",
                    ["ID", "Operation", "Tier", "Target", "Created"],
                    rows
                )
                console.print(table)
            else:
                print_info("No pending approvals")
        else:
            print_error("Failed to fetch approvals")

    except Exception as e:
        print_error(f"Error fetching approvals: {e}")


@approvals.command("approve")
@click.argument("request_id")
@click.option("--reason", "-r", type=str, help="Approval reason")
def approve_request(request_id: str, reason: Optional[str]):
    """Approve a pending request."""
    print_header("Approve Request", f"ID: {request_id}")

    if not confirm_action(f"Approve request {request_id}?"):
        print_info("Cancelled")
        return

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        payload = {"request_id": request_id, "decision": "APPROVED"}
        if reason:
            payload["reason"] = reason

        response = client.post("/api/v1/approvals/decide", json=payload)

        if response.status_code == 200:
            print_success(f"Request {request_id} approved")
        else:
            print_error(f"Failed to approve: {response.text}")

    except Exception as e:
        print_error(f"Error approving request: {e}")


@approvals.command("reject")
@click.argument("request_id")
@click.option("--reason", "-r", type=str, required=True, help="Rejection reason")
def reject_request(request_id: str, reason: str):
    """Reject a pending request."""
    print_header("Reject Request", f"ID: {request_id}")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        payload = {"request_id": request_id, "decision": "REJECTED", "reason": reason}
        response = client.post("/api/v1/approvals/decide", json=payload)

        if response.status_code == 200:
            print_success(f"Request {request_id} rejected")
        else:
            print_error(f"Failed to reject: {response.text}")

    except Exception as e:
        print_error(f"Error rejecting request: {e}")


@orchestrator.group("audit")
def audit():
    """Audit log operations."""
    pass


@audit.command("list")
@click.option("--limit", "-l", type=int, default=50, help="Maximum entries to show")
@click.option("--operation", "-o", type=str, help="Filter by operation type")
@click.option("--target", "-t", type=str, help="Filter by target")
def list_audit_entries(limit: int, operation: Optional[str], target: Optional[str]):
    """List audit log entries."""
    print_header("Audit Log")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        params = {"limit": limit}
        if operation:
            params["operation"] = operation
        if target:
            params["target"] = target

        response = client.get("/api/orchestrator/audit", params=params)

        if response.status_code == 200:
            data = response.json()
            entries = data.get("entries", [])

            if entries:
                rows = [
                    [
                        e.get("timestamp", "")[:19],
                        e.get("operation", "N/A"),
                        e.get("target", "N/A")[:25],
                        e.get("status", "N/A"),
                        e.get("actor", "N/A"),
                    ]
                    for e in entries[:limit]
                ]

                table = create_table(
                    f"Audit Entries ({len(entries)})",
                    ["Timestamp", "Operation", "Target", "Status", "Actor"],
                    rows
                )
                console.print(table)
            else:
                print_info("No audit entries found")
        else:
            print_warning("Audit log not available")

    except Exception as e:
        print_error(f"Error fetching audit log: {e}")


@orchestrator.command("permissions")
def list_permission_slips():
    """List active permission slips."""
    print_header("Permission Slips")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        response = client.get("/api/orchestrator/permissions")

        if response.status_code == 200:
            data = response.json()
            slips = data.get("permission_slips", [])

            if slips:
                rows = [
                    [
                        s.get("slip_id", "")[:8],
                        s.get("operation", "N/A"),
                        s.get("target", "N/A")[:25],
                        s.get("granted_by", "N/A"),
                        s.get("expires_at", "N/A")[:19],
                    ]
                    for s in slips
                ]

                table = create_table(
                    f"Active Permission Slips ({len(slips)})",
                    ["ID", "Operation", "Target", "Granted By", "Expires"],
                    rows
                )
                console.print(table)
            else:
                print_info("No active permission slips")
        else:
            print_warning("Permission slips not available")

    except Exception as e:
        print_error(f"Error fetching permission slips: {e}")


@orchestrator.command("watchdog")
@click.option("--check", is_flag=True, help="Run watchdog check")
@click.option("--unsigned", is_flag=True, help="Show unsigned log entries")
def watchdog_status(check: bool, unsigned: bool):
    """Log watchdog operations."""
    print_header("Log Watchdog")

    client = get_api_client()
    if not client:
        print_error("API client not available")
        return

    try:
        if unsigned:
            response = client.get("/api/watchdog/unsigned")
            if response.status_code == 200:
                data = response.json()
                entries = data.get("unsigned_entries", [])

                if entries:
                    console.print(f"[warning]Found {len(entries)} unsigned critical entries[/warning]")
                    for entry in entries[:10]:
                        console.print(f"  - {entry.get('operation', 'N/A')}: {entry.get('target', 'N/A')}")
                else:
                    print_success("No unsigned critical entries found")
            else:
                print_error("Failed to check unsigned entries")
        elif check:
            response = client.post("/api/watchdog/scan")
            if response.status_code == 200:
                data = response.json()
                print_success("Watchdog scan completed")
                console.print(f"  Scanned: {data.get('entries_scanned', 0)} entries")
                console.print(f"  Alerts: {data.get('alerts_generated', 0)}")
            else:
                print_error("Watchdog scan failed")
        else:
            response = client.get("/api/watchdog/status")
            if response.status_code == 200:
                data = response.json()
                console.print(create_status_panel("Watchdog Status", {
                    "Status": data.get("status", "unknown"),
                    "Last Scan": data.get("last_scan", "N/A"),
                    "Entries Monitored": data.get("entries_monitored", 0),
                    "Alerts Pending": data.get("alerts_pending", 0),
                }))
            else:
                print_warning("Watchdog status unavailable")

    except Exception as e:
        print_error(f"Watchdog error: {e}")
