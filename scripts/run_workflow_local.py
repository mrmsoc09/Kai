#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.backend.src.core.hil_db import get_async_session_maker
from apps.backend.src.core.workflow_executor import WorkflowExecutor


async def _run(args) -> int:
    session_maker = get_async_session_maker()
    async with session_maker() as db:
        executor = WorkflowExecutor(db=db, trigger_source="CLI")
        try:
            result = await executor.execute_template(
                workflow_template=args.template,
                target=args.target,
                run_id=args.run_id,
                safe_mode=args.safe_mode,
                dry_run=args.dry_run,
                concurrency_limit=args.concurrency,
                enable_steps=args.enable_steps,
                disable_steps=args.disable_steps,
                scope_policy_path=args.scope_policy_path,
                resume=args.resume,
            )
            await db.commit()
        except ValueError as exc:
            await db.rollback()
            print(str(exc), file=sys.stderr)
            return 2
        except Exception:
            await db.rollback()
            raise
    print(json.dumps(result.as_dict(), indent=2, default=str))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Kai workflow locally without API server.")
    parser.add_argument("--template", required=True, help="workflow template name")
    parser.add_argument("--target", required=True, help="target domain/host/url")
    parser.add_argument("--run-id", default=None, help="optional run identifier")
    parser.add_argument("--safe-mode", action="store_true", dest="safe_mode")
    parser.add_argument("--unsafe-mode", action="store_false", dest="safe_mode")
    parser.set_defaults(safe_mode=True)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--enable-step", dest="enable_steps", action="append", default=[])
    parser.add_argument("--disable-step", dest="disable_steps", action="append", default=[])
    parser.add_argument("--scope-policy-path", default=None)
    parser.add_argument("--resume", action="store_true", default=False)
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
