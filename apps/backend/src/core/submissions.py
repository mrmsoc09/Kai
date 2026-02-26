from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
from hashlib import sha256
import json

ROOT = Path(__file__).resolve().parents[4]
ART = ROOT / 'artifacts' / 'reports'
ART.mkdir(parents=True, exist_ok=True)


def _hash_file(p: Path) -> str:
    h = sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def _merkle(paths: List[Path]) -> Dict[str, Any]:
    leaves = [(_hash_file(p), str(p.name)) for p in paths]
    # Simple pairwise merkle for audit; no tree storage beyond root + leaves
    layer = [h for h, _ in leaves]
    if not layer:
        root = sha256(b'').hexdigest()
    else:
        cur = layer
        while len(cur) > 1:
            nxt = []
            for i in range(0, len(cur), 2):
                a = cur[i].encode(); b = cur[i+1].encode() if i+1 < len(cur) else cur[i].encode()
                nxt.append(sha256(a + b).hexdigest())
            cur = nxt
        root = cur[0]
    return { 'root': root, 'leaves': [{'file': name, 'hash': h} for h, name in leaves] }


def persist_submission(run_id: str, content_md: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    out_dir = ART / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    report_md = out_dir / 'report.md'
    meta_json = out_dir / 'meta.json'
    report_md.write_text(content_md)
    meta_json.write_text(json.dumps(meta, indent=2))
    merkle = _merkle([report_md, meta_json])
    (out_dir / 'merkle.json').write_text(json.dumps(merkle, indent=2))
    return { 'dir': str(out_dir), 'files': ['report.md','meta.json','merkle.json'], 'merkle_root': merkle['root'] }
