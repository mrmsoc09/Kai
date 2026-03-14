"""
Bug bounty continuous hunting CLI operations.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import click

from ..ui import console, create_table, print_error, print_header, print_info, print_success


def _client():
    try:
        import httpx

        return httpx.Client(
            base_url=os.getenv("K1_API_URL", "http://localhost:8000"),
            timeout=120.0,
        )
    except Exception:
        return None


@click.group(name="bug-bounty")
def bug_bounty() -> None:
    """Continuous bug bounty opportunity hunting operations."""
    pass


@bug_bounty.command("program-import")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
def program_import(path: str) -> None:
    """Import bug bounty program opportunity JSON payload."""
    print_header("Bug Bounty Program Import")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    response = client.post("/api/v1/bug-bounty/programs/import", json=payload)
    if response.status_code != 200:
        print_error(f"Import failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    print_success(f"Imported program: {body.get('name')} ({body.get('id')})")


@bug_bounty.command("programs")
def list_programs() -> None:
    """List persisted bug bounty programs."""
    print_header("Bug Bounty Programs")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    response = client.get("/api/v1/bug-bounty/programs")
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("name"),
                item.get("platform"),
                item.get("status"),
                item.get("program_key"),
            ]
        )
    if not rows:
        print_info("No programs found.")
        return
    console.print(create_table("Programs", ["ID", "Name", "Platform", "Status", "Key"], rows))


@bug_bounty.command("targets")
@click.option("--program-id", required=True, help="Program UUID")
def list_targets(program_id: str) -> None:
    """List monitored targets for a program."""
    print_header("Monitored Targets")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    response = client.get(f"/api/v1/bug-bounty/programs/{program_id}/targets")
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("target"),
                item.get("target_type"),
                "yes" if item.get("is_in_scope") else "no",
                "yes" if item.get("monitoring_enabled") else "no",
                item.get("monitoring_status"),
            ]
        )
    if not rows:
        print_info("No targets found.")
        return
    console.print(
        create_table(
            "Targets",
            ["ID", "Target", "Type", "In Scope", "Enabled", "Status"],
            rows,
        )
    )


@bug_bounty.command("schedule-create")
@click.option("--program-id", required=True, help="Program UUID")
@click.option("--scope-target-id", required=True, help="Scope target UUID")
@click.option("--template", "workflow_template", required=True, help="Workflow template name")
@click.option("--interval-minutes", type=int, default=60, show_default=True)
@click.option("--safe-mode/--unsafe-mode", default=True, show_default=True)
@click.option("--dry-run", is_flag=True, default=False)
def schedule_create(
    program_id: str,
    scope_target_id: str,
    workflow_template: str,
    interval_minutes: int,
    safe_mode: bool,
    dry_run: bool,
) -> None:
    """Create recurring bug bounty schedule."""
    print_header("Create Schedule")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    payload = {
        "program_id": program_id,
        "scope_target_id": scope_target_id,
        "workflow_template": workflow_template,
        "schedule_type": "interval",
        "interval_minutes": max(1, interval_minutes),
        "safe_mode": safe_mode,
        "dry_run": dry_run,
    }
    response = client.post("/api/v1/bug-bounty/schedules", json=payload)
    if response.status_code != 200:
        print_error(f"Create failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    print_success(f"Created schedule: {body.get('id')}")


@bug_bounty.command("schedules")
@click.option("--program-id", default=None)
@click.option("--status", default=None)
def list_schedules(program_id: str | None, status: str | None) -> None:
    """List schedules."""
    print_header("Schedules")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {}
    if program_id:
        params["program_id"] = program_id
    if status:
        params["status"] = status
    response = client.get("/api/v1/bug-bounty/schedules", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("workflow_template"),
                item.get("status"),
                item.get("next_scheduled_run_at"),
                item.get("last_run_status"),
            ]
        )
    if not rows:
        print_info("No schedules found.")
        return
    console.print(
        create_table(
            "Schedules",
            ["ID", "Template", "Status", "Next Run", "Last Run"],
            rows,
        )
    )


@bug_bounty.command("run-due")
@click.option("--limit", default=25, type=int, show_default=True)
def run_due(limit: int) -> None:
    """Trigger due schedules immediately."""
    print_header("Run Due Schedules")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    payload = {"actor": "cli.bug_bounty", "limit": max(1, limit)}
    response = client.post("/api/v1/bug-bounty/schedules/run-due", json=payload)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    print_success(f"Processed {len(body)} schedules")


@bug_bounty.command("dispatch-due")
@click.option("--limit", default=25, type=int, show_default=True)
def dispatch_due(limit: int) -> None:
    """Dispatch due schedules to Celery workers for parallel execution."""
    print_header("Dispatch Due Schedules")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    payload = {"actor": "cli.bug_bounty.dispatch", "limit": max(1, limit)}
    response = client.post("/api/v1/bug-bounty/schedules/dispatch-due", json=payload)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("schedule_id"),
                item.get("worker_task_id"),
                item.get("worker_role"),
                item.get("decision_status"),
            ]
        )
    if not rows:
        print_info("No due schedules found.")
        return
    console.print(
        create_table(
            "Dispatch Results",
            ["Schedule", "Task ID", "Worker Role", "Status"],
            rows,
        )
    )


@bug_bounty.command("schedule-trigger")
@click.option("--schedule-id", required=True, help="Schedule UUID")
@click.option("--force", is_flag=True, default=False, help="Force trigger even if readiness blocks")
@click.option("--actor", default="cli.bug_bounty", show_default=True)
def schedule_trigger(schedule_id: str, force: bool, actor: str) -> None:
    """Trigger a specific schedule immediately."""
    print_header("Trigger Schedule")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    response = client.post(
        f"/api/v1/bug-bounty/schedules/{schedule_id}/trigger",
        json={"actor": actor, "force": force},
    )
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    print_success(
        f"Schedule decision={body.get('decision_status')} reason={body.get('reason')}"
    )


@bug_bounty.command("scheduler-status")
@click.option("--program-id", default=None)
def scheduler_status(program_id: str | None) -> None:
    """Show scheduler status summary."""
    print_header("Scheduler Status")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"program_id": program_id} if program_id else None
    response = client.get("/api/v1/bug-bounty/schedules/status", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    rows = [[k, body.get(k)] for k in sorted(body.keys())]
    console.print(create_table("Scheduler", ["Metric", "Value"], rows))


@bug_bounty.command("readiness")
@click.option("--program-id", required=True)
@click.option("--scope-target-id", required=True)
@click.option("--template", "workflow_template", required=True)
@click.option("--safe-mode/--unsafe-mode", default=True, show_default=True)
@click.option("--persist/--no-persist", default=False, show_default=True)
def readiness_check(
    program_id: str,
    scope_target_id: str,
    workflow_template: str,
    safe_mode: bool,
    persist: bool,
) -> None:
    """Run preflight readiness check for a program target/template pair."""
    print_header("Readiness Check")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    response = client.get(
        "/api/v1/bug-bounty/readiness",
        params={
            "program_id": program_id,
            "scope_target_id": scope_target_id,
            "workflow_template": workflow_template,
            "safe_mode": str(safe_mode).lower(),
            "persist": str(persist).lower(),
        },
    )
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    print_success(f"{body.get('decision_status')}: {body.get('reason')}")
    console.print_json(data=body.get("details") or {})


@bug_bounty.command("candidates")
@click.option("--program-id", default=None)
@click.option("--status", default=None)
@click.option("--limit", default=100, type=int, show_default=True)
def list_candidates(program_id: str | None, status: str | None, limit: int) -> None:
    """List candidate findings in analyst queue."""
    print_header("Analyst Queue")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    if status:
        params["status"] = status
    response = client.get("/api/v1/bug-bounty/candidates", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("affected_asset"),
                item.get("vulnerability_type"),
                item.get("status"),
                item.get("reportability_score"),
            ]
        )
    if not rows:
        print_info("No candidates found.")
        return
    console.print(
        create_table(
            "Candidates",
            ["ID", "Asset", "Vulnerability", "Status", "Reportability"],
            rows,
        )
    )


@bug_bounty.command("candidate-update")
@click.option("--queue-item-id", required=True, help="Analyst queue item UUID")
@click.option("--status", required=True, help="New queue status")
@click.option("--assigned-to", default=None)
@click.option("--notes", default=None)
@click.option("--actor", default="cli.bug_bounty", show_default=True)
def candidate_update(
    queue_item_id: str,
    status: str,
    assigned_to: str | None,
    notes: str | None,
    actor: str,
) -> None:
    """Update analyst queue status/assignment."""
    print_header("Candidate Queue Update")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    payload = {
        "status": status,
        "assigned_to": assigned_to,
        "analyst_notes": notes,
        "actor": actor,
    }
    response = client.patch(
        f"/api/v1/bug-bounty/candidates/{queue_item_id}",
        json=payload,
    )
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    print_success(f"Queue item updated to {body.get('status')}")


@bug_bounty.command("report-draft")
@click.option("--queue-item-id", required=True, help="Analyst queue item UUID")
@click.option("--actor", default="cli.bug_bounty", show_default=True)
@click.option("--notes", default=None, help="Analyst notes to include in draft artifact")
def report_draft(queue_item_id: str, actor: str, notes: str | None) -> None:
    """Generate report draft artifact for a queue item."""
    print_header("Report Draft Generation")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    response = client.post(
        f"/api/v1/bug-bounty/candidates/{queue_item_id}/report-draft",
        json={"actor": actor, "analyst_notes": notes},
    )
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    print_success(f"Draft created: {body.get('draft_path')}")


@bug_bounty.command("deltas")
@click.option("--program-id", default=None)
@click.option("--limit", default=100, type=int, show_default=True)
def list_deltas(program_id: str | None, limit: int) -> None:
    """List recently detected workflow deltas."""
    print_header("Run Deltas")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    response = client.get("/api/v1/bug-bounty/deltas", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("delta_type"),
                item.get("change_type"),
                item.get("delta_key"),
                item.get("severity_hint"),
            ]
        )
    if not rows:
        print_info("No deltas found.")
        return
    console.print(create_table("Deltas", ["ID", "Type", "Change", "Key", "Severity"], rows))


@bug_bounty.command("inference-run")
@click.option("--program-id", default=None)
@click.option("--apply-adaptive/--no-apply-adaptive", default=True, show_default=True)
@click.option("--actor", default="cli.phase6.inference", show_default=True)
def inference_run(program_id: str | None, apply_adaptive: bool, actor: str) -> None:
    """Run deterministic Phase 6 inference and optional adaptive scheduling."""
    print_header("Phase 6 Inference Run")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    payload = {
        "actor": actor,
        "program_id": program_id,
        "apply_adaptive": apply_adaptive,
    }
    response = client.post("/api/v1/bug-bounty/inference/run", json=payload)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    rows = [[k, body.get(k)] for k in sorted(body.keys())]
    console.print(create_table("Inference Summary", ["Metric", "Value"], rows))


@bug_bounty.command("scores")
@click.option("--program-id", default=None)
@click.option("--limit", default=50, type=int, show_default=True)
def list_scores(program_id: str | None, limit: int) -> None:
    """List opportunity scores and next-best actions."""
    print_header("Opportunity Scores")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    response = client.get("/api/v1/bug-bounty/opportunity-scores", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("scope_target_id"),
                item.get("opportunity_score"),
                item.get("target_priority_score"),
                item.get("recommended_workflow"),
                item.get("next_best_action"),
            ]
        )
    if not rows:
        print_info("No opportunity scores found.")
        return
    console.print(
        create_table(
            "Opportunity Scores",
            ["ID", "Target", "Opp Score", "Priority", "Workflow", "Action"],
            rows,
        )
    )


@bug_bounty.command("swarm")
@click.option("--program-id", default=None)
@click.option("--role", default=None)
@click.option("--limit", default=50, type=int, show_default=True)
def list_swarm_outputs(program_id: str | None, role: str | None, limit: int) -> None:
    """List structured swarm reasoning outputs."""
    print_header("Swarm Reasoning Outputs")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    if role:
        params["agent_role"] = role
    response = client.get("/api/v1/bug-bounty/swarm-outputs", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        output = item.get("output_json") or {}
        rows.append(
            [
                item.get("id"),
                item.get("agent_role"),
                item.get("confidence_score"),
                output.get("recommended_workflow"),
                output.get("next_best_action"),
            ]
        )
    if not rows:
        print_info("No swarm outputs found.")
        return
    console.print(
        create_table(
            "Swarm Outputs",
            ["ID", "Role", "Confidence", "Workflow", "Action"],
            rows,
        )
    )


@bug_bounty.command("briefing")
@click.option("--program-id", default=None)
@click.option("--limit", default=20, type=int, show_default=True)
def analyst_briefing(program_id: str | None, limit: int) -> None:
    """Generate analyst briefing from phase 6 inference outputs."""
    print_header("Analyst Briefing")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    response = client.get("/api/v1/bug-bounty/analyst-briefing", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    top_targets = body.get("top_targets") or []
    top_candidates = body.get("top_candidates") or []
    print_success(
        f"Briefing generated with {len(top_targets)} prioritized targets and {len(top_candidates)} candidates."
    )
    console.print_json(data=body)
