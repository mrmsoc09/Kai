from __future__ import annotations

import os, json
from pathlib import Path
from typing import Dict, Any, List, Tuple
import yaml

ROOT = Path(__file__).resolve().parents[4]
CONF = ROOT / 'configs' / 'knowledge.yaml'
ART = ROOT / 'artifacts' / 'knowledge'
ART.mkdir(parents=True, exist_ok=True)

REQ_FIELDS = ["id","type","classification","scope_ref","status","evidence_refs","created_at"]

class ObsidianConnector:
    def __init__(self):
        self.conf = self._load_conf()

    def _load_conf(self) -> Dict[str, Any]:
        try:
            return yaml.safe_load(CONF.read_text()) or {}
        except Exception:
            return {"enabled": False}

    def status(self) -> Dict[str, Any]:
        return {"enabled": bool(self.conf.get('enabled')), "vault_path": self.conf.get('vault_path')}

    def _parse_frontmatter(self, text: str):
        # Expect YAML frontmatter delimited by lines containing only '---'
        lines = text.splitlines()
        if len(lines) < 3 or lines[0].strip() != '---':
            return {}, text
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                end_idx = i
                break
        if end_idx is None:
            return {}, text
        fm_text = '\n'.join(lines[1:end_idx])
        body = '\n'.join(lines[end_idx+1:])
        try:
            data = yaml.safe_load(fm_text) or {}
        except Exception:
            data = {}
        return data, body

    def _redact(self, body: str) -> str:
        pats = (self.conf.get('governance') or {}).get('redact_patterns') or []
        red = body
        for p in pats:
            red = red.replace(p, '[REDACTED]')
        return red

    def refresh(self) -> Dict[str, Any]:
        if not bool(self.conf.get('enabled')):
            return {"status": "disabled"}
        vault = self.conf.get('vault_path')
        if not vault or not os.path.isdir(vault):
            return {"status": "error", "reason": "vault_path_missing"}
        notes: List[Dict[str, Any]] = []
        for path in Path(vault).rglob('*.md'):
            try:
                raw = path.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            fm, body = self._parse_frontmatter(raw)
            required = self.conf.get('frontmatter_required') or REQ_FIELDS
            if not fm:
                continue
            if not all(k in fm for k in required):
                continue
            if fm.get('classification') == 'Regulated' and not ((self.conf.get('governance') or {}).get('regulated_allowed')):
                continue
            note = {k: fm.get(k) for k in REQ_FIELDS}
            note['title'] = fm.get('title')
            note['path'] = str(path)
            note['body_preview'] = self._redact(body)[:400]
            notes.append(note)
        idx_path = ART / 'index.json'
        idx_path.write_text(json.dumps({"count": len(notes), "notes": notes}, ensure_ascii=False, indent=2))
        return {"status": "ok", "count": len(notes), "index": str(idx_path)}

    def list_notes(self) -> Dict[str, Any]:
        p = ART / 'index.json'
        if not p.exists():
            return {"status": "empty"}
        try:
            return json.loads(p.read_text())
        except Exception:
            return {"status": "error"}
