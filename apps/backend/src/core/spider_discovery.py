from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from .scope_state_engine import ScopeStateEngine


logger = logging.getLogger(__name__)


DELTA_NEW_ASSET_POINTS = 25
DELTA_INTERNAL_OR_CLOUD_POINTS = 40
DELTA_CRITICAL_TIER_POINTS = 35


class SpiderAsset(BaseModel):
    id: str
    name: str
    url: str
    platform: str
    program_type: str = "bug_bounty"
    max_payout: float = 0.0
    disallowed_vulnerability_types: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScrapeError(BaseModel):
    source: str
    page_number: int
    cursor: str | None = None
    message: str


class SpiderCrawlSummary(BaseModel):
    total_assets_seen: int = 0
    total_new_assets: int = 0
    queued_pages: int = 0
    processed_pages: int = 0
    errors: list[ScrapeError] = Field(default_factory=list)
    blocked_modules_by_asset: dict[str, list[str]] = Field(default_factory=dict)
    prioritized_asset_ids: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class _PageTask:
    source: str
    page_number: int
    cursor: str | None = None


def _asset_fingerprint_payload(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": asset.get("id") or asset.get("name") or asset.get("url") or "",
        "url": asset.get("url") or "",
        "type": asset.get("program_type") or "program",
    }


def _is_internal_or_cloud(asset: dict[str, Any]) -> bool:
    platform = str(asset.get("platform") or "").lower()
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    category = str(metadata.get("category") or "").lower()
    tags = metadata.get("tags")
    if not isinstance(tags, list):
        tags = []
    tags_l = [str(t).lower() for t in tags]
    if platform in {"google_vrp", "microsoft", "amazon", "aws", "azure"}:
        return True
    if any(token in category for token in ("cloud", "api", "internal")):
        return True
    return any(token in tags_l for token in ("cloud", "api", "internal"))


def _is_critical_tier(asset: dict[str, Any]) -> bool:
    max_payout = float(asset.get("max_payout") or 0.0)
    payouts = asset.get("payout_structure")
    if isinstance(payouts, list):
        for row in payouts:
            if not isinstance(row, dict):
                continue
            sev = str(row.get("severity_level") or "").lower()
            if sev == "critical":
                return True
    return max_payout >= 10_000.0


def score_asset_delta(asset: dict[str, Any], *, is_new_asset: bool) -> int:
    score = 0
    if is_new_asset:
        score += DELTA_NEW_ASSET_POINTS
    if _is_internal_or_cloud(asset):
        score += DELTA_INTERNAL_OR_CLOUD_POINTS
    if _is_critical_tier(asset):
        score += DELTA_CRITICAL_TIER_POINTS
    return score


def _extract_blocked_modules(asset: dict[str, Any]) -> list[str]:
    """
    Scope whisperer:
    infer blocked scanning modules from program restrictions.
    """
    blocked: set[str] = set()
    raw = asset.get("disallowed_vulnerability_types")
    disallowed = [str(v).strip().lower() for v in raw] if isinstance(raw, list) else []

    restriction_hints: list[str] = []
    metadata = asset.get("metadata")
    if isinstance(metadata, dict):
        rules = metadata.get("rules")
        if isinstance(rules, list):
            restriction_hints.extend(str(v).lower() for v in rules)
        elif isinstance(rules, str):
            restriction_hints.append(rules.lower())

    combined = " | ".join(disallowed + restriction_hints)

    if "brute" in combined:
        blocked.add("brute_force")
    if "dos" in combined or "denial of service" in combined:
        blocked.add("dos")
    if "social" in combined or "phishing" in combined:
        blocked.add("social_engineering")
    if "physical" in combined:
        blocked.add("physical_testing")
    if "rate limit" in combined:
        blocked.add("aggressive_crawling")

    # Map direct vuln bans to scanners.
    if "sqli" in combined or "sql injection" in combined:
        blocked.add("sql_injection")
    if "xss" in combined:
        blocked.add("xss")
    if "ssrf" in combined:
        blocked.add("ssrf")

    return sorted(blocked)


def prioritize_top_twenty_percent(assets: list[dict[str, Any]]) -> list[str]:
    if not assets:
        return []
    sorted_assets = sorted(
        assets,
        key=lambda item: int(item.get("delta_score") or 0),
        reverse=True,
    )
    top_n = max(1, int(len(sorted_assets) * 0.2))
    return [str(row.get("id") or "") for row in sorted_assets[:top_n] if str(row.get("id") or "")]


async def crawl_scraper_statefully(
    *,
    source: str,
    scope_engine: ScopeStateEngine,
    fetch_page_coro,
    reauthenticate_coro,
    max_concurrency: int = 3,
    max_pages: int = 5000,
    retry_attempts: int = 3,
) -> tuple[list[dict[str, Any]], SpiderCrawlSummary]:
    """
    Stateful BFS pagination crawler with retry-and-notify behavior.
    """
    summary = SpiderCrawlSummary()
    queue: asyncio.Queue[_PageTask] = asyncio.Queue()
    queue.put_nowait(_PageTask(source=source, page_number=1, cursor=None))
    summary.queued_pages = 1

    seen_tasks: set[tuple[str, int, str | None]] = set()
    assets: list[dict[str, Any]] = []
    new_assets: list[dict[str, Any]] = []
    async def worker() -> None:
        nonlocal assets, new_assets
        while True:
            task = await queue.get()
            try:
                if task.source == "__stop__":
                    return
                if summary.processed_pages >= max_pages:
                    continue
                task_key = (task.source, task.page_number, task.cursor)
                if task_key in seen_tasks:
                    continue
                seen_tasks.add(task_key)

                if not scope_engine.should_fetch_page(
                    source=task.source,
                    page_number=task.page_number,
                    cursor=task.cursor,
                ):
                    continue

                last_error: Exception | None = None
                page_payload: dict[str, Any] | None = None
                for attempt in range(1, retry_attempts + 1):
                    try:
                        page_payload = await fetch_page_coro(page_number=task.page_number, cursor=task.cursor)
                        break
                    except Exception as exc:  # noqa: PERF203
                        last_error = exc
                        if attempt < retry_attempts:
                            await asyncio.sleep(0.5 * attempt)
                        else:
                            summary.errors.append(
                                ScrapeError(
                                    source=task.source,
                                    page_number=task.page_number,
                                    cursor=task.cursor,
                                    message=str(exc),
                                )
                            )
                if page_payload is None:
                    if last_error:
                        logger.warning("Spider page fetch failed source=%s page=%s err=%s", task.source, task.page_number, last_error)
                    continue

                items = page_payload.get("items") if isinstance(page_payload.get("items"), list) else []
                has_more = bool(page_payload.get("has_more"))
                next_cursor = page_payload.get("next_cursor")
                session_expired = bool(page_payload.get("session_expired"))

                if session_expired:
                    try:
                        ok = await reauthenticate_coro()
                    except Exception as exc:
                        ok = False
                        summary.errors.append(
                            ScrapeError(
                                source=task.source,
                                page_number=task.page_number,
                                cursor=task.cursor,
                                message=f"reauth_failed:{exc}",
                            )
                        )
                    if ok:
                        # Requeue same page/cursor and continue.
                        retry_task = _PageTask(source=task.source, page_number=task.page_number, cursor=task.cursor)
                        await queue.put(retry_task)
                        summary.queued_pages += 1
                    continue

                scope_engine.mark_page(
                    source=task.source,
                    page_number=task.page_number,
                    cursor=task.cursor,
                    next_cursor=str(next_cursor) if next_cursor else None,
                    item_count=len(items),
                )
                summary.processed_pages += 1

                page_new_assets: list[dict[str, Any]] = []
                current_page_assets: list[dict[str, Any]] = []
                for raw in items:
                    if not isinstance(raw, dict):
                        continue
                    asset = dict(raw)
                    fp_payload = _asset_fingerprint_payload(asset)
                    asset["id"] = asset.get("id") or fp_payload["id"]
                    asset["delta_score"] = 0
                    asset["blocked_modules"] = _extract_blocked_modules(asset)
                    if asset.get("blocked_modules"):
                        summary.blocked_modules_by_asset[str(asset["id"])] = list(asset["blocked_modules"])
                    assets.append(asset)
                    current_page_assets.append(asset)
                    page_new_assets.append(fp_payload)

                truly_new = scope_engine.identify_new_opportunities(page_new_assets)
                new_fingerprints = {scope_engine.get_asset_fingerprint(row) for row in truly_new}

                for asset in current_page_assets:
                    fp = scope_engine.get_asset_fingerprint(_asset_fingerprint_payload(asset))
                    is_new_asset = fp in new_fingerprints
                    asset["is_new_asset"] = is_new_asset
                    asset["delta_score"] = score_asset_delta(asset, is_new_asset=is_new_asset)
                    if is_new_asset:
                        new_assets.append(asset)

                summary.total_assets_seen += len(page_new_assets)
                summary.total_new_assets += len(truly_new)

                if has_more or next_cursor:
                    next_page = _PageTask(
                        source=task.source,
                        page_number=task.page_number + 1,
                        cursor=str(next_cursor) if next_cursor is not None else None,
                    )
                    await queue.put(next_page)
                    summary.queued_pages += 1
            finally:
                queue.task_done()

    worker_count = max(1, int(max_concurrency))
    workers = [asyncio.create_task(worker()) for _ in range(worker_count)]
    await queue.join()
    for _ in workers:
        queue.put_nowait(_PageTask(source="__stop__", page_number=max_pages + 1))
    await asyncio.gather(*workers, return_exceptions=True)

    scope_engine.save()
    summary.prioritized_asset_ids = prioritize_top_twenty_percent(assets)
    prioritized = set(summary.prioritized_asset_ids)
    for asset in assets:
        asset["priority_bucket"] = "top_20_percent" if str(asset.get("id")) in prioritized else "baseline"

    return assets, summary
