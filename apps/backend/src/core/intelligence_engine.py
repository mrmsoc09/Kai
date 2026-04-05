"""
Kaison K1 - Intelligence Engine
Automated threat intelligence processing with RSS feeds, EPSS scoring, and RAG indexing
"""

import asyncio
import hashlib
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from ..integrations.rss_parser import get_rss_parser, RSSItem
from ..integrations.epss_client import get_epss_client
from ..integrations.llamaindex_rag import get_llamaindex_rag

logger = logging.getLogger(__name__)


@dataclass
class IntelligenceItem:
    """Processed intelligence item"""
    id: str
    source: str
    title: str
    link: str
    published: datetime
    cves: List[str]
    max_epss_score: float
    priority_score: float
    summary: str
    indexed_in_rag: bool


class IntelligenceEngine:
    """Core intelligence processing engine"""

    def __init__(self):
        self.rss_parser = get_rss_parser()
        self.epss_client = get_epss_client()
        self.rag = None  # Initialized async
        self.last_scan_time: Optional[datetime] = None
        self.scan_interval_minutes = 60
        self.is_scanning = False
        self._background_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize intelligence engine"""
        logger.info("Initializing Intelligence Engine")
        self.rag = await get_llamaindex_rag()
        logger.info("Intelligence Engine initialized successfully")

    async def scan_feeds(self) -> List[IntelligenceItem]:
        """Scan all RSS feeds and extract intelligence"""
        if self.is_scanning:
            logger.warning("Scan already in progress, skipping...")
            return []

        self.is_scanning = True
        logger.info("Starting intelligence scan...")

        try:
            # Fetch all RSS feeds
            async with self.rss_parser:
                feed_items = await self.rss_parser.fetch_all_feeds()

            # Process all items
            intelligence_items = []
            all_items = []

            for feed_name, items in feed_items.items():
                for item in items:
                    published_at = self._normalize_datetime(item.published)
                    if published_at is None:
                        continue
                    all_items.append({
                        'feed': feed_name,
                        'title': item.title,
                        'link': item.link,
                        'published': published_at.isoformat(),
                        'content': item.content,
                        'summary': item.summary,
                        'cves': item.cves,
                        'tags': item.tags
                    })

            # Index in RAG
            if self.rag and all_items:
                logger.info(f"Indexing {len(all_items)} items in RAG...")
                await self.rag.index_rss_items(all_items)

            # Extract all unique CVEs
            all_cves = set()
            for item_data in all_items:
                all_cves.update(item_data.get('cves', []))

            # Enrich with EPSS scores
            logger.info(f"Enriching {len(all_cves)} CVEs with EPSS scores...")
            epss_data = {}
            if all_cves:
                try:
                    epss_data = await self.epss_client.get_scores(list(all_cves))
                except Exception as e:
                    logger.error(f"Error fetching EPSS scores: {e}")

            # Create intelligence items with priority scoring
            for item_data in all_items:
                # Calculate max EPSS score
                max_epss = 0.0
                for cve_id in item_data.get('cves', []):
                    if cve_id in epss_data:
                        epss_score = epss_data[cve_id].get('epss', 0.0)
                        max_epss = max(max_epss, epss_score)

                # Calculate priority score
                priority_score = self._calculate_priority_score(
                    item_data,
                    max_epss
                )

                # Create intelligence item
                intel_item = IntelligenceItem(
                    id=self._stable_item_id(item_data["feed"], item_data["link"]),
                    source=item_data['feed'],
                    title=item_data['title'],
                    link=item_data['link'],
                    published=self._normalize_datetime(item_data.get("published")) or datetime.now(timezone.utc),
                    cves=item_data['cves'],
                    max_epss_score=max_epss,
                    priority_score=priority_score,
                    summary=item_data['summary'],
                    indexed_in_rag=True
                )

                intelligence_items.append(intel_item)

            # Sort by priority score
            intelligence_items.sort(key=lambda x: x.priority_score, reverse=True)

            self.last_scan_time = datetime.now(timezone.utc)
            logger.info(f"Intelligence scan completed. Found {len(intelligence_items)} items")

            return intelligence_items

        except Exception as e:
            logger.error(f"Error during intelligence scan: {e}")
            return []

        finally:
            self.is_scanning = False

    def _calculate_priority_score(
        self,
        item: Dict[str, Any],
        max_epss: float
    ) -> float:
        """Calculate priority score for intelligence item"""
        score = 0.0

        # EPSS score contributes 60%
        score += max_epss * 0.6

        # Recency contributes 20%
        try:
            published = item.get('published')
            published = self._normalize_datetime(published)
            if published is None:
                raise ValueError("missing/invalid published timestamp")

            age_hours = (datetime.now(timezone.utc) - published).total_seconds() / 3600
            recency_score = max(0, 1.0 - (age_hours / 168))  # Decay over 7 days
            score += recency_score * 0.2
        except Exception:
            pass

        # Number of CVEs contributes 10%
        cve_count = len(item.get('cves', []))
        cve_score = min(1.0, cve_count / 5)  # Normalize to max 5 CVEs
        score += cve_score * 0.1

        # Feed priority contributes 10%
        feed_name = item.get('feed', '')
        feed_priorities = {
            'nvd': 1.0,
            'cisa_alerts': 1.0,
            'exploit_db': 0.9,
            'full_disclosure': 0.8,
            'packet_storm': 0.7,
            'bleeping_computer': 0.6,
            'reddit_netsec': 0.5,
            'reddit_vulndb': 0.5
        }
        feed_score = feed_priorities.get(feed_name, 0.5)
        score += feed_score * 0.1

        return score

    async def prioritize_intelligence(
        self,
        items: List[IntelligenceItem],
        min_epss: float = 0.5
    ) -> List[IntelligenceItem]:
        """Filter and prioritize intelligence by EPSS score and recency"""
        # Filter by min EPSS
        filtered = [item for item in items if item.max_epss_score >= min_epss]

        # Sort by priority score
        filtered.sort(key=lambda x: x.priority_score, reverse=True)

        logger.info(f"Prioritized {len(filtered)} items (min EPSS: {min_epss})")
        return filtered

    async def get_high_priority_cves(
        self,
        min_epss: float = 0.7,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get high-priority CVEs from recent intelligence"""
        logger.info(f"Getting high-priority CVEs (EPSS >= {min_epss}, last {hours}h)")

        try:
            async with self.rss_parser:
                high_priority = await self.rss_parser.get_high_priority_items(
                    min_epss=min_epss,
                    hours=hours
                )

            return high_priority

        except Exception as e:
            logger.error(f"Error getting high-priority CVEs: {e}")
            return []

    async def auto_generate_nuclei_templates(
        self,
        cves: List[str]
    ) -> Dict[str, Optional[str]]:
        """Auto-generate Nuclei templates for high-EPSS CVEs"""
        if not self.rag:
            logger.error("RAG not initialized")
            return {}

        templates = {}

        for cve_id in cves:
            try:
                logger.info(f"Generating Nuclei template for {cve_id}")
                template = await self.rag.generate_nuclei_template(cve_id)
                templates[cve_id] = template

            except Exception as e:
                logger.error(f"Error generating template for {cve_id}: {e}")
                templates[cve_id] = None

        return templates

    async def start_background_scanner(self, interval_minutes: int = 60):
        """Start background intelligence scanner"""
        self.scan_interval_minutes = max(1, int(interval_minutes))
        if self._background_task and not self._background_task.done():
            logger.info("Background intelligence scanner already running")
            return
        logger.info(f"Starting background intelligence scanner (interval: {interval_minutes}m)")

        async def scan_loop():
            while True:
                try:
                    await self.scan_feeds()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"Error in background scanner: {e}")

                # Wait for next scan
                await asyncio.sleep(self.scan_interval_minutes * 60)

        # Create background task
        self._background_task = asyncio.create_task(scan_loop())
        logger.info("Background intelligence scanner started")

    async def stop_background_scanner(self):
        """Stop background intelligence scanner"""
        if self._background_task:
            logger.info("Stopping background intelligence scanner")
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None

    def get_scan_status(self) -> Dict[str, Any]:
        """Get intelligence scanner status"""
        return {
            "is_scanning": self.is_scanning,
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "scan_interval_minutes": self.scan_interval_minutes,
            "background_scanner_active": self._background_task is not None and not self._background_task.done()
        }

    @staticmethod
    def _stable_item_id(feed: str, link: str) -> str:
        payload = f"{feed.strip().lower()}|{link.strip()}"
        digest = hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()
        return f"{feed}_{digest[:16]}"

    @staticmethod
    def _normalize_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            token = value.strip()
            if not token:
                return None
            if token.endswith("Z"):
                token = token[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(token)
            except ValueError:
                return None
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return None


# Singleton pattern
_intelligence_engine_instance: Optional[IntelligenceEngine] = None


async def get_intelligence_engine() -> IntelligenceEngine:
    """Get or create intelligence engine instance"""
    global _intelligence_engine_instance
    if _intelligence_engine_instance is None:
        _intelligence_engine_instance = IntelligenceEngine()
        await _intelligence_engine_instance.initialize()
    return _intelligence_engine_instance


async def start_intelligence_scanner(interval_minutes: int = 60):
    """Start background intelligence scanner on startup"""
    engine = await get_intelligence_engine()
    await engine.start_background_scanner(interval_minutes)


async def shutdown_intelligence_engine():
    """Gracefully stop intelligence background tasks and close clients."""
    global _intelligence_engine_instance
    if _intelligence_engine_instance is None:
        return
    await _intelligence_engine_instance.stop_background_scanner()
    try:
        await _intelligence_engine_instance.epss_client.close()
    except Exception:
        pass
