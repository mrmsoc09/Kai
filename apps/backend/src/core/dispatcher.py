from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import zipfile, time

ROOT = Path(__file__).resolve().parents[4]
OUTBOX = ROOT / 'artifacts' / 'submissions' / 'outbox'
OUTBOX.mkdir(parents=True, exist_ok=True)


def dispatch_from_package(zip_path: str) -> Dict[str, Any]:
    zp = Path(zip_path)
    if not zp.exists():
        return {'ok': False, 'error': 'package_missing'}
    # Extract email.eml into outbox with timestamped name
    with zipfile.ZipFile(zp, 'r') as z:
        names = z.namelist()
        if 'email.eml' not in names:
            return {'ok': False, 'error': 'email_missing_in_package'}
        data = z.read('email.eml')
    out = OUTBOX / f"{int(time.time()*1000)}_{zp.stem}.eml"
    out.write_bytes(data)
    return {'ok': True, 'outbox': str(out)}
