"""Normalize tool results into Evidence Object contract."""

from pathlib import Path
from typing import Dict, Any
from .lib.io_contracts import HookResult
from .lib.schema_utils import validate_json
from .lib.common import logger

SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schemas"


def run(result: Dict[str, Any]) -> HookResult:
    """Ensure result matches tool_result schema if available."""
    schema_path = SCHEMA_ROOT / "tool_result.schema.json"
    try:
        validate_json(result, schema_path)
    except Exception as exc:
        return HookResult(ok=False, reason=f"result schema invalid: {exc}")
    logger.debug("result_normalizer pass id=%s", result.get("id"))
    return HookResult(ok=True, data={"result": result})
