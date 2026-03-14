from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _root() -> Path:
    env_root = os.getenv("K1_WORKFLOW_OUTPUT_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parents[4] / "output"


def _workflow_dir(workflow_key: str) -> Path:
    path = _root() / "raw" / "workflows" / workflow_key
    path.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically via a temp file in the same directory."""
    text = json.dumps(payload, indent=2)
    dir_ = path.parent
    dir_.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=dir_,
        prefix=".tmp_",
        suffix=".json",
        delete=False,
    ) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def write_workflow_plan(
    *,
    workflow_key: str,
    workflow_template: str,
    metadata: dict[str, Any],
    phase_plan: list[dict[str, Any]],
) -> str:
    payload = {
        "workflow_key": workflow_key,
        "workflow_template": workflow_template,
        "metadata": metadata,
        "phase_plan": phase_plan,
    }
    path = _workflow_dir(workflow_key) / "plan.json"
    _atomic_write(path, payload)
    return str(path)


def write_workflow_summary(
    *,
    workflow_key: str,
    summary: dict[str, Any],
) -> str:
    path = _workflow_dir(workflow_key) / "summary.json"
    _atomic_write(path, summary)
    return str(path)
