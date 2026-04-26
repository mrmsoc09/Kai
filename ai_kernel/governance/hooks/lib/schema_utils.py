"""Minimal JSON schema validation helper."""

import json
from pathlib import Path
from typing import Any, Dict

try:
    import jsonschema
except ImportError:  # pragma: no cover - guard for environments without dependency
    jsonschema = None


def validate_json(data: Any, schema_path: Path) -> None:
    if jsonschema is None:
        return  # fallback: skip validation if library unavailable
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(data, schema)
