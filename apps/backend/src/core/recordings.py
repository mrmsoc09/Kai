from __future__ import annotations

import tarfile
from pathlib import Path
from typing import Any

from .helpers import artifacts_root


_VIDEO_EXTS = frozenset({".mp4", ".webm", ".mkv"})


def _recordings_root() -> Path:
    return artifacts_root() / "recordings"


def _run_dir(run_id: str) -> Path:
    d = _recordings_root() / (run_id or "unknown")
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_recordings(run_id: str) -> list[str]:
    base = _run_dir(run_id)
    try:
        return [
            str(p)
            for p in base.glob("**/*")
            if p.is_file() and p.suffix.lower() in _VIDEO_EXTS
        ]
    except Exception:
        return []


def compress_run(run_id: str) -> str:
    base = _run_dir(run_id)
    arch = _recordings_root() / f"{run_id}.tar.gz"
    try:
        with tarfile.open(arch, "w:gz") as tf:
            for p in base.glob("**/*"):
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


def global_index() -> dict[str, Any]:
    idx: dict[str, Any] = {}
    recs = _recordings_root()
    try:
        for run_dir in recs.iterdir():
            if not run_dir.is_dir():
                continue
            rid = run_dir.name
            seg_files = [
                p
                for p in run_dir.glob("**/*")
                if p.is_file() and p.suffix.lower() in _VIDEO_EXTS
            ]
            total_bytes = sum(p.stat().st_size for p in seg_files)
            arch = recs / f"{rid}.tar.gz"
            idx[rid] = {
                "segments": len(seg_files),
                "bytes": total_bytes,
                "archive": str(arch) if arch.exists() else None,
            }
    except Exception:
        pass
    return idx


def has_recording(run_id: str) -> bool:
    try:
        base = _run_dir(run_id)
        for p in base.glob("**/*"):
            if p.is_file() and p.suffix.lower() in _VIDEO_EXTS:
                return True
        arch = _recordings_root() / f"{run_id}.tar.gz"
        if arch.exists() and arch.is_file() and arch.stat().st_size > 0:
            return True
    except Exception:
        pass
    return False
