from __future__ import annotations

from types import SimpleNamespace

from apps.backend.src.routers import credentials as creds


def _opportunity(idx: int):
    return SimpleNamespace(
        id=f"hackerone:program-{idx}",
        name=f"Program {idx}",
        organization="Example Corp",
        platform="hackerone",
        credential_requirements=[
            SimpleNamespace(
                kind="signup",
                label="Hunter account",
                signup_url="https://hackerone.com/users/sign_up",
                notes="",
                required=True,
            )
        ],
        scope_domains=[f"app{idx}.example.com"],
    )


def test_scan_suggestions_only_return_account_ready_matches(monkeypatch):
    inventory = {
        "records": [
            {
                "display_name": "HackerOne main",
                "platform_hint": "hackerone",
                "credential_kind": "hunter_account",
                "source_url": "https://hackerone.com/users/sign_in",
                "slug": "hackerone-main",
                "source_index": 1,
            }
        ]
    }

    monkeypatch.setattr(creds, "load_hunter_account_index", lambda: inventory)
    monkeypatch.setattr(creds, "list_filtered", lambda limit=500: [_opportunity(i) for i in range(60)])

    suggestions = creds._build_scan_suggestions(limit=50)

    assert len(suggestions) == 50
    assert all(item["account_ready"] is True for item in suggestions)
    assert all(item["matching_accounts"] for item in suggestions)
    assert all(item["score"] > 0 for item in suggestions)
