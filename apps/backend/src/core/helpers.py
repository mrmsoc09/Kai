"""
Shared micro-utilities used across core modules.

Keep this file small — only house primitives that are genuinely duplicated in
three or more places.  Domain logic does not belong here.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------


def utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable.

    Truthy values: ``"1"``, ``"true"``, ``"yes"`` (case-insensitive).
    Everything else (including absent) resolves to *default*.
    """
    raw = os.getenv(name, "").strip().lower()
    if raw in ("1", "true", "yes"):
        return True
    if raw in ("0", "false", "no"):
        return False
    return default


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def repo_root() -> Path:
    """Return the repository root (five levels above this file)."""
    return Path(__file__).resolve().parents[4]


def artifacts_root() -> Path:
    """Return the artifacts root directory, respecting ``K1_ARTIFACTS_ROOT``."""
    env_value = os.getenv("K1_ARTIFACTS_ROOT", "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve()
    return repo_root() / "artifacts"


def workflow_output_root() -> Path:
    """Return the workflow output root, respecting ``K1_WORKFLOW_OUTPUT_ROOT``."""
    env_value = os.getenv("K1_WORKFLOW_OUTPUT_ROOT", "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve()
    return repo_root() / "output"


# ---------------------------------------------------------------------------
# Data coercion
# ---------------------------------------------------------------------------


def as_list_of_str(value: Any) -> list[str]:
    """Coerce *value* to a list of non-empty stripped strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    stripped = str(value).strip()
    return [stripped] if stripped else []
