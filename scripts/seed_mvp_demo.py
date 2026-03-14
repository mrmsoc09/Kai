#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx


DEFAULT_PAYLOAD_PATH = Path("config/mvp_program_example.json")


def _auth_headers(base_url: str) -> dict[str, str]:
    token = (os.getenv("K1_API_TOKEN", "") or "").strip()
    if not token:
        dev_token = (os.getenv("K1_DEV_TOKEN", "") or "").strip()
        if dev_token:
            response = httpx.post(
                f"{base_url.rstrip('/')}/auth/login",
                json={"token": dev_token},
                timeout=30.0,
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    "failed to bootstrap auth token from /auth/login; "
                    "set K1_API_TOKEN or valid K1_DEV_TOKEN"
                )
            token = str(response.json().get("access_token") or "").strip()
    if not token:
        raise RuntimeError("missing auth token; set K1_API_TOKEN or K1_DEV_TOKEN")
    return {"Authorization": f"Bearer {token}"}


def _load_payload(path: Path, target: str | None, program_key: str | None) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if target:
        assets = payload.get("in_scope_assets") or []
        if assets:
            assets[0]["target"] = target
        else:
            payload["in_scope_assets"] = [{"target": target, "target_type": "domain"}]
    if program_key:
        payload["program_key"] = program_key
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed deterministic MVP bug bounty demo data via canonical APIs.")
    parser.add_argument("--api-url", default=os.getenv("K1_API_URL", "http://localhost:8080"))
    parser.add_argument("--payload", default=str(DEFAULT_PAYLOAD_PATH))
    parser.add_argument("--target", default=None, help="Override first in-scope target in payload.")
    parser.add_argument("--program-key", default=None, help="Override program_key.")
    parser.add_argument("--template", default="workflow_recon_surface_map")
    parser.add_argument("--apply", action="store_true", help="Execute writes; default is dry planning output.")
    parser.add_argument("--trigger-run", action="store_true", help="Trigger schedule after seed (requires --apply).")
    parser.add_argument(
        "--create-case-from-first-alert",
        action="store_true",
        help="Create one case from first alert after sync if available.",
    )
    args = parser.parse_args()

    payload_path = Path(args.payload)
    if not payload_path.exists():
        print(f"payload file not found: {payload_path}", file=sys.stderr)
        return 2

    payload = _load_payload(payload_path, args.target, args.program_key)

    if not args.apply:
        print(
            json.dumps(
                {
                    "mode": "plan",
                    "api_url": args.api_url,
                    "workflow_template": args.template,
                    "program_payload": payload,
                    "notes": "Run with --apply to persist canonical records.",
                },
                indent=2,
            )
        )
        return 0

    headers = _auth_headers(args.api_url)
    with httpx.Client(base_url=args.api_url, headers=headers, timeout=60.0) as client:
        imported = client.post("/api/v1/bug-bounty/programs/import", json=payload)
        if imported.status_code >= 400:
            print(imported.text, file=sys.stderr)
            return 1
        program = imported.json()
        program_id = program["id"]

        targets_response = client.get(f"/api/v1/bug-bounty/programs/{program_id}/targets")
        if targets_response.status_code >= 400:
            print(targets_response.text, file=sys.stderr)
            return 1
        targets = targets_response.json()
        if not targets:
            print("no monitored targets returned after import", file=sys.stderr)
            return 1
        target = targets[0]

        schedules_response = client.get("/api/v1/bug-bounty/schedules", params={"program_id": program_id})
        if schedules_response.status_code >= 400:
            print(schedules_response.text, file=sys.stderr)
            return 1
        schedules = schedules_response.json()
        schedule = next(
            (
                item
                for item in schedules
                if item.get("scope_target_id") == target["id"] and item.get("workflow_template") == args.template
            ),
            None,
        )
        if schedule is None:
            create_schedule = client.post(
                "/api/v1/bug-bounty/schedules",
                json={
                    "program_id": program_id,
                    "scope_target_id": target["id"],
                    "workflow_template": args.template,
                    "schedule_type": "interval",
                    "interval_minutes": 60,
                    "safe_mode": True,
                    "dry_run": False,
                    "priority_tier": 2,
                    "created_by": "cli.mvp.seed",
                },
            )
            if create_schedule.status_code >= 400:
                print(create_schedule.text, file=sys.stderr)
                return 1
            schedule = create_schedule.json()

        trigger_result = None
        if args.trigger_run:
            trigger = client.post(
                f"/api/v1/bug-bounty/schedules/{schedule['id']}/trigger",
                json={"actor": "cli.mvp.seed", "force": False},
            )
            if trigger.status_code >= 400:
                print(trigger.text, file=sys.stderr)
                return 1
            trigger_result = trigger.json()

        alert_sync = client.post(
            "/api/v1/bug-bounty/alerts/sync",
            json={"actor": "cli.mvp.seed", "program_id": program_id, "cooldown_minutes": 30},
        )
        if alert_sync.status_code >= 400:
            print(alert_sync.text, file=sys.stderr)
            return 1
        alert_sync_payload = alert_sync.json()

        candidates = client.get("/api/v1/bug-bounty/candidates", params={"program_id": program_id, "limit": 50})
        alerts = client.get("/api/v1/bug-bounty/alerts", params={"program_id": program_id, "limit": 50})
        cases = client.get("/api/v1/bug-bounty/cases", params={"program_id": program_id, "limit": 50})
        if candidates.status_code >= 400 or alerts.status_code >= 400 or cases.status_code >= 400:
            print("failed reading seeded lists", file=sys.stderr)
            return 1

        alerts_payload = alerts.json()
        created_case = None
        if args.create_case_from_first_alert and alerts_payload:
            case_response = client.post(
                f"/api/v1/bug-bounty/alerts/{alerts_payload[0]['id']}/case",
                json={"actor": "cli.mvp.seed"},
            )
            if case_response.status_code < 400:
                created_case = case_response.json()

    print(
        json.dumps(
            {
                "mode": "applied",
                "program_id": program_id,
                "program_name": program.get("name"),
                "scope_target_id": target.get("id"),
                "scope_target": target.get("target"),
                "schedule_id": schedule.get("id"),
                "trigger_result": trigger_result,
                "alert_sync": alert_sync_payload,
                "candidate_count": len(candidates.json()),
                "alert_count": len(alerts_payload),
                "case_count": len(cases.json()),
                "created_case_id": created_case.get("id") if isinstance(created_case, dict) else None,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
