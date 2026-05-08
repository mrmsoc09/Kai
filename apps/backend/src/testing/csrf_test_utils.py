"""Utilities for CSRF integration tests."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def issue_csrf_token(client: TestClient) -> str:
    response = client.get("/auth/csrf-token")
    response.raise_for_status()
    return response.json()["csrf_token"]


def issue_csrf_challenge(client: TestClient, path: str, method: str = "POST") -> str:
    response = client.get(
        "/auth/csrf-challenge",
        params={"path": path, "method": method},
    )
    response.raise_for_status()
    return response.json()["csrf_challenge"]


def issue_csrf_nonce(client: TestClient, path: str, method: str = "POST") -> str:
    response = client.get(
        "/auth/csrf-nonce",
        params={"path": path, "method": method},
    )
    response.raise_for_status()
    return response.json()["csrf_nonce"]


def build_csrf_headers(
    csrf_token: str,
    origin: str,
    *,
    challenge: str | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {
        "Origin": origin,
        "X-CSRF-Token": csrf_token,
    }
    if challenge:
        headers["X-CSRF-Challenge"] = challenge
    if nonce:
        headers["X-CSRF-Nonce"] = nonce
    return headers


def error_code(response: Any) -> str | None:
    try:
        return response.json().get("code")
    except Exception:
        return None

