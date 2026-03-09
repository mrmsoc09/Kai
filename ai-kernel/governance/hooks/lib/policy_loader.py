"""Load governance policies with basic schema checks."""

from pathlib import Path
from typing import Dict, Any

from .common import load_yaml


def load_policy(name: str, root: Path) -> Dict[str, Any]:
    path = root / f"{name}.yaml"
    policy = load_yaml(path)
    if policy.get("schema") != 1:
        raise ValueError(f"policy {name} invalid schema version")
    return policy
