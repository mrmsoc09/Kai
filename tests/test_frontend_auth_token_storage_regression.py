from __future__ import annotations

from pathlib import Path


FRONTEND_SRC = Path("apps/frontend/src")
FRONTEND_EXTS = {".ts", ".tsx", ".js", ".jsx"}


def _frontend_sources() -> list[Path]:
    return [p for p in FRONTEND_SRC.rglob("*") if p.suffix in FRONTEND_EXTS and p.is_file()]


def test_frontend_does_not_persist_bearer_tokens_in_browser_storage() -> None:
    banned_patterns = [
        "localStorage.getItem('k1_token')",
        'localStorage.getItem("k1_token")',
        "localStorage.setItem('k1_token'",
        'localStorage.setItem("k1_token"',
        "localStorage.getItem('K1_DEV_TOKEN')",
        'localStorage.getItem("K1_DEV_TOKEN")',
        "localStorage.setItem('K1_DEV_TOKEN'",
        'localStorage.setItem("K1_DEV_TOKEN"',
        "sessionStorage.getItem('k1_token')",
        'sessionStorage.getItem("k1_token")',
        "sessionStorage.setItem('k1_token'",
        'sessionStorage.setItem("k1_token"',
    ]

    offenders: list[str] = []
    for path in _frontend_sources():
        text = path.read_text(encoding="utf-8")
        for pattern in banned_patterns:
            if pattern in text:
                offenders.append(f"{path}:{pattern}")

    assert not offenders, "Found forbidden token storage patterns:\n" + "\n".join(offenders)
