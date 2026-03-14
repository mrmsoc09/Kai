from __future__ import annotations

import asyncio
from typing import Any

import httpx


class ASGITestClient:
    """Threadless sync test client backed by httpx.ASGITransport."""

    def __init__(self, app: Any, *, base_url: str = "http://testserver") -> None:
        self.app = app
        self.base_url = base_url
        self.headers: dict[str, str] = {}

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        request_headers = kwargs.pop("headers", None)

        async def _runner() -> httpx.Response:
            transport = httpx.ASGITransport(app=self.app)
            merged_headers = dict(self.headers)
            if request_headers:
                merged_headers.update(request_headers)

            async with httpx.AsyncClient(
                transport=transport,
                base_url=self.base_url,
                headers=merged_headers or None,
            ) as client:
                return await client.request(method, url, **kwargs)

        return asyncio.run(_runner())

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def close(self) -> None:
        return None
