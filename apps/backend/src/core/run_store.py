from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .metrics import aggregate_metrics, compute_run_metrics

ROOT = Path(__file__).resolve().parents[4]


def _artifacts_root() -> Path:
    env_value = os.getenv("K1_ARTIFACTS_ROOT", "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve()
    return ROOT / "artifacts"


def _dork_root() -> Path:
    root = _artifacts_root() / "dork_runs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def run_dir(run_id: str) -> Path:
    d = _dork_root() / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_run_record(run_id: str, run: dict[str, Any]) -> str:
    d = run_dir(run_id)
    p = d / "run.json"
    run.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    run.setdefault("run_id", run_id)
    run.setdefault("id", run_id)
    run["metrics"] = compute_run_metrics(run)
    p.write_text(json.dumps(run, ensure_ascii=False, indent=2))
    return str(p)


# Explicit alias — prefer write_run_record for new code
save_run_record = write_run_record


def load_run(run_id: str) -> dict[str, Any] | None:
    p = _dork_root() / run_id / "run.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_all_runs() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sub in sorted(_dork_root().glob("*/run.json")):
        try:
            out.append(json.loads(sub.read_text(encoding="utf-8")))
        except Exception:
            pass
    return out


def aggregate_all() -> dict[str, Any]:
    return aggregate_metrics(load_all_runs())


def append_finding(run_id: str, finding: dict[str, Any]) -> dict[str, Any]:
    """Append a finding to a run record (creates run if missing)."""
    run = load_run(run_id) or {"run_id": run_id, "findings": []}
    run.setdefault("run_id", run_id)
    run.setdefault("findings", []).append(finding)
    write_run_record(run_id, run)
    return run
