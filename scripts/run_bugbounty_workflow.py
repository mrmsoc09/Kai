#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Start a template-based K1 bug bounty workflow.")
    parser.add_argument("--backend", default=os.getenv("BACKEND_URL", "http://localhost:8080"))
    parser.add_argument("--template", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--initiated-by", default="cli.operator")
    parser.add_argument("--program-name", default="CLI Program")
    parser.add_argument("--safe-mode", action="store_true", dest="safe_mode")
    parser.add_argument("--unsafe-mode", action="store_false", dest="safe_mode")
    parser.set_defaults(safe_mode=True)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--declared-goal", default=None)
    args = parser.parse_args()

    payload = {
        "workflow_template": args.template,
        "target": args.target,
        "target_type": "domain",
        "initiated_by": args.initiated_by,
        "program_name": args.program_name,
        "safe_mode": args.safe_mode,
        "dry_run": args.dry_run,
        "declared_goal": args.declared_goal
        or f"Run {args.template} against {args.target}",
    }
    endpoint = f"{args.backend.rstrip('/')}/api/v1/campaigns/start-workflow"
    try:
        response = httpx.post(endpoint, json=payload, timeout=30)
    except Exception as exc:
        print(f"request_failed: {exc}", file=sys.stderr)
        return 2

    if response.status_code >= 400:
        print(response.text, file=sys.stderr)
        return 1
    print(json.dumps(response.json(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
