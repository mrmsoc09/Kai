from __future__ import annotations
"""Generate draft Nuclei HTTP templates from CVE metadata (simplified)."""
import os, re, datetime as dt
from typing import Dict, Any, List
try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # fallback to manual formatting

OUT_DIR = "/a0/usr/projects/main-startup-build/k1/data/nuclei/custom"
os.makedirs(OUT_DIR, exist_ok=True)

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", s.lower())

def generate_http_template(cve_id: str, name: str, path: str, matchers: List[Dict[str, Any]] | None = None) -> str:
    tpl = {
        "id": f"{cve_id.lower()}-{_slug(name)}",
        "info": {
            "name": f"{cve_id} - {name}",
            "author": "k1-orchestration",
            "severity": "medium",
            "tags": ["cve", "autogen"],
            "description": f"Auto-generated probe for {cve_id}",
        },
        "http": [
            {
                "method": "GET",
                "path": ["{{BaseURL}}" + path],
                "matchers": matchers or [
                    {"type": "word", "words": [cve_id], "part": "body", "condition": "or"}
                ],
            }
        ],
    }
    out_path = os.path.join(OUT_DIR, f"{tpl['id']}.yaml")
    if yaml is not None:
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(tpl, f, sort_keys=False)
    else:
        # Minimal manual YAML writer
        lines = []
        lines.append(f"id: {tpl['id']}")
        lines.append("info:")
        lines.append(f"  name: \"{tpl['info']['name']}\"")
        lines.append(f"  author: {tpl['info']['author']}")
        lines.append(f"  severity: {tpl['info']['severity']}")
        lines.append(f"  tags: [{', '.join(tpl['info']['tags'])}]")
        lines.append(f"  description: \"{tpl['info']['description']}\"")
        lines.append("http:")
        lines.append("  - method: GET")
        lines.append("    path:")
        lines.append(f"      - '{{{{BaseURL}}}}{path}'")
        lines.append("    matchers:")
        lines.append("      - type: word")
        lines.append("        part: body")
        lines.append("        condition: or")
        lines.append(f"        words: [{cve_id}]")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return out_path
