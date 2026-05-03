"""Simple caching for scraped data."""

import json
import hashlib
from pathlib import Path
from typing import Optional, Set
import time


class ScrapingCache:
    """File-based cache for scraping results."""
    
    def __init__(self, cache_dir: str = ".wordlist_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl = 3600  # 1 hour default
        
    def _get_cache_key(self, target: str) -> str:
        """Generate cache key from target."""
        return hashlib.md5(target.encode()).hexdigest()
    
    def get(self, target: str) -> Optional[Set[str]]:
        """Retrieve cached data if valid."""
        cache_file = self.cache_dir / f"{self._get_cache_key(target)}.json"
        
        if not cache_file.exists():
            return None
            
        # Check TTL
        if time.time() - cache_file.stat().st_mtime > self.ttl:
            return None
            
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                return set(data.get('keywords', []))
        except:
            return None
    
    def set(self, target: str, keywords: Set[str]):
        """Cache scraping results."""
        cache_file = self.cache_dir / f"{self._get_cache_key(target)}.json"
        
        with open(cache_file, 'w') as f:
            json.dump({
                'target': target,
                'keywords': list(keywords),
                'timestamp': time.time()
            }, f)
            
    def clear(self):
        """Clear all cached data."""
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
