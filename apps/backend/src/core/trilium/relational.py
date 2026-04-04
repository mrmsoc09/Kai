from __future__ import annotations

import logging
import re
from typing import Any

from .client import TriliumClient

logger = logging.getLogger(__name__)


class SpiderWebEngine:
    """
    Relational engine for mapping infrastructure connections in Trilium.
    Handles attributes, relations, and automatic discovery of asset links.
    """

    # Regex for IP addresses and basic Domain names
    IP_REGEX = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    DOMAIN_REGEX = r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\b"

    def __init__(self, client: TriliumClient):
        self.client = client

    async def add_attribute(self, note_id: str, key: str, value: str | None = None):
        """Adds a label attribute to a note if it doesn't already exist."""
        existing = await self.client.get_attributes(note_id)
        for attr in existing:
            if attr["type"] == "label" and attr["name"] == key and attr["value"] == value:
                logger.debug(f"Attribute {key}={value} already exists on note {note_id}")
                return
        
        await self.client.create_attribute(note_id, "label", key, value)
        logger.info(f"Added attribute {key}={value} to note {note_id}")

    async def create_relation(self, source_id: str, target_id: str, relation_type: str):
        """Creates a relation between two notes if it doesn't already exist."""
        existing = await self.client.get_attributes(source_id)
        for attr in existing:
            if attr["type"] == "relation" and attr["name"] == relation_type and attr["value"] == target_id:
                logger.debug(f"Relation {relation_type}->{target_id} already exists on note {source_id}")
                return
        
        await self.client.create_attribute(source_id, "relation", relation_type, target_id)
        logger.info(f"Created relation {relation_type} from {source_id} to {target_id}")

    async def parse_and_map_discovery(self, note_id: str, content: str):
        """
        Parses discovery note content for IP-Domain relationships and maps them.
        This is a simplified version that looks for adjacent or associated assets.
        """
        ips = re.findall(self.IP_REGEX, content)
        domains = re.findall(self.DOMAIN_REGEX, content, re.IGNORECASE)
        
        # Remove duplicates
        ips = list(dict.fromkeys(ips))
        domains = list(dict.fromkeys(domains))
        
        if not ips or not domains:
            return

        logger.info(f"Found {len(ips)} IPs and {len(domains)} domains in note {note_id}")
        
        # Add basic attributes to the discovery note itself
        for ip in ips:
            await self.add_attribute(note_id, "ip", ip)
        for domain in domains:
            await self.add_attribute(note_id, "domain", domain)
            
        # Here we could implement more complex logic to find specific pairs.
        # For now, we'll tag the note with all found assets.
        # Relational mapping often requires knowing the context (e.g. 'resolves to').
        # If a line contains both an IP and a domain, create a relation.
        for line in content.splitlines():
            line_ips = re.findall(self.IP_REGEX, line)
            line_domains = re.findall(self.DOMAIN_REGEX, line, re.IGNORECASE)
            
            for d in line_domains:
                for ip in line_ips:
                    # In a real scenario, we'd find the Note IDs for these IP/Domain assets.
                    # This requires a search capability (Stage 5).
                    # For Stage 3, we acknowledge the relationship in telemetry.
                    logger.debug(f"Discovered relationship: {d} -> {ip} in line: {line.strip()[:50]}...")
