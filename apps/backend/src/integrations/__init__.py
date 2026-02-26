"""
External API Integrations for Kaison K1

Provides clients for external security data sources.
"""

from .epss_client import EPSSClient, get_epss_client

__all__ = ["EPSSClient", "get_epss_client"]
