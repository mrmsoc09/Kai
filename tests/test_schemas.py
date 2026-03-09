import json
from pathlib import Path


def test_schemas_load():
    schema_dir = Path("ai-kernel/governance/schemas")
    for path in schema_dir.glob("*.json"):
        data = json.loads(path.read_text())
        assert "title" in data
