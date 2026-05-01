"""Web scraping implementation using async HTTP."""

import asyncio
from typing import Set, Optional
import logging

import aiohttp
import tldextract

from wordlist_generator.scrapers.base import BaseScraper
from wordlist_generator.scrapers.spider import IntelligentSpider
from wordlist_generator.core.config import ScraperConfig

logger = logging.getLogger(__name__)


class WebScraper(BaseScraper):
    """Production web scraper with intelligent crawling."""
    
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.spider = IntelligentSpider(
            max_depth=config.max_depth,
            max_pages=config.max_pages,
            delay=config.delay,
            respect_robots=config.respect_robots_txt
        )
        
    async def scrape(self, target: str) -> Set[str]:
        """Scrape target domain for keywords."""
        # Normalize target
        if not target.startswith(('http://', 'https://')):
            target = f"https://{target}"
            
        headers = {
            'User-Agent': self.config.user_agent,
            **self.config.headers
        }
        
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        
        async with aiohttp.ClientSession(
            headers=headers,
            timeout=timeout
        ) as session:
            self.session = session
            
            try:
                keywords = await self.spider.crawl(target, session)
                
                # Also try common variations
                domain_info = tldextract.extract(target)
                base_domain = f"{domain_info.domain}.{domain_info.suffix}"
                
                # Add domain parts as keywords
                keywords.add(domain_info.domain)
                keywords.add(base_domain)
                
                return keywords
                
            except Exception as e:
                logger.error(f"Scraping failed: {e}")
                return {target}  # Fallback to at least having the target
                
    async def close(self):
        """Cleanup."""
        if self.session and not self.session.closed:
            await self.session.close()
