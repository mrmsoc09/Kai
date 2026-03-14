"""
Bug bounty continuous hunting CLI operations.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import click

from ...core.secret_manager import get_secret_manager
from ..ui import console, create_table, print_error, print_header, print_info, print_success


def _client():
    try:
        import httpx

        base_url = os.getenv("K1_API_URL", "http://localhost:8080")
        headers: dict[str, str] = {}

        secret_manager = None
        try:
            secret_manager = get_secret_manager()
        except Exception:
            secret_manager = None

        access_token = (
            (secret_manager.get_optional("K1_API_TOKEN") if secret_manager else None) or ""
        ).strip()
        if not access_token:
            dev_token = (
                (secret_manager.get_optional("K1_DEV_TOKEN") if secret_manager else None) or ""
            ).strip()
            if dev_token:
                try:
                    login = httpx.post(
                        f"{base_url.rstrip('/')}/auth/login",
                        json={"token": dev_token},
                        timeout=30.0,
                    )
                    if login.status_code == 200:
                        payload = login.json()
                        candidate = str(payload.get("access_token") or "").strip()
                        if candidate:
                            access_token = candidate
                except Exception:
                    access_token = ""

        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        return httpx.Client(
            base_url=base_url,
            timeout=120.0,
            headers=headers or None,
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


@bug_bounty.command("phase7-run")
@click.option("--program-id", default=None)
@click.option("--apply-adaptive/--no-apply-adaptive", default=True, show_default=True)
@click.option("--actor", default="cli.phase7.prediction", show_default=True)
def phase7_run(program_id: str | None, apply_adaptive: bool, actor: str) -> None:
    """Run deterministic Phase 7 prediction and opportunity selection."""
    print_header("Phase 7 Prediction Run")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    payload = {
        "actor": actor,
        "program_id": program_id,
        "apply_adaptive": apply_adaptive,
    }
    response = client.post("/api/v1/bug-bounty/phase7/run", json=payload)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    rows = [[k, body.get(k)] for k in sorted(body.keys())]
    console.print(create_table("Phase 7 Summary", ["Metric", "Value"], rows))


@bug_bounty.command("phase7-predictions")
@click.option("--program-id", default=None)
@click.option("--limit", default=50, type=int, show_default=True)
def phase7_predictions(program_id: str | None, limit: int) -> None:
    """List vulnerability prediction outputs."""
    print_header("Phase 7 Predictions")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    response = client.get("/api/v1/bug-bounty/phase7/predictions", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("scope_target_id"),
                item.get("predicted_vulnerability_type"),
                item.get("reportability_score"),
                item.get("duplicate_risk_score"),
                item.get("evidence_completeness_score"),
            ]
        )
    if not rows:
        print_info("No predictions found.")
        return
    console.print(
        create_table(
            "Predictions",
            ["ID", "Target", "Type", "Reportability", "Duplicate", "Evidence"],
            rows,
        )
    )


@bug_bounty.command("phase7-rankings")
@click.option("--program-id", default=None)
@click.option("--subject-type", default=None)
@click.option("--limit", default=50, type=int, show_default=True)
def phase7_rankings(program_id: str | None, subject_type: str | None, limit: int) -> None:
    """List opportunity selection rankings."""
    print_header("Phase 7 Opportunity Rankings")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    if subject_type:
        params["subject_type"] = subject_type
    response = client.get("/api/v1/bug-bounty/phase7/opportunity-rankings", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("subject_type"),
                item.get("subject_key"),
                item.get("selection_score"),
                item.get("priority_rank"),
            ]
        )
    if not rows:
        print_info("No rankings found.")
        return
    console.print(
        create_table(
            "Opportunity Rankings",
            ["ID", "Subject Type", "Subject", "Score", "Rank"],
            rows,
        )
    )


@bug_bounty.command("phase7-recommendations")
@click.option("--program-id", default=None)
@click.option("--status", "recommendation_status", default=None)
@click.option("--limit", default=50, type=int, show_default=True)
def phase7_recommendations(
    program_id: str | None,
    recommendation_status: str | None,
    limit: int,
) -> None:
    """List next-best-workflow recommendations."""
    print_header("Phase 7 Recommendations")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    if recommendation_status:
        params["recommendation_status"] = recommendation_status
    response = client.get("/api/v1/bug-bounty/phase7/recommendations", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("recommended_workflow"),
                item.get("recommended_action"),
                item.get("recommendation_status"),
                item.get("action_priority"),
            ]
        )
    if not rows:
        print_info("No recommendations found.")
        return
    console.print(
        create_table(
            "Recommendations",
            ["ID", "Workflow", "Action", "Status", "Priority"],
            rows,
        )
    )


@bug_bounty.command("phase7-analyst-support")
@click.option("--program-id", default=None)
@click.option("--limit", default=20, type=int, show_default=True)
def phase7_analyst_support(program_id: str | None, limit: int) -> None:
    """Generate analyst decision-support summary for Phase 7 outputs."""
    print_header("Phase 7 Analyst Support")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    response = client.get("/api/v1/bug-bounty/phase7/analyst-support", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    print_success(
        "Support summary generated: "
        f"{len(body.get('top_predictions') or [])} predictions, "
        f"{len(body.get('top_target_yields') or [])} target yields."
    )
    console.print_json(data=body)


@bug_bounty.command("alerts-sync")
@click.option("--program-id", default=None)
@click.option("--cooldown-minutes", default=120, type=int, show_default=True)
@click.option("--actor", default="cli.phase9.alerts", show_default=True)
def alerts_sync(program_id: str | None, cooldown_minutes: int, actor: str) -> None:
    """Run Phase 9 alert synchronization."""
    print_header("Phase 9 Alert Sync")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    payload = {
        "program_id": program_id,
        "cooldown_minutes": max(1, cooldown_minutes),
        "actor": actor,
    }
    response = client.post("/api/v1/bug-bounty/alerts/sync", json=payload)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    rows = [[k, body.get(k)] for k in sorted(body.keys())]
    console.print(create_table("Alert Sync", ["Metric", "Value"], rows))


@bug_bounty.command("alerts")
@click.option("--program-id", default=None)
@click.option("--status", default=None)
@click.option("--severity", default=None)
@click.option("--limit", default=100, type=int, show_default=True)
def list_alerts(program_id: str | None, status: str | None, severity: str | None, limit: int) -> None:
    """List persisted alert records."""
    print_header("Phase 9 Alerts")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    if status:
        params["status"] = status
    if severity:
        params["severity"] = severity
    response = client.get("/api/v1/bug-bounty/alerts", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("alert_type"),
                item.get("severity"),
                item.get("urgency"),
                item.get("status"),
                item.get("occurrence_count"),
            ]
        )
    if not rows:
        print_info("No alerts found.")
        return
    console.print(
        create_table(
            "Alerts",
            ["ID", "Type", "Severity", "Urgency", "Status", "Count"],
            rows,
        )
    )


@bug_bounty.command("alert-ack")
@click.option("--alert-id", required=True, help="Alert UUID")
@click.option("--actor", default="cli.phase9.alerts", show_default=True)
@click.option("--note", default=None)
def acknowledge_alert(alert_id: str, actor: str, note: str | None) -> None:
    """Acknowledge an alert."""
    print_header("Acknowledge Alert")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    response = client.post(
        f"/api/v1/bug-bounty/alerts/{alert_id}/acknowledge",
        json={"actor": actor, "note": note},
    )
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    print_success(f"Acknowledged alert {alert_id}")


@bug_bounty.command("alert-resolve")
@click.option("--alert-id", required=True, help="Alert UUID")
@click.option("--actor", default="cli.phase9.alerts", show_default=True)
@click.option("--note", default=None)
def resolve_alert(alert_id: str, actor: str, note: str | None) -> None:
    """Resolve an alert."""
    print_header("Resolve Alert")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    response = client.post(
        f"/api/v1/bug-bounty/alerts/{alert_id}/resolve",
        json={"actor": actor, "note": note},
    )
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    print_success(f"Resolved alert {alert_id}")


@bug_bounty.command("cases")
@click.option("--program-id", default=None)
@click.option("--status", default=None)
@click.option("--priority", default=None)
@click.option("--owner", default=None)
@click.option("--limit", default=100, type=int, show_default=True)
def list_cases(
    program_id: str | None,
    status: str | None,
    priority: str | None,
    owner: str | None,
    limit: int,
) -> None:
    """List analyst case records."""
    print_header("Phase 9 Cases")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    if status:
        params["status"] = status
    if priority:
        params["priority"] = priority
    if owner:
        params["owner"] = owner
    response = client.get("/api/v1/bug-bounty/cases", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("title"),
                item.get("priority"),
                item.get("status"),
                item.get("owner"),
            ]
        )
    if not rows:
        print_info("No cases found.")
        return
    console.print(create_table("Cases", ["ID", "Title", "Priority", "Status", "Owner"], rows))


@bug_bounty.command("case-update")
@click.option("--case-id", required=True, help="Case UUID")
@click.option("--status", default=None)
@click.option("--priority", default=None)
@click.option("--summary", default=None)
@click.option("--reasoning-summary", default=None)
@click.option("--closure-reason", default=None)
@click.option("--actor", default="cli.phase9.cases", show_default=True)
def case_update(
    case_id: str,
    status: str | None,
    priority: str | None,
    summary: str | None,
    reasoning_summary: str | None,
    closure_reason: str | None,
    actor: str,
) -> None:
    """Update case status/priority/summary."""
    print_header("Case Update")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    payload = {
        "status": status,
        "priority": priority,
        "summary": summary,
        "reasoning_summary": reasoning_summary,
        "closure_reason": closure_reason,
        "actor": actor,
    }
    response = client.patch(f"/api/v1/bug-bounty/cases/{case_id}", json=payload)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    print_success(f"Updated case {case_id}")


@bug_bounty.command("case-assign")
@click.option("--case-id", required=True, help="Case UUID")
@click.option("--owner", required=True, help="Owner identity")
@click.option("--actor", default="cli.phase9.cases", show_default=True)
def case_assign(case_id: str, owner: str, actor: str) -> None:
    """Assign or reassign a case owner."""
    print_header("Case Assignment")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    response = client.post(
        f"/api/v1/bug-bounty/cases/{case_id}/assign",
        json={"owner": owner, "actor": actor},
    )
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    print_success(f"Assigned case {case_id} to {owner}")


@bug_bounty.command("case-note")
@click.option("--case-id", required=True, help="Case UUID")
@click.option("--note", required=True)
@click.option("--actor", default="cli.phase9.cases", show_default=True)
def case_note(case_id: str, note: str, actor: str) -> None:
    """Append an analyst note to a case."""
    print_header("Case Note")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    response = client.post(
        f"/api/v1/bug-bounty/cases/{case_id}/notes",
        json={"note": note, "actor": actor},
    )
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    print_success(f"Added note to case {case_id}")


@bug_bounty.command("phase10-run")
@click.option("--program-id", default=None)
@click.option("--window-days", default=30, type=int, show_default=True)
@click.option("--actor", default="cli.phase10.retrospective", show_default=True)
def phase10_run(program_id: str | None, window_days: int, actor: str) -> None:
    """Run retrospective learning pass and persist feedback outcomes."""
    print_header("Phase 10 Retrospective Run")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    payload = {
        "actor": actor,
        "program_id": program_id,
        "window_days": max(1, window_days),
    }
    response = client.post("/api/v1/bug-bounty/retrospective/run", json=payload)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    rows = [[k, body.get(k)] for k in sorted(body.keys())]
    console.print(create_table("Phase 10 Summary", ["Metric", "Value"], rows))


@bug_bounty.command("phase10-summary")
@click.option("--program-id", default=None)
@click.option("--window-days", default=30, type=int, show_default=True)
def phase10_summary(program_id: str | None, window_days: int) -> None:
    """Show retrospective intelligence summary."""
    print_header("Phase 10 Retrospective Summary")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"window_days": max(1, window_days)}
    if program_id:
        params["program_id"] = program_id
    response = client.get("/api/v1/bug-bounty/retrospective/summary", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    console.print_json(data=response.json())


@bug_bounty.command("phase10-workflows")
@click.option("--program-id", default=None)
@click.option("--limit", default=50, type=int, show_default=True)
def phase10_workflows(program_id: str | None, limit: int) -> None:
    """List workflow retrospective performance records."""
    print_header("Phase 10 Workflow Performance")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    response = client.get("/api/v1/bug-bounty/retrospective/workflows", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("workflow_template"),
                item.get("workflow_signal_value"),
                item.get("workflow_reportability_rate"),
                item.get("workflow_noise_rate"),
            ]
        )
    if not rows:
        print_info("No workflow retrospective records found.")
        return
    console.print(
        create_table(
            "Workflow Performance",
            ["ID", "Template", "Signal Value", "Reportability", "Noise"],
            rows,
        )
    )


@bug_bounty.command("phase10-targets")
@click.option("--program-id", default=None)
@click.option("--limit", default=50, type=int, show_default=True)
def phase10_targets(program_id: str | None, limit: int) -> None:
    """List target retrospective performance records."""
    print_header("Phase 10 Target Performance")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    response = client.get("/api/v1/bug-bounty/retrospective/targets", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("scope_target_id"),
                item.get("target_yield_score"),
                item.get("target_reportability_rate"),
                item.get("target_duplicate_rate"),
            ]
        )
    if not rows:
        print_info("No target retrospective records found.")
        return
    console.print(
        create_table(
            "Target Performance",
            ["ID", "Target", "Yield", "Reportability", "Duplicate"],
            rows,
        )
    )


@bug_bounty.command("phase10-recommendations")
@click.option("--program-id", default=None)
@click.option("--status", "outcome_status", default=None)
@click.option("--limit", default=50, type=int, show_default=True)
def phase10_recommendations(
    program_id: str | None,
    outcome_status: str | None,
    limit: int,
) -> None:
    """List recommendation outcomes for retrospective quality analysis."""
    print_header("Phase 10 Recommendation Outcomes")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    if outcome_status:
        params["outcome_status"] = outcome_status
    response = client.get("/api/v1/bug-bounty/retrospective/recommendations", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("recommendation_record_id"),
                item.get("outcome_status"),
                item.get("success_score"),
                item.get("decided_at"),
            ]
        )
    if not rows:
        print_info("No recommendation outcome records found.")
        return
    console.print(
        create_table(
            "Recommendation Outcomes",
            ["ID", "Recommendation", "Outcome", "Success", "Decided At"],
            rows,
        )
    )


@bug_bounty.command("phase10-5-agents-sync")
@click.option("--actor", default="cli.phase10_5.registry", show_default=True)
def phase10_5_agents_sync(actor: str) -> None:
    """Synchronize canonical Phase 10.5 specialized agent registry."""
    print_header("Phase 10.5 Agent Registry Sync")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    response = client.post("/api/v1/bug-bounty/agents/sync", json={"actor": actor})
    if response.status_code != 200:
        print_error(f"Sync failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    print_success(
        f"Registry synced (created={body.get('created')}, updated={body.get('updated')}, total={body.get('total')})"
    )


@bug_bounty.command("phase10-5-agents")
@click.option("--enabled-only", is_flag=True, default=False)
@click.option("--category", default=None)
@click.option("--limit", default=200, type=int, show_default=True)
def phase10_5_agents(enabled_only: bool, category: str | None, limit: int) -> None:
    """List registered Phase 10.5 agents."""
    print_header("Phase 10.5 Agents")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params: dict[str, str | int | bool] = {"limit": max(1, limit), "enabled_only": enabled_only}
    if category:
        params["category"] = category
    response = client.get("/api/v1/bug-bounty/agents", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("agent_id"),
                item.get("category"),
                "yes" if item.get("enabled") else "no",
                item.get("model_preference"),
                item.get("confidence_threshold"),
                item.get("escalation_agent_id") or "-",
            ]
        )
    if not rows:
        print_info("No agents found.")
        return
    console.print(
        create_table(
            "Agent Registry",
            ["Agent ID", "Category", "Enabled", "Model", "Threshold", "Escalation"],
            rows,
        )
    )


@bug_bounty.command("phase10-5-agent-run")
@click.option("--agent-id", required=True, help="Registered agent_id")
@click.option("--program-id", default=None, help="Program UUID")
@click.option("--scope-target-id", default=None, help="Scope target UUID")
@click.option("--workflow-run-id", default=None, help="Workflow run UUID")
@click.option("--analyst-case-id", default=None, help="Analyst case UUID")
@click.option("--analyst-queue-item-id", default=None, help="Analyst queue item UUID")
@click.option("--input-json", "input_json_path", default=None, help="Path to input JSON payload")
@click.option("--actor", default="cli.phase10_5.agent", show_default=True)
def phase10_5_agent_run(
    agent_id: str,
    program_id: str | None,
    scope_target_id: str | None,
    workflow_run_id: str | None,
    analyst_case_id: str | None,
    analyst_queue_item_id: str | None,
    input_json_path: str | None,
    actor: str,
) -> None:
    """Run a Phase 10.5 specialized agent and persist execution history."""
    print_header("Phase 10.5 Agent Run")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)

    input_payload: dict[str, object] = {}
    if input_json_path:
        input_payload = json.loads(Path(input_json_path).read_text(encoding="utf-8"))

    payload: dict[str, object] = {"actor": actor, "input_payload": input_payload}
    if program_id:
        payload["program_id"] = program_id
    if scope_target_id:
        payload["scope_target_id"] = scope_target_id
    if workflow_run_id:
        payload["workflow_run_id"] = workflow_run_id
    if analyst_case_id:
        payload["analyst_case_id"] = analyst_case_id
    if analyst_queue_item_id:
        payload["analyst_queue_item_id"] = analyst_queue_item_id

    response = client.post(f"/api/v1/bug-bounty/agents/{agent_id}/run", json=payload)
    if response.status_code != 200:
        print_error(f"Agent run failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    print_success(
        f"Execution {body.get('id')} status={body.get('execution_status')} confidence={body.get('confidence')}"
    )
    summary_rows = [
        ["Agent", body.get("agent_id")],
        ["Model", body.get("model_used")],
        ["Routing", body.get("routing_policy")],
        ["Duration (ms)", body.get("duration_ms")],
        ["Escalation Taken", body.get("escalation_taken")],
    ]
    console.print(create_table("Agent Execution Summary", ["Field", "Value"], summary_rows))


@bug_bounty.command("phase10-5-agent-executions")
@click.option("--program-id", default=None)
@click.option("--agent-id", default=None)
@click.option("--status", "execution_status", default=None)
@click.option("--limit", default=100, type=int, show_default=True)
def phase10_5_agent_executions(
    program_id: str | None,
    agent_id: str | None,
    execution_status: str | None,
    limit: int,
) -> None:
    """List Phase 10.5 agent execution history."""
    print_header("Phase 10.5 Agent Executions")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params: dict[str, str | int] = {"limit": max(1, limit)}
    if program_id:
        params["program_id"] = program_id
    if agent_id:
        params["agent_id"] = agent_id
    if execution_status:
        params["execution_status"] = execution_status
    response = client.get("/api/v1/bug-bounty/agents/executions", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("agent_id"),
                item.get("execution_status"),
                item.get("confidence"),
                item.get("model_used"),
                item.get("started_at"),
            ]
        )
    if not rows:
        print_info("No agent executions found.")
        return
    console.print(
        create_table(
            "Agent Executions",
            ["Execution ID", "Agent", "Status", "Confidence", "Model", "Started"],
            rows,
        )
    )


@bug_bounty.command("phase10-5-agent-evaluate")
@click.option("--agent-id", required=True)
@click.option("--benchmark-name", default="default", show_default=True)
@click.option("--actor", default="cli.phase10_5.agent_eval", show_default=True)
def phase10_5_agent_evaluate(agent_id: str, benchmark_name: str, actor: str) -> None:
    """Run Phase 10.5 evaluation harness for a specific agent."""
    print_header("Phase 10.5 Agent Evaluation")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    payload = {"actor": actor, "benchmark_name": benchmark_name}
    response = client.post(f"/api/v1/bug-bounty/agents/{agent_id}/evaluate", json=payload)
    if response.status_code != 200:
        print_error(f"Evaluation failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    body = response.json()
    print_success(
        f"Evaluation {body.get('id')} status={body.get('status')} success_rate={body.get('success_rate')}"
    )


@bug_bounty.command("phase10-5-agent-evaluations")
@click.option("--agent-id", default=None)
@click.option("--status", default=None)
@click.option("--limit", default=100, type=int, show_default=True)
def phase10_5_agent_evaluations(
    agent_id: str | None,
    status: str | None,
    limit: int,
) -> None:
    """List Phase 10.5 agent evaluation records."""
    print_header("Phase 10.5 Agent Evaluations")
    client = _client()
    if client is None:
        print_error("httpx is unavailable")
        raise SystemExit(2)
    params: dict[str, str | int] = {"limit": max(1, limit)}
    if agent_id:
        params["agent_id"] = agent_id
    if status:
        params["status"] = status
    response = client.get("/api/v1/bug-bounty/agents/evaluations", params=params)
    if response.status_code != 200:
        print_error(f"Failed: {response.status_code} {response.text}")
        raise SystemExit(1)
    rows = []
    for item in response.json():
        rows.append(
            [
                item.get("id"),
                item.get("agent_id"),
                item.get("benchmark_name"),
                item.get("status"),
                item.get("success_rate"),
                item.get("executed_at"),
            ]
        )
    if not rows:
        print_info("No agent evaluations found.")
        return
    console.print(
        create_table(
            "Agent Evaluations",
            ["Evaluation ID", "Agent", "Benchmark", "Status", "Success Rate", "Executed"],
            rows,
        )
    )
