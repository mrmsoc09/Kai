"""
Response middleware that enforces secure attributes on auth/session cookies.
"""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class CookieSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        raw_names = os.getenv("CSRF_PROTECTED_COOKIE_NAMES", "session_id,k1_token")
        self._cookie_names = {
            name.strip()
            for name in raw_names.split(",")
            if name.strip()
        }
        self._force_secure = os.getenv("COOKIE_FORCE_SECURE", "false").strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _upsert_attr(segments: list[str], key: str, value: str | None = None) -> None:
        lookup = key.lower()
        replacement = key if value is None else f"{key}={value}"
        for index in range(1, len(segments)):
            segment = segments[index].strip()
            if not segment:
                continue
            name = segment.split("=", 1)[0].strip().lower()
            if name == lookup:
                segments[index] = replacement
                return
        segments.append(replacement)

    def _harden_set_cookie(self, header_value: str) -> str:
        parts = [segment.strip() for segment in header_value.split(";")]
        if not parts or "=" not in parts[0]:
            return header_value

        cookie_name = parts[0].split("=", 1)[0].strip()
        if cookie_name not in self._cookie_names:
            return header_value

        self._upsert_attr(parts, "HttpOnly")
        self._upsert_attr(parts, "SameSite", "Strict")
        self._upsert_attr(parts, "Path", "/")
        if self._force_secure:
            self._upsert_attr(parts, "Secure")
        return "; ".join(parts)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        hardened: list[tuple[bytes, bytes]] = []
        for header_key, header_value in response.raw_headers:
            if header_key.lower() != b"set-cookie":
                hardened.append((header_key, header_value))
                continue
            rewritten = self._harden_set_cookie(header_value.decode("latin-1"))
            hardened.append((header_key, rewritten.encode("latin-1")))
        response.raw_headers = hardened
        return response

