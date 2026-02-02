from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import hashlib, json
from datetime import datetime, timezone


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def compute_merkle_tree(dir_path: str | Path, include_patterns: List[str] | None = None) -> Dict[str, Any]:
    d = Path(dir_path)
    if not d.exists():
        raise FileNotFoundError(str(d))
    # Collect leaves: only regular files in directory (non-recursive) matching patterns if provided
    files = [p for p in sorted(d.iterdir()) if p.is_file()]
    if include_patterns:
        import fnmatch
        files = [p for p in files if any(fnmatch.fnmatch(p.name, pat) for pat in include_patterns)]
    leaves = [{'name': p.name, 'sha256': _sha256_file(p)} for p in files]
    # Build tree layers
    layer = [bytes.fromhex(l['sha256']) for l in leaves]
    if not layer:
        root = _sha256_bytes(b'')
    else:
        while len(layer) > 1:
            nxt: List[bytes] = []
            for i in range(0, len(layer), 2):
                a = layer[i]
                b = layer[i+1] if i+1 < len(layer) else layer[i]
                nxt.append(hashlib.sha256(a + b).digest())
            layer = nxt
        root = layer[0].hex()
    out = {
        'algorithm': 'sha256',
        'root': root,
        'leaves': leaves,
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    }
    mpath = d / 'merkle.json'
    mpath.write_text(json.dumps(out, indent=2))
    return {'path': str(mpath), 'root': root, 'count': len(leaves)}
