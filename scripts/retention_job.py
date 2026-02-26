from __future__ import annotations
from pathlib import Path
import os, time, json

ROOT = Path(__file__).resolve().parents[2]
REC = ROOT / 'artifacts' / 'recordings'
MAX_AGE_DAYS = int(os.getenv('REC_MAX_AGE_DAYS', '14'))
MAX_TOTAL_GB = float(os.getenv('REC_MAX_TOTAL_GB', '50'))

now = time.time()
cutoff = now - MAX_AGE_DAYS * 86400

# Delete per-run directories older than cutoff
deleted = []
for p in sorted(REC.glob('*')):
    try:
        if p.is_dir():
            if p.stat().st_mtime < cutoff:
                for f in p.glob('*'):
                    try: f.unlink()
                    except Exception: pass
                p.rmdir()
                deleted.append({'path': str(p), 'reason': 'age'})
    except Exception:
        pass

# Enforce total size limit by deleting oldest archives
def total_size_bytes():
    s = 0
    for f in REC.glob('**/*'):
        try:
            if f.is_file(): s += f.stat().st_size
        except Exception:
            pass
    return s

limit = MAX_TOTAL_GB * (1024**3)
if total_size_bytes() > limit:
    archives = sorted([f for f in REC.glob('*.tar.gz') if f.is_file()], key=lambda x: x.stat().st_mtime)
    for f in archives:
        if total_size_bytes() <= limit:
            break
        try:
            f.unlink()
            deleted.append({'path': str(f), 'reason': 'quota'})
        except Exception:
            pass

print(json.dumps({'deleted': deleted}))
