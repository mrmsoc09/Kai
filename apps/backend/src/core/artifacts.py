"""Lightweight artifact writer for tool outputs.

Stores JSON payloads per task into ARTIFACTS_DIR (default /app/artifacts).
Returns relative path for later retrieval.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "/app/artifacts"))


def ensure_dir() -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACTS_DIR


def write_json(task_id: str, payload: Dict[str, Any]) -> str:
    base = ensure_dir()
    path = base / f"{task_id}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return str(path)

