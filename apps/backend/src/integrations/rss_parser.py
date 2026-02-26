"""
Kaison K1 - RSS Intelligence Parser
Automated vulnerability feed monitoring with CVE extraction and EPSS enrichment
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

import aiohttp
import feedparser
from bs4 import BeautifulSoup

from .epss_client import get_epss_client

logger = logging.getLogger(__name__)


@dataclass
class RSSItem:
    """RSS feed item with extracted intelligence"""
    feed: str
    title: str
    link: str
    published: datetime
    content: str
    summary: str
    cves: List[str]
    tags: List[str]
    raw_data: Dict[str, Any]


@dataclass
class EnrichedCVE:
    """CVE with EPSS enrichment"""
    cve_id: str
    epss_score: Optional[float]
    epss_percentile: Optional[float]
    source_feed: str
    discovered_at: datetime


class RSSIntelligenceParser:
    """Parser for security intelligence RSS feeds"""

    # Security intelligence RSS feeds
    FEEDS = {
        'nvd': {
            'url': 'https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml',
            'description': 'NIST National Vulnerability Database',
            'priority': 1
        },
        'full_disclosure': {
            'url': 'https://seclists.org/rss/fulldisclosure.rss',
            'description': 'Full Disclosure Mailing List',
            'priority': 2
        },
        'exploit_db': {
            'url': 'https://www.exploit-db.com/rss.xml',
            'description': 'Exploit Database',
            'priority': 1
        },
        'packet_storm': {
            'url': 'https://packetstormsecurity.com/feeds/news/',
            'description': 'Packet Storm Security',
            'priority': 2
        },
        'reddit_netsec': {
            'url': 'https://www.reddit.com/r/netsec/.rss',
            'description': 'Reddit Network Security',
            'priority': 3
        },
        'cisa_alerts': {
            'url': 'https://www.cisa.gov/cybersecurity-advisories/rss.xml',
            'description': 'CISA Cybersecurity Advisories',
            'priority': 1
        },
        'reddit_vulndb': {
            'url': 'https://www.reddit.com/r/CVE/.rss',
            'description': 'Reddit CVE Subreddit',
            'priority': 3
        },
        'bleeping_computer': {
            'url': 'https://www.bleepingcomputer.com/feed/',
            'description': 'Bleeping Computer Security News',
            'priority': 2
        }
    }

    # CVE pattern regex
    CVE_PATTERN = re.compile(r'CVE-\d{4}-\d{4,7}', re.IGNORECASE)

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.epss_client = get_epss_client()

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Kaison K1 Security Intelligence Platform/1.0'
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def fetch_feed(self, feed_name: str) -> List[RSSItem]:
        """Fetch and parse RSS feed"""
        if feed_name not in self.FEEDS:
            raise ValueError(f"Unknown feed: {feed_name}")

        feed_config = self.FEEDS[feed_name]
        feed_url = feed_config['url']

        try:
            logger.info(f"Fetching RSS feed: {feed_name} from {feed_url}")

            # Fetch feed content
            if not self.session:
                raise RuntimeError("Session not initialized. Use 'async with' context manager")

            async with self.session.get(feed_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch {feed_name}: HTTP {response.status}")
                    return []

                content = await response.text()

            # Parse feed
            feed = feedparser.parse(content)

            if not feed.entries:
                logger.warning(f"No entries found in feed: {feed_name}")
                return []

            # Process entries
            items = []
            for entry in feed.entries:
                try:
                    item = await self._parse_entry(entry, feed_name)
                    if item:
                        items.append(item)
                except Exception as e:
                    logger.error(f"Error parsing entry from {feed_name}: {e}")
                    continue

            logger.info(f"Fetched {len(items)} items from {feed_name}")
            return items

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching feed: {feed_name}")
            return []
        except Exception as e:
            logger.error(f"Error fetching feed {feed_name}: {e}")
            return []

    async def _parse_entry(self, entry: Any, feed_name: str) -> Optional[RSSItem]:
        """Parse individual RSS entry"""
        try:
            # Extract basic fields
            title = entry.get('title', 'No Title')
            link = entry.get('link', '')

            # Parse published date
            published = datetime.now()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                import time
                published = datetime.fromtimestamp(time.mktime(entry.published_parsed))
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                import time
                published = datetime.fromtimestamp(time.mktime(entry.updated_parsed))

            # Extract content
            content = ''
            if hasattr(entry, 'content') and entry.content:
                content = entry.content[0].get('value', '')
            elif hasattr(entry, 'description'):
                content = entry.description
            elif hasattr(entry, 'summary'):
                content = entry.summary

            # Clean HTML from content
            soup = BeautifulSoup(content, 'html.parser')
            clean_content = soup.get_text(separator=' ', strip=True)

            # Generate summary (first 200 chars)
            summary = clean_content[:200] + '...' if len(clean_content) > 200 else clean_content

            # Extract CVEs
            cves = self.extract_cves(title + ' ' + clean_content)

            # Extract tags
            tags = []
            if hasattr(entry, 'tags'):
                tags = [tag.term for tag in entry.tags if hasattr(tag, 'term')]

            return RSSItem(
                feed=feed_name,
                title=title,
                link=link,
                published=published,
                content=clean_content,
                summary=summary,
                cves=cves,
                tags=tags,
                raw_data=dict(entry)
            )

        except Exception as e:
            logger.error(f"Error parsing entry: {e}")
            return None

    def extract_cves(self, text: str) -> List[str]:
        """Extract CVE IDs from text"""
        matches = self.CVE_PATTERN.findall(text)
        # Normalize to uppercase and deduplicate
        cves = list(set([cve.upper() for cve in matches]))
        return sorted(cves)

    async def enrich_with_epss(self, cves: List[str]) -> List[EnrichedCVE]:
        """Enrich CVE list with EPSS scores"""
        enriched = []

        try:
            # Batch lookup EPSS scores
            epss_data = await self.epss_client.get_scores(cves)

            for cve_id in cves:
                epss_score = None
                epss_percentile = None

                if cve_id in epss_data:
                    epss_info = epss_data[cve_id]
                    epss_score = epss_info.get('epss')
                    epss_percentile = epss_info.get('percentile')

                enriched.append(EnrichedCVE(
                    cve_id=cve_id,
                    epss_score=epss_score,
                    epss_percentile=epss_percentile,
                    source_feed='',
                    discovered_at=datetime.now()
                ))

        except Exception as e:
            logger.error(f"Error enriching CVEs with EPSS: {e}")
            # Return CVEs without EPSS data
            for cve_id in cves:
                enriched.append(EnrichedCVE(
                    cve_id=cve_id,
                    epss_score=None,
                    epss_percentile=None,
                    source_feed='',
                    discovered_at=datetime.now()
                ))

        return enriched

    async def fetch_all_feeds(self) -> Dict[str, List[RSSItem]]:
        """Fetch all configured RSS feeds"""
        logger.info(f"Fetching {len(self.FEEDS)} RSS feeds")

        tasks = []
        feed_names = []

        for feed_name in self.FEEDS.keys():
            tasks.append(self.fetch_feed(feed_name))
            feed_names.append(feed_name)

        # Fetch all feeds concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Organize results by feed
        feed_items = {}
        for feed_name, result in zip(feed_names, results):
            if isinstance(result, Exception):
                logger.error(f"Exception fetching {feed_name}: {result}")
                feed_items[feed_name] = []
            else:
                feed_items[feed_name] = result

        total_items = sum(len(items) for items in feed_items.values())
        logger.info(f"Fetched {total_items} total items from all feeds")

        return feed_items

    async def get_high_priority_items(
        self,
        min_epss: float = 0.7,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get high-priority CVEs from recent feeds"""

        # Fetch all feeds
        feed_items = await self.fetch_all_feeds()

        # Collect all items with CVEs
        items_with_cves = []
        for feed_name, items in feed_items.items():
            for item in items:
                if item.cves:
                    # Filter by time
                    age_hours = (datetime.now() - item.published).total_seconds() / 3600
                    if age_hours <= hours:
                        items_with_cves.append({
                            'item': item,
                            'feed_priority': self.FEEDS[feed_name]['priority']
                        })

        # Extract all unique CVEs
        all_cves = set()
        for data in items_with_cves:
            all_cves.update(data['item'].cves)

        # Enrich with EPSS
        enriched_cves = await self.enrich_with_epss(list(all_cves))

        # Create CVE lookup
        cve_lookup = {cve.cve_id: cve for cve in enriched_cves}

        # Filter high-priority items
        high_priority = []
        for data in items_with_cves:
            item = data['item']
            feed_priority = data['feed_priority']

            # Check if any CVE has high EPSS
            max_epss = 0.0
            for cve_id in item.cves:
                if cve_id in cve_lookup and cve_lookup[cve_id].epss_score:
                    max_epss = max(max_epss, cve_lookup[cve_id].epss_score)

            if max_epss >= min_epss:
                high_priority.append({
                    'feed': item.feed,
                    'title': item.title,
                    'link': item.link,
                    'published': item.published.isoformat(),
                    'cves': item.cves,
                    'max_epss': max_epss,
                    'feed_priority': feed_priority,
                    'summary': item.summary
                })

        # Sort by EPSS score (descending) and feed priority
        high_priority.sort(key=lambda x: (x['max_epss'], -x['feed_priority']), reverse=True)

        logger.info(f"Found {len(high_priority)} high-priority items (EPSS >= {min_epss})")
        return high_priority

    def get_feed_list(self) -> List[Dict[str, Any]]:
        """Get list of all configured feeds"""
        return [
            {
                'name': name,
                'url': config['url'],
                'description': config['description'],
                'priority': config['priority']
            }
            for name, config in self.FEEDS.items()
        ]


# Singleton pattern
_rss_parser_instance: Optional[RSSIntelligenceParser] = None


def get_rss_parser() -> RSSIntelligenceParser:
    """Get or create RSS parser instance"""
    global _rss_parser_instance
    if _rss_parser_instance is None:
        _rss_parser_instance = RSSIntelligenceParser()
    return _rss_parser_instance
