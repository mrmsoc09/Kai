"""Common helpers for governance hooks."""

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("ai_kernel.governance")
logger.setLevel(logging.INFO)


def load_yaml(path: Path) -> Dict[str, Any]:
    import yaml  # local import to avoid hard dependency at module load

    if not path.exists():
        raise FileNotFoundError(f"policy file missing: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def json_safe(data: Any) -> str:
    return json.dumps(data, default=str, separators=(",", ":"), ensure_ascii=False)
