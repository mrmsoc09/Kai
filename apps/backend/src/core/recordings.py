from __future__ import annotations
import os, tarfile
from pathlib import Path
from typing import List, Dict, Any

ROOT = Path(__file__).resolve().parents[4]
ART = ROOT / 'artifacts'
RECS = ART / 'recordings'
RECS.mkdir(parents=True, exist_ok=True)

def _run_dir(run_id: str) -> Path:
    d = RECS / (run_id or 'unknown')
    d.mkdir(parents=True, exist_ok=True)
    return d

def list_recordings(run_id: str) -> List[str]:
    base = _run_dir(run_id)
    out: List[str] = []
    try:
        for p in base.glob('**/*'):
            if p.is_file() and p.suffix.lower() in ('.mp4', '.webm', '.mkv'):
                out.append(str(p))
    except Exception:
        return []
    return out

def compress_run(run_id: str) -> str:
    base = _run_dir(run_id)
    arch = RECS / f"{run_id}.tar.gz"
    try:
        with tarfile.open(arch, 'w:gz') as tf:
            for p in base.glob('**/*'):
                if p.is_file():
                    tf.add(p, arcname=p.relative_to(base))
    except Exception:
        try:
            if arch.exists():
                arch.unlink()
        except Exception:
            pass
        raise
    return str(arch)

def global_index() -> Dict[str, Any]:
    idx: Dict[str, Any] = {}
    try:
        for run_dir in RECS.iterdir():
            if run_dir.is_dir():
                rid = run_dir.name
                seg_files = [p for p in run_dir.glob('**/*') if p.is_file() and p.suffix.lower() in ('.mp4','.webm','.mkv')]
                total = sum(p.stat().st_size for p in seg_files)
                arch = RECS / f"{rid}.tar.gz"
                idx[rid] = {
                    'segments': len(seg_files),
                    'bytes': total,
                    'archive': str(arch) if arch.exists() else None,
                }
    except Exception:
        pass
    return idx

def has_recording(run_id: str) -> bool:
    try:
        base = _run_dir(run_id)
        for q in base.glob('**/*'):
            if q.is_file() and q.suffix.lower() in {'.mp4','.webm','.mkv'}:
                return True
        arch = (ART / 'recordings') / f"{run_id}.tar.gz"
        if arch.exists() and arch.is_file() and arch.stat().st_size > 0:
            return True
    except Exception:
        pass
    return False
