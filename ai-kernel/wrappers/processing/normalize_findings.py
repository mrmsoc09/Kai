"""Normalize findings into schema-aligned payloads."""

import json
import sys
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[2] / "governance" / "schemas" / "finding.schema.json"


def main():
    data = json.load(sys.stdin)
    # lightweight normalization: ensure required keys exist
    for key in ("id", "title", "severity", "evidence_ids"):
        if key not in data:
            raise SystemExit(json.dumps({"status": "error", "reason": f"missing {key}"}))
    print(json.dumps({"status": "ok", "finding": data}))


if __name__ == "__main__":
    main()
