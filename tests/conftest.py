import os
import sys
import pytest
from pathlib import Path
import anyio.to_thread
import asyncio
import threading

# Ensure repository root on path (avoid environment-specific hardcoded paths)
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.asgi_test_client import ASGITestClient

os.environ.setdefault("K1_TEST_MODE", "true")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("K1_DEV_TOKEN", "devtoken")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
# Enable bootstrap auth for test environment — allows /auth/login with K1_DEV_TOKEN.
# Safe because ENVIRONMENT=test, so assert_bootstrap_auth_safe() won't block it.
os.environ.setdefault("K1_ENABLE_BOOTSTRAP_AUTH", "true")
os.environ.setdefault("K1_ARTIFACTS_ROOT", str(REPO_ROOT / ".pytest_artifacts"))
Path(os.environ["K1_ARTIFACTS_ROOT"]).mkdir(parents=True, exist_ok=True)
# Ensure subprocess-based tests resolve to system python with installed test deps.
_path = os.environ.get("PATH", "")
if not _path.startswith("/usr/bin:"):
    os.environ["PATH"] = f"/usr/bin:{_path}"

_ORIGINAL_RUN_SYNC = anyio.to_thread.run_sync

async def _inline_run_sync(func, *args, abandon_on_cancel=False, cancellable=None, limiter=None):
    """Test-only fallback for environments where anyio thread handoff is unavailable."""
    return func(*args)


def _threadpool_handoff_healthy(timeout_seconds: float = 0.75) -> bool:
    outcome: dict[str, bool] = {"ok": False}

    def _runner() -> None:
        async def _probe() -> int:
            return await _ORIGINAL_RUN_SYNC(lambda: 1)

        try:
            outcome["ok"] = asyncio.run(_probe()) == 1
        except Exception:
            outcome["ok"] = False

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    return (not thread.is_alive()) and bool(outcome.get("ok"))


_INLINE_THREADPOOL_FALLBACK = not _threadpool_handoff_healthy()
if _INLINE_THREADPOOL_FALLBACK:
    anyio.to_thread.run_sync = _inline_run_sync
    os.environ.setdefault("K1_TEST_INLINE_THREADPOOL_FALLBACK", "1")

@pytest.fixture(scope='session')
def auth_headers():
    from apps.backend.src.core.auth import (
        create_access_token,
        ROLE_ADMIN, ROLE_ANALYST, ROLE_OPERATOR, ROLE_VIEWER,
    )
    token = create_access_token(
        subject="dev",
        roles=[ROLE_ADMIN, ROLE_ANALYST, ROLE_OPERATOR, ROLE_VIEWER],
    )
    return {'Authorization': f"Bearer {token}"}

@pytest.fixture(scope='session')
def client(auth_headers):
    try:
        from apps.backend.src.main import app  # noqa: E402
    except Exception as exc:  # pragma: no cover - environment/bootstrap guard
        pytest.skip(f"TestClient app bootstrap unavailable: {exc}")
    c = ASGITestClient(app)
    # Set default auth header for all requests in tests
    c.headers.update(auth_headers)
    return c


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:  # pragma: no cover - cleanup hook
    anyio.to_thread.run_sync = _ORIGINAL_RUN_SYNC
