"""
EPSS (Exploit Prediction Scoring System) Client

Integrates with FIRST.org EPSS API to fetch exploit probability scores for CVEs.
Provides caching to reduce API load and improve performance.

API Documentation: https://www.first.org/epss/api
"""

import httpx
import asyncio
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class EPSSScore:
    """EPSS score for a CVE."""
    cve_id: str
    epss: float  # Probability of exploitation (0-1)
    percentile: float  # Percentile rank (0-1)
    date: str  # Score date (YYYY-MM-DD)
    fetched_at: str  # When we fetched it


class EPSSCache:
    """Simple file-based cache for EPSS scores."""

    def __init__(self, cache_dir: str = "var/epss_cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        self.memory_cache: Dict[str, EPSSScore] = {}

    def _get_cache_file(self, cve_id: str) -> Path:
        """Get cache file path for a CVE."""
        return self.cache_dir / f"{cve_id.replace('-', '_')}.json"

    def get(self, cve_id: str) -> Optional[EPSSScore]:
        """Get cached score for a CVE."""
        # Check memory cache first
        if cve_id in self.memory_cache:
            score = self.memory_cache[cve_id]
            # Check if still valid
            fetched_at = datetime.fromisoformat(score.fetched_at)
            if datetime.utcnow() - fetched_at < self.ttl:
                return score

        # Check file cache
        cache_file = self._get_cache_file(cve_id)
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)

            score = EPSSScore(**data)

            # Check if still valid
            fetched_at = datetime.fromisoformat(score.fetched_at)
            if datetime.utcnow() - fetched_at < self.ttl:
                self.memory_cache[cve_id] = score
                return score
            else:
                # Expired, delete cache file
                cache_file.unlink()
                return None

        except Exception as e:
            logger.error(f"Error reading cache for {cve_id}: {e}")
            return None

    def set(self, score: EPSSScore):
        """Cache a score."""
        # Update memory cache
        self.memory_cache[score.cve_id] = score

        # Write to file
        cache_file = self._get_cache_file(score.cve_id)
        try:
            with open(cache_file, 'w') as f:
                json.dump(asdict(score), f, indent=2)
        except Exception as e:
            logger.error(f"Error writing cache for {score.cve_id}: {e}")

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total_files = len(list(self.cache_dir.glob("*.json")))
        memory_entries = len(self.memory_cache)

        return {
            "cache_dir": str(self.cache_dir),
            "total_cached_cves": total_files,
            "memory_cache_size": memory_entries,
            "ttl_hours": self.ttl.total_seconds() / 3600,
        }


class EPSSClient:
    """Client for EPSS API."""

    BASE_URL = "https://api.first.org/data/v1"

    def __init__(self, cache_dir: str = "var/epss_cache", cache_ttl_hours: int = 24):
        self.cache = EPSSCache(cache_dir, cache_ttl_hours)
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.stats = {
            "api_calls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
        }

    async def get_score(self, cve_id: str) -> Optional[EPSSScore]:
        """Get EPSS score for a single CVE.

        Args:
            cve_id: CVE identifier (e.g., "CVE-2021-44228")

        Returns:
            EPSSScore or None if not found
        """
        # Normalize CVE ID
        cve_id = cve_id.upper().strip()

        # Check cache
        cached = self.cache.get(cve_id)
        if cached:
            self.stats["cache_hits"] += 1
            return cached

        self.stats["cache_misses"] += 1

        # Fetch from API
        try:
            self.stats["api_calls"] += 1
            response = await self.http_client.get(
                f"{self.BASE_URL}/epss",
                params={"cve": cve_id}
            )
            response.raise_for_status()

            data = response.json()

            if not data.get("data"):
                logger.warning(f"No EPSS data found for {cve_id}")
                return None

            # Parse response
            cve_data = data["data"][0]
            score = EPSSScore(
                cve_id=cve_data["cve"],
                epss=float(cve_data["epss"]),
                percentile=float(cve_data["percentile"]),
                date=cve_data["date"],
                fetched_at=datetime.utcnow().isoformat(),
            )

            # Cache it
            self.cache.set(score)

            return score

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching EPSS for {cve_id}: {e}")
            self.stats["errors"] += 1
            return None
        except Exception as e:
            logger.error(f"Error fetching EPSS for {cve_id}: {e}")
            self.stats["errors"] += 1
            return None

    async def get_scores_batch(self, cve_ids: List[str]) -> Dict[str, EPSSScore]:
        """Get EPSS scores for multiple CVEs (batch request).

        Args:
            cve_ids: List of CVE identifiers

        Returns:
            Dict mapping CVE ID to EPSSScore
        """
        if not cve_ids:
            return {}

        # Normalize CVE IDs
        cve_ids = [cve_id.upper().strip() for cve_id in cve_ids]

        results = {}
        to_fetch = []

        # Check cache first
        for cve_id in cve_ids:
            cached = self.cache.get(cve_id)
            if cached:
                results[cve_id] = cached
                self.stats["cache_hits"] += 1
            else:
                to_fetch.append(cve_id)
                self.stats["cache_misses"] += 1

        # Fetch remaining from API
        if to_fetch:
            try:
                self.stats["api_calls"] += 1

                # EPSS API supports multiple CVEs with comma-separated values
                cve_param = ",".join(to_fetch)

                response = await self.http_client.get(
                    f"{self.BASE_URL}/epss",
                    params={"cve": cve_param}
                )
                response.raise_for_status()

                data = response.json()

                for cve_data in data.get("data", []):
                    score = EPSSScore(
                        cve_id=cve_data["cve"],
                        epss=float(cve_data["epss"]),
                        percentile=float(cve_data["percentile"]),
                        date=cve_data["date"],
                        fetched_at=datetime.utcnow().isoformat(),
                    )

                    results[score.cve_id] = score
                    self.cache.set(score)

            except Exception as e:
                logger.error(f"Error batch fetching EPSS scores: {e}")
                self.stats["errors"] += 1

        return results

    async def get_high_risk_cves(
        self,
        min_epss: float = 0.7,
        limit: int = 100
    ) -> List[EPSSScore]:
        """Get CVEs with high exploitation probability.

        Args:
            min_epss: Minimum EPSS score (0-1)
            limit: Maximum number of results

        Returns:
            List of high-risk CVEs
        """
        try:
            self.stats["api_calls"] += 1

            # EPSS API supports filtering by score
            response = await self.http_client.get(
                f"{self.BASE_URL}/epss",
                params={
                    "epss-gt": min_epss,
                    "limit": limit,
                    "order": "!epss"  # Descending order
                }
            )
            response.raise_for_status()

            data = response.json()

            results = []
            for cve_data in data.get("data", []):
                score = EPSSScore(
                    cve_id=cve_data["cve"],
                    epss=float(cve_data["epss"]),
                    percentile=float(cve_data["percentile"]),
                    date=cve_data["date"],
                    fetched_at=datetime.utcnow().isoformat(),
                )
                results.append(score)

                # Cache it
                self.cache.set(score)

            return results

        except Exception as e:
            logger.error(f"Error fetching high-risk CVEs: {e}")
            self.stats["errors"] += 1
            return []

    def prioritize_cves(
        self,
        cve_scores: Dict[str, EPSSScore],
        threshold: float = 0.5
    ) -> Tuple[List[str], List[str]]:
        """Prioritize CVEs based on EPSS scores.

        Args:
            cve_scores: Dict of CVE ID to EPSSScore
            threshold: EPSS threshold for high priority

        Returns:
            Tuple of (high_priority_cves, low_priority_cves)
        """
        high_priority = []
        low_priority = []

        for cve_id, score in cve_scores.items():
            if score.epss >= threshold:
                high_priority.append(cve_id)
            else:
                low_priority.append(cve_id)

        # Sort by EPSS score (descending)
        high_priority.sort(
            key=lambda cve: cve_scores[cve].epss,
            reverse=True
        )
        low_priority.sort(
            key=lambda cve: cve_scores[cve].epss,
            reverse=True
        )

        return high_priority, low_priority

    def get_stats(self) -> Dict:
        """Get client statistics."""
        cache_stats = self.cache.get_stats()

        return {
            **self.stats,
            **cache_stats,
            "cache_hit_rate": (
                self.stats["cache_hits"] / (self.stats["cache_hits"] + self.stats["cache_misses"])
                if (self.stats["cache_hits"] + self.stats["cache_misses"]) > 0
                else 0
            ),
        }

    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()


# Global client instance
_epss_client: Optional[EPSSClient] = None


def get_epss_client() -> EPSSClient:
    """Get the global EPSS client instance."""
    global _epss_client
    if _epss_client is None:
        _epss_client = EPSSClient()
    return _epss_client


# Example usage
async def main():
    """Example usage of EPSS client."""
    client = EPSSClient()

    # Get single CVE score
    score = await client.get_score("CVE-2021-44228")  # Log4Shell
    if score:
        print(f"{score.cve_id}: EPSS={score.epss:.4f}, Percentile={score.percentile:.4f}")

    # Batch request
    cves = ["CVE-2021-44228", "CVE-2021-45046", "CVE-2022-22965"]
    scores = await client.get_scores_batch(cves)
    print(f"\nBatch results: {len(scores)} CVEs")

    # Get high-risk CVEs
    high_risk = await client.get_high_risk_cves(min_epss=0.9, limit=10)
    print(f"\nHigh-risk CVEs (EPSS > 0.9): {len(high_risk)}")
    for score in high_risk[:5]:
        print(f"  {score.cve_id}: {score.epss:.4f}")

    # Print statistics
    print(f"\nClient stats: {client.get_stats()}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
