from __future__ import annotations

import os
from typing import Any


def _load_token() -> str:
    for key in ("K1_API_TOKEN", "K1_AUTH_TOKEN", "K1_DEV_TOKEN"):
        value = (os.getenv(key) or "").strip()
        if value:
            return value

    try:
        from ..core.secret_manager import get_secret_manager

        manager = get_secret_manager()
        for key in ("K1_API_TOKEN", "K1_AUTH_TOKEN", "K1_DEV_TOKEN"):
            value = (manager.get_optional(key) or "").strip()
            if value:
                return value
    except Exception:
        return ""

    return ""


def get_api_client(*, timeout: float = 60.0) -> Any | None:
    try:
        import httpx
    except Exception:
        return None

    base_url = os.getenv("K1_API_URL", "http://localhost:8080").strip().rstrip("/")
    headers: dict[str, str] = {}
    token = _load_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    return httpx.Client(
        base_url=base_url,
        timeout=timeout,
        headers=headers or None,
    )
