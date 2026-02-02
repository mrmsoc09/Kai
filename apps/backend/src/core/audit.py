from __future__ import annotations

import os, json, datetime
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

ROOT = Path(__file__).resolve().parents[4]
AUD_BASE = ROOT / 'artifacts' / 'logs' / 'http'

class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        AUD_BASE.mkdir(parents=True, exist_ok=True)

    async def dispatch(self, request: Request, call_next):
        now = datetime.datetime.now(datetime.timezone.utc)
        daydir = AUD_BASE / f"{now.year:04d}" / f"{now.month:02d}" / f"{now.day:02d}"
        daydir.mkdir(parents=True, exist_ok=True)
        path = daydir / 'audit.jsonl'
        rec = {
            'ts': now.isoformat(),
            'method': request.method,
            'path': request.url.path,
            'query': str(request.url.query),
            'client': request.client.host if request.client else None,
        }
        try:
            resp = await call_next(request)
            rec['status'] = resp.status_code
            return resp
        finally:
            try:
                with open(path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + '
')
            except Exception:
                pass
