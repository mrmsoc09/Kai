#!/usr/bin/env python3
"""Run a full Kai headless opportunity cycle through Kai's API only.

This script orchestrates (auth -> queue settings -> approve/execute -> poll ->
telemetry summary) for the configured HackerOne opportunity IDs.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env_map(env_path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not env_path.exists():
        return data
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _json_or_text(response: requests.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text[:1200]


@dataclass
class Config:
    repo_root: Path
    env_path: Path
    base_url: str
    username: str
    password: str
    program_ids: list[str]
    poll_timeout_seconds: int
    poll_interval_seconds: int
    min_concurrent: int
    max_concurrent: int
    force_rerun: bool


def _build_config(args: argparse.Namespace) -> Config:
    repo_root = Path(args.repo_root).resolve()
    env_path = repo_root / ".env"
    env_map = _load_env_map(env_path)

    base_url = args.base_url or env_map.get("KAI_BACKEND_URL") or env_map.get("BACKEND_URL") or "http://127.0.0.1:8080"
    username = args.username or env_map.get("K1_BOOTSTRAP_ADMIN_USERNAME") or env_map.get("KAI_ADMIN_USERNAME") or "k1-admin"
    password = args.password or env_map.get("K1_BOOTSTRAP_ADMIN_PASSWORD") or env_map.get("KAI_ADMIN_PASSWORD") or ""
    if not password:
        raise SystemExit("Missing admin password in args or .env (K1_BOOTSTRAP_ADMIN_PASSWORD).")

    raw_programs = (
        args.program_ids
        or env_map.get("K1_HEADLESS_PROGRAM_IDS")
        or "hackerone:twitter,hackerone:snapchat,hackerone:coinbase"
    )
    program_ids = [row.strip() for row in raw_programs.split(",") if row.strip()]
    if not program_ids:
        raise SystemExit("No program IDs configured.")

    return Config(
        repo_root=repo_root,
        env_path=env_path,
        base_url=base_url.rstrip("/"),
        username=username,
        password=password,
        program_ids=program_ids,
        poll_timeout_seconds=max(30, int(args.poll_timeout_seconds)),
        poll_interval_seconds=max(3, int(args.poll_interval_seconds)),
        min_concurrent=max(1, int(args.min_concurrent)),
        max_concurrent=max(1, int(args.max_concurrent)),
        force_rerun=bool(args.force_rerun),
    )


def _telemetry_summary(repo_root: Path, mission_ids: list[str]) -> dict[str, Any]:
    if not mission_ids:
        return {}
    path = repo_root / "artifacts" / "telemetry" / "mission_events.jsonl"
    if not path.exists():
        return {}
    mission_filter = set(mission_ids)
    summary: dict[str, dict[str, Any]] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        mission_id = str(event.get("mission_id", "")).strip()
        if mission_filter and mission_id not in mission_filter:
            continue
        rec = summary.setdefault(mission_id, {"event_counts": {}, "tools": set(), "last_ts": None})
        event_type = str(event.get("event_type", "")).strip()
        if event_type:
            rec["event_counts"][event_type] = rec["event_counts"].get(event_type, 0) + 1
        detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
        tool_id = detail.get("tool_id")
        if tool_id:
            rec["tools"].add(str(tool_id))
        ts = event.get("timestamp")
        if ts:
            rec["last_ts"] = ts

    return {
        mission_id: {
            "event_counts": rec["event_counts"],
            "tools": sorted(rec["tools"]),
            "last_ts": rec["last_ts"],
        }
        for mission_id, rec in summary.items()
    }


def _extract_mission_ids(states: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for value in states.values():
        mids = value.get("mission_ids", []) if isinstance(value, dict) else []
        if not isinstance(mids, list):
            continue
        for mission_id in mids:
            text = str(mission_id).strip()
            if text and text not in out:
                out.append(text)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full Kai headless opportunity cycle.")
    parser.add_argument("--repo-root", default="/home/k1-admin/Kai")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--program-ids", default="")
    parser.add_argument("--poll-timeout-seconds", type=int, default=300)
    parser.add_argument("--poll-interval-seconds", type=int, default=10)
    parser.add_argument("--min-concurrent", type=int, default=1)
    parser.add_argument("--max-concurrent", type=int, default=3)
    parser.add_argument("--force-rerun", action="store_true", help="Reject completed opportunities before re-approving/executing.")
    args = parser.parse_args()

    cfg = _build_config(args)
    out_dir = cfg.repo_root / "runtime" / "headless"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"headless_full_run_{int(time.time())}.json"

    result: dict[str, Any] = {
        "started_at": _now_iso(),
        "base_url": cfg.base_url,
        "programs": cfg.program_ids,
        "auth": {},
        "capabilities": {},
        "queue_settings": {},
        "queue_settings_update": {},
        "actions": [],
        "poll": [],
        "telemetry": {},
        "status": "partial",
        "errors": [],
    }

    session = requests.Session()
    auth = session.post(
        f"{cfg.base_url}/auth/token",
        data={"username": cfg.username, "password": cfg.password},
        timeout=30,
    )
    result["auth"] = {"status": auth.status_code}
    if auth.status_code >= 400:
        result["errors"].append({"step": "auth", "status": auth.status_code, "detail": auth.text[:500]})
        out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(out_file)
        return 1

    access_token = _json_or_text(auth).get("access_token")
    session.headers.update({"Authorization": f"Bearer {access_token}"})

    for path, key in (
        ("/opportunities/actions/capabilities", "capabilities"),
        ("/opportunities/scan-queue/settings", "queue_settings"),
    ):
        rr = session.get(f"{cfg.base_url}{path}", timeout=30)
        result[key] = {"status": rr.status_code, "payload": _json_or_text(rr)}

    update = session.put(
        f"{cfg.base_url}/opportunities/scan-queue/settings",
        json={"min_concurrent": cfg.min_concurrent, "max_concurrent": cfg.max_concurrent},
        timeout=30,
    )
    result["queue_settings_update"] = {"status": update.status_code, "payload": _json_or_text(update)}

    listed = session.get(
        f"{cfg.base_url}/opportunities",
        params={"limit": 400, "sort_by": "score"},
        timeout=60,
    )
    if listed.status_code >= 400:
        result["errors"].append({"step": "list_opportunities", "status": listed.status_code, "detail": listed.text[:500]})
        out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(out_file)
        return 1

    opportunities_payload = _json_or_text(listed)
    if isinstance(opportunities_payload, dict):
        opportunities = opportunities_payload.get("opportunities", [])
    else:
        opportunities = opportunities_payload
    opp_map = {row.get("id"): row for row in opportunities if isinstance(row, dict)}

    for program_id in cfg.program_ids:
        action: dict[str, Any] = {"program_id": program_id}
        opp = opp_map.get(program_id)
        if not opp:
            action["error"] = "missing_opportunity"
            result["actions"].append(action)
            result["errors"].append({"step": "resolve_program", "program_id": program_id, "detail": "missing_opportunity"})
            continue

        status = str(opp.get("status", "")).strip()
        approval_state = str(opp.get("approval_state", "")).strip()

        if cfg.force_rerun and status in {"completed", "rejected", "failed"}:
            reset = session.post(
                f"{cfg.base_url}/opportunities/{program_id}/reset",
                json={"reason": "Reset for fresh headless rerun."},
                timeout=60,
            )
            action["reset"] = {"status": reset.status_code, "payload": _json_or_text(reset)}
            if reset.status_code >= 400:
                result["errors"].append(
                    {
                        "step": "reset",
                        "program_id": program_id,
                        "status": reset.status_code,
                        "detail": _json_or_text(reset),
                    }
                )
            refreshed = session.get(f"{cfg.base_url}/opportunities/{program_id}", timeout=60)
            refreshed_payload = _json_or_text(refreshed)
            if isinstance(refreshed_payload, dict):
                status = str(refreshed_payload.get("status", "")).strip()
                approval_state = str(refreshed_payload.get("approval_state", "")).strip()

        if approval_state != "approved" and status not in {"executing", "completed"}:
            approve = session.post(
                f"{cfg.base_url}/opportunities/{program_id}/approve",
                json={"reason": "headless full-run dispatch"},
                timeout=60,
            )
            action["approve"] = {"status": approve.status_code, "payload": _json_or_text(approve)}
        else:
            action["approve"] = {"status": "skipped", "reason": f"already_{approval_state or status}"}

        execute = session.post(
            f"{cfg.base_url}/opportunities/{program_id}/execute",
            json={"reason": "headless full-run dispatch", "execution_mode": "live", "max_targets": 3},
            timeout=60,
        )
        action["execute"] = {"status": execute.status_code, "payload": _json_or_text(execute)}
        if execute.status_code >= 400 and execute.status_code != 409:
            result["errors"].append(
                {
                    "step": "execute",
                    "program_id": program_id,
                    "status": execute.status_code,
                    "detail": _json_or_text(execute),
                }
            )
        result["actions"].append(action)

    terminal_states = {"completed", "failed", "rejected"}
    deadline = time.time() + cfg.poll_timeout_seconds
    last_states: dict[str, Any] = {}
    while time.time() < deadline:
        poll = session.get(
            f"{cfg.base_url}/opportunities",
            params={"limit": 400, "sort_by": "score"},
            timeout=60,
        )
        if poll.status_code >= 400:
            result["errors"].append({"step": "poll", "status": poll.status_code, "detail": poll.text[:500]})
            break

        poll_payload = _json_or_text(poll)
        if isinstance(poll_payload, dict):
            opp_rows = poll_payload.get("opportunities", [])
        else:
            opp_rows = poll_payload
        cur_map = {row.get("id"): row for row in opp_rows if isinstance(row, dict)}
        state_snapshot: dict[str, Any] = {}
        all_terminal = True
        for program_id in cfg.program_ids:
            row = cur_map.get(program_id, {})
            status = str(row.get("status", "missing"))
            approval_state = str(row.get("approval_state", ""))
            em = row.get("execution_metadata", {}) if isinstance(row.get("execution_metadata"), dict) else {}
            state_snapshot[program_id] = {
                "status": status,
                "approval_state": approval_state,
                "missions_launched": em.get("missions_launched"),
                "missions_completed": em.get("missions_completed"),
                "missions_failed": em.get("missions_failed"),
                "mission_ids": em.get("mission_ids", []),
                "report_ids": em.get("report_ids", []),
                "actual_yield_proxy": em.get("actual_yield_proxy"),
                "last_error": em.get("last_error"),
            }
            if status not in terminal_states:
                all_terminal = False

        if not last_states or any(last_states.get(k) != v for k, v in state_snapshot.items()):
            result["poll"].append({"ts": _now_iso(), "states": state_snapshot})
            last_states = state_snapshot

        if all_terminal:
            break
        time.sleep(cfg.poll_interval_seconds)

    final_states = result["poll"][-1]["states"] if result["poll"] else {}
    mission_ids = _extract_mission_ids(final_states)
    result["telemetry"] = _telemetry_summary(cfg.repo_root, mission_ids)

    if final_states and all(row.get("status") in terminal_states for row in final_states.values()):
        result["status"] = "success"
    elif any(row.get("status") == "executing" for row in final_states.values()):
        result["status"] = "partial"
    else:
        result["status"] = "failed" if result["errors"] else "partial"

    result["finished_at"] = _now_iso()
    out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(out_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
