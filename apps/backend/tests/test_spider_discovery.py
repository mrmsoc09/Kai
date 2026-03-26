from __future__ import annotations

import asyncio

from apps.backend.src.core.scope_state_engine import ScopeStateEngine
from apps.backend.src.core.spider_discovery import crawl_scraper_statefully


def test_spider_discovery_crawl_tracks_pages_deltas_and_blocked_modules(tmp_path):
    state_path = tmp_path / "spider_scope_state.json"
    scope_engine = ScopeStateEngine(state_path)
    scope_engine.load()

    pages = {
        (1, None): {
            "items": [
                {
                    "id": "google-core",
                    "name": "Google Core",
                    "url": "https://google.com",
                    "platform": "google_vrp",
                    "max_payout": 20000,
                    "disallowed_vulnerability_types": ["no brute force"],
                    "metadata": {"category": "cloud"},
                },
                {
                    "id": "workspace",
                    "name": "Workspace",
                    "url": "https://workspace.google.com",
                    "platform": "google_vrp",
                    "max_payout": 5000,
                    "metadata": {"category": "api"},
                },
            ],
            "has_more": True,
            "next_cursor": "c2",
            "session_expired": False,
        },
        (2, "c2"): {
            "items": [
                {
                    "id": "chrome",
                    "name": "Chrome",
                    "url": "https://www.google.com/chrome/",
                    "platform": "google_vrp",
                    "max_payout": 30000,
                    "metadata": {"category": "desktop"},
                }
            ],
            "has_more": False,
            "next_cursor": None,
            "session_expired": False,
        },
    }

    async def _fetch_page(*, page_number: int, cursor: str | None):
        return dict(pages.get((page_number, cursor), {"items": [], "has_more": False, "next_cursor": None, "session_expired": False}))

    async def _reauth():
        return True

    assets, summary = asyncio.run(
        crawl_scraper_statefully(
            source="google_vrp",
            scope_engine=scope_engine,
            fetch_page_coro=_fetch_page,
            reauthenticate_coro=_reauth,
            max_concurrency=2,
            max_pages=10,
            retry_attempts=2,
        )
    )

    assert summary.processed_pages == 2
    assert summary.total_assets_seen == 3
    assert summary.total_new_assets == 3
    assert "google-core" in summary.blocked_modules_by_asset
    assert "brute_force" in summary.blocked_modules_by_asset["google-core"]
    assert len(summary.prioritized_asset_ids) >= 1
    assert any(row.get("priority_bucket") == "top_20_percent" for row in assets)

    # Second run over same pages should produce no new assets.
    scope_engine_2 = ScopeStateEngine(state_path)
    scope_engine_2.load()
    _, summary_2 = asyncio.run(
        crawl_scraper_statefully(
            source="google_vrp",
            scope_engine=scope_engine_2,
            fetch_page_coro=_fetch_page,
            reauthenticate_coro=_reauth,
            max_concurrency=2,
            max_pages=10,
            retry_attempts=2,
        )
    )
    assert summary_2.total_new_assets == 0
