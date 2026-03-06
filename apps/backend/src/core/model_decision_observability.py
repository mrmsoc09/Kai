from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _telemetry_path() -> Path:
    path = Path(os.getenv("K1_MODEL_TELEMETRY_PATH", "artifacts/telemetry/model_decisions.jsonl")).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def emit_model_decision_event(event: Dict[str, Any]) -> None:
    row = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    with _telemetry_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
