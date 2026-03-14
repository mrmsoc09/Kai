"""Capability registry loader."""

from pathlib import Path
from typing import Any, Dict

import yaml


REGISTRY_PATH = Path("config/registry/model_capabilities.yaml")


def load_capabilities(path: Path = REGISTRY_PATH) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def find_models(task: str, min_privacy: int = 1) -> list[dict]:
    data = load_capabilities()
    matches: list[dict] = []
    for entry in data.get("models", []):
        caps = entry.get("capabilities", {})
        if caps.get("privacy_tier", 0) < min_privacy:
            continue
        if task in caps.get("preferred_workloads", []):
            matches.append(entry)
    return matches
