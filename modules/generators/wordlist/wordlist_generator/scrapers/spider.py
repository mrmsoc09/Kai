"""Intelligent spider for crawling and keyword extraction."""

import asyncio
from typing import Set, List, Optional
from urllib.parse import urljoin, urlparse
import re
import logging

from bs4 import BeautifulSoup
import aiohttp
from asyncio_throttle import Throttler

logger = logging.getLogger(__name__)


class IntelligentSpider:
    """Context-aware web spider with keyword extraction."""
    
    def __init__(self, max_depth: int = 2, max_pages: int = 50, 
                 delay: float = 1.0, respect_robots: bool = True):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.delay = delay
        self.respect_robots = respect_robots
        self.visited = set()
        self.keywords = set()
        self.throttler = Throttler(rate_limit=1, period=delay)
        
        # Context-aware extraction patterns
        self.patterns = {
            'emails': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phones': re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
            'names': re.compile(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'),
            'products': re.compile(r'\b[A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*)+\b'),
            'tech_terms': re.compile(r'\b(?:API|SDK|JSON|XML|HTML|CSS|JS|Python|Java|React|Node)\b', re.I),
        }
        
    async def crawl(self, start_url: str, session: aiohttp.ClientSession) -> Set[str]:
        """Crawl starting from URL and extract keywords."""
        to_visit = [(start_url, 0)]
        domain = urlparse(start_url).netloc
        
        while to_visit and len(self.visited) < self.max_pages:
            url, depth = to_visit.pop(0)
            
            if url in self.visited or depth > self.max_depth:
                continue
                
            self.visited.add(url)
            
            try:
                async with self.throttler:
                    async with session.get(url, timeout=30) as response:
                        if response.status == 200:
                            content = await response.text()
                            self._extract_keywords(content, url)
                            
                            if depth < self.max_depth:
                                links = self._extract_links(content, url, domain)
                                for link in links:
                                    if link not in self.visited:
                                        to_visit.append((link, depth + 1))
                                        
            except Exception as e:
                logger.debug(f"Failed to fetch {url}: {e}")
                
        return self.keywords
    
    def _extract_keywords(self, content: str, url: str):
        """Extract contextual keywords from content."""
        soup = BeautifulSoup(content, 'lxml')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
            
        # Extract text
        text = soup.get_text(separator=' ', strip=True)
        
        # Extract using patterns
        for pattern_name, pattern in self.patterns.items():
            matches = pattern.findall(text)
            self.keywords.update(matches)
            
        # Extract meaningful words (capitalized compounds, likely proper nouns)
        words = re.findall(r'\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b', text)
        self.keywords.update(words)
        
        # Extract from meta tags
        meta_tags = soup.find_all('meta', attrs={'name': ['keywords', 'description', 'author']})
        for tag in meta_tags:
            content = tag.get('content', '')
            if content:
                self.keywords.update(content.split(','))
                
        # Extract from title
        title = soup.find('title')
        if title:
            self.keywords.add(title.get_text(strip=True))
            
    def _extract_links(self, content: str, base_url: str, domain: str) -> List[str]:
        """Extract internal links."""
        soup = BeautifulSoup(content, 'lxml')
        links = []
        
        for anchor in soup.find_all('a', href=True):
            href = anchor['href']
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            if parsed.netloc == domain and full_url not in self.visited:
                links.append(full_url)
                
        return links[:10]  # Limit links per page to avoid explosion
