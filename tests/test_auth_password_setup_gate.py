from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from apps.backend.src.auth.dependencies import CurrentUser, _enforce_password_setup_gate


def _request(path: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8080),
        "scheme": "http",
    }
    return Request(scope)


def _user(*, must_change_password: bool) -> CurrentUser:
    return CurrentUser(
        id=uuid4(),
        tenant_id=uuid4(),
        username="k1-admin",
        email=None,
        full_name="Kai Admin",
        is_active=True,
        is_superuser=True,
        must_change_password=must_change_password,
        role="admin",
    )


def test_password_setup_gate_allows_password_setup_route() -> None:
    user = _user(must_change_password=True)
    _enforce_password_setup_gate(user, _request("/auth/users/set-initial-password"))


def test_password_setup_gate_blocks_non_auth_routes_until_password_set() -> None:
    user = _user(must_change_password=True)
    with pytest.raises(HTTPException) as exc_info:
        _enforce_password_setup_gate(user, _request("/missions/"))
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "password_setup_required"
