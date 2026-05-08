"""
MISP (Malware Information Sharing Platform) Integration for KAISON AI.

MISP provides threat intelligence — IOCs, threat actors, campaigns,
and vulnerability data — enriching KAISON findings with community
intelligence before and during scan phases.

Credentials: MISP_URL, MISP_API_KEY via Vault.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from .secret_manager import get_secret_manager

logger = logging.getLogger(__name__)


class MISPClient:
    """
    MISP threat intelligence client for KAISON AI.

    Queries MISP for IOC matches, threat actor attribution,
    and vulnerability context during scan enrichment phases.

    Credentials: MISP_URL, MISP_API_KEY via Vault.
    """

    def __init__(self, url: str = "", api_key: str = ""):
        self.url = (
            url
            or get_secret_manager().get_optional("MISP_URL")
            or "http://localhost:80"
        ).rstrip("/")
        self.api_key = (
            api_key
            or get_secret_manager().get_optional("MISP_API_KEY")
            or ""
        )
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "Authorization": self.api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
            })

    def health_check(self) -> bool:
        """Returns True if MISP is reachable."""
        try:
            resp = self.session.get(
                f"{self.url}/servers/getPyMISPVersion.json",
                timeout=10,
            )
            return resp.status_code < 400
        except Exception as exc:
            logger.warning("MISP health check failed: %s", exc)
            return False

    def search_by_value(
        self,
        value: str,
        type_attribute: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Search MISP for attributes matching a value.

        Args:
            value: IOC value (IP, domain, hash, URL, etc.)
            type_attribute: Optional MISP attribute type filter
                            (e.g. "ip-dst", "domain", "url", "md5")
            limit: Maximum number of results to return

        Returns:
            List of matching MISP attribute dicts
        """
        payload: dict[str, Any] = {
            "returnFormat": "json",
            "value": value,
            "limit": limit,
        }
        if type_attribute:
            payload["type"] = type_attribute

        try:
            resp = self.session.post(
                f"{self.url}/attributes/restSearch",
                json=payload,
                timeout=30,
            )
            if resp.status_code < 400:
                data = resp.json()
                return data.get("response", {}).get("Attribute", [])
            logger.warning("MISP search failed: %s", resp.status_code)
            return []
        except Exception as exc:
            logger.error("MISP search error: %s", exc)
            return []

    def search_events(
        self,
        value: str | None = None,
        tags: list[str] | None = None,
        threat_level: int | None = None,
        limit: int = 10,
        _use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Search MISP events (threat reports).

        Args:
            value: Optional IOC value to match
            tags: Optional list of MISP tags to filter by
            threat_level: 1=High, 2=Medium, 3=Low, 4=Undefined
            limit: Maximum number of events to return

        Returns:
            List of MISP event dicts
        """
        cache_key = f"events:{value}:{tags}:{threat_level}:{limit}"
        if _use_cache:
            try:
                from .scan_cache import get_scan_cache
                hit = get_scan_cache().get("misp", cache_key)
                if hit is not None:
                    return hit
            except Exception:
                pass

        payload: dict[str, Any] = {
            "returnFormat": "json",
            "limit": limit,
        }
        if value:
            payload["value"] = value
        if tags:
            payload["tags"] = tags
        if threat_level is not None:
            payload["threat_level_id"] = threat_level

        try:
            resp = self.session.post(
                f"{self.url}/events/restSearch",
                json=payload,
                timeout=30,
            )
            if resp.status_code < 400:
                data = resp.json()
                result = data.get("response", [])
                if _use_cache:
                    try:
                        from .scan_cache import get_scan_cache
                        get_scan_cache().set("misp", cache_key, result)
                    except Exception:
                        pass
                return result
            logger.warning("MISP event search failed: %s", resp.status_code)
            return []
        except Exception as exc:
            logger.error("MISP event search error: %s", exc)
            return []

    def enrich_ioc(
        self,
        ioc_type: str,
        ioc_value: str,
        _use_cache: bool = True,
    ) -> dict[str, Any]:
        """
        High-level IOC enrichment: queries both attributes and events,
        returns a consolidated enrichment summary.

        Args:
            ioc_type: "ip", "domain", "url", "hash"
            ioc_value: The IOC value to enrich

        Returns:
            Dict with keys: ioc_type, ioc_value, attribute_hits,
            event_count, threat_level, tags, first_seen, last_seen
        """
        cache_key = f"enrich:{ioc_type}:{ioc_value}"
        if _use_cache:
            try:
                from .scan_cache import get_scan_cache
                hit = get_scan_cache().get("misp", cache_key)
                if hit is not None:
                    return hit
            except Exception:
                pass

        type_map = {
            "ip": "ip-dst",
            "domain": "domain",
            "url": "url",
            "hash": None,  # will match md5/sha1/sha256
        }
        misp_type = type_map.get(ioc_type)

        attributes = self.search_by_value(ioc_value, type_attribute=misp_type)
        events = self.search_events(value=ioc_value, limit=5)

        all_tags: list[str] = []
        threat_levels: list[int] = []
        first_seen: str | None = None
        last_seen: str | None = None

        for attr in attributes:
            for tag in attr.get("Tag", []):
                name = tag.get("name", "")
                if name and name not in all_tags:
                    all_tags.append(name)
            ts = attr.get("timestamp")
            if ts:
                ts_str = str(ts)
                if first_seen is None or ts_str < first_seen:
                    first_seen = ts_str
                if last_seen is None or ts_str > last_seen:
                    last_seen = ts_str

        for event in events:
            evt = event.get("Event", event)
            tl = evt.get("threat_level_id")
            if tl:
                try:
                    threat_levels.append(int(tl))
                except (ValueError, TypeError):
                    pass

        max_threat = min(threat_levels) if threat_levels else None  # lower = higher threat in MISP

        result = {
            "ioc_type": ioc_type,
            "ioc_value": ioc_value,
            "attribute_hits": len(attributes),
            "event_count": len(events),
            "threat_level": max_threat,
            "tags": all_tags[:20],
            "first_seen": first_seen,
            "last_seen": last_seen,
            "known_malicious": len(attributes) > 0,
        }
        if _use_cache:
            try:
                from .scan_cache import get_scan_cache
                get_scan_cache().set("misp", cache_key, result)
            except Exception:
                pass
        return result

    def add_finding_as_event(
        self,
        finding: dict[str, Any],
        scan_id: str,
        distribution: int = 0,
    ) -> str | None:
        """
        Pushes a KAISON finding into MISP as a new event for sharing.

        Args:
            finding: Finding dict with type, severity, value, target
            scan_id: KAISON scan ID for deduplication
            distribution: 0=org only, 1=community, 2=connected, 3=all

        Returns:
            New MISP event UUID or None on failure
        """
        event_info = (
            f"[KAI-{scan_id[:8]}] "
            f"{finding.get('finding_type', 'finding')} — "
            f"{finding.get('target', 'unknown')}"
        )
        threat_map = {"critical": 1, "high": 1, "medium": 2, "low": 3}
        threat_level = threat_map.get(
            str(finding.get("severity", "")).lower(), 4
        )

        attributes = []
        target = finding.get("target") or finding.get("value")
        if target:
            attributes.append({
                "type": "target-external",
                "value": str(target),
                "category": "External analysis",
            })

        payload = {
            "Event": {
                "info": event_info,
                "threat_level_id": str(threat_level),
                "analysis": "1",  # ongoing
                "distribution": str(distribution),
                "Attribute": attributes,
                "Tag": [{"name": "tlp:amber"}, {"name": "kai:auto-generated"}],
            }
        }

        try:
            resp = self.session.post(
                f"{self.url}/events",
                json=payload,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                event = data.get("Event", data)
                uuid_val = event.get("uuid")
                logger.info("Created MISP event %s for scan %s", uuid_val, scan_id)
                return uuid_val
            logger.warning("MISP add event failed: %s", resp.status_code)
            return None
        except Exception as exc:
            logger.error("MISP add event error: %s", exc)
            return None
