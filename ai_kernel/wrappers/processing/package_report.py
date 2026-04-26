"""Package report objects for submission."""

import json
import sys
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[2] / "governance" / "schemas" / "report.schema.json"


def main():
    report = json.load(sys.stdin)
    if "findings" not in report:
        raise SystemExit(json.dumps({"status": "error", "reason": "findings required"}))
    out_dir = Path("runtime/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report.get('id','report')}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "path": str(path)}))


if __name__ == "__main__":
    main()
