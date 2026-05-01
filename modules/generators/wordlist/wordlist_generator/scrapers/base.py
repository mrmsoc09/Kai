"""Abstract base class for scrapers."""

from abc import ABC, abstractmethod
from typing import Set


class BaseScraper(ABC):
    """Abstract base for all scrapers."""
    
    @abstractmethod
    async def scrape(self, target: str) -> Set[str]:
        """Scrape target and return set of keywords."""
        pass
    
    @abstractmethod
    async def close(self):
        """Cleanup resources."""
        pass
