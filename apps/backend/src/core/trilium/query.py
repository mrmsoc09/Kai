from __future__ import annotations

import json
import logging
import re
from typing import Any

from .client import TriliumClient

logger = logging.getLogger(__name__)


class OrchestrationQueryLayer:
    """
    Query interface for AI agents to retrieve intelligence from Trilium.
    Outputs are optimized for LLM token efficiency.
    """

    def __init__(self, client: TriliumClient):
        self.client = client

    @staticmethod
    def clean_html(raw_html: str) -> str:
        """Removes HTML tags and normalizes whitespace for LLM consumption."""
        # Remove script and style elements
        clean = re.sub(r"<(script|style).*?>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
        # Remove tags
        clean = re.sub(r"<.*?>", " ", clean)
        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    async def search_intelligence(self, query_string: str) -> list[dict[str, Any]]:
        """Performs a search and returns high-level metadata for matching notes."""
        results = await self.client.search_notes(query_string)
        return [
            {
                "noteId": r["noteId"],
                "title": r["title"],
                "type": r["type"],
            }
            for r in results
        ]

    async def get_target_context(self, target_id: str) -> dict[str, Any]:
        """Retrieves note content plus all linked relations and attributes."""
        note = await self.client.get_note(target_id)
        attributes = await self.client.get_attributes(target_id)
        
        # Format attributes and relations
        labels = {}
        relations = []
        for attr in attributes:
            if attr["type"] == "label":
                labels[attr["name"]] = attr["value"]
            elif attr["type"] == "relation":
                relations.append({
                    "type": attr["name"],
                    "targetId": attr["value"]
                })

        return {
            "noteId": target_id,
            "title": note["title"],
            "content": self.clean_html(note.get("content", "")),
            "labels": labels,
            "relations": relations,
        }

    async def summarize_attack_surface(self, parent_id: str) -> str:
        """
        Returns a JSON summary of all infrastructure found under a parent.
        Optimized for prompt injection into agent workflows.
        """
        # Fetch child notes
        # In ETAPI, getting children requires a search or a specific endpoint.
        # Assuming search syntax for children: 'parentId=XYZ'
        children = await self.client.search_notes(f"parentId={parent_id}")
        
        summary = {
            "target_id": parent_id,
            "discovered_ports": set(),
            "services": set(),
            "vulnerabilities": [],
            "subdomains": set(),
        }

        for child in children:
            note_id = child["noteId"]
            attrs = await self.client.get_attributes(note_id)
            
            for attr in attrs:
                name = attr["name"].lower()
                value = attr["value"]
                if name == "port":
                    summary["discovered_ports"].add(value)
                elif name == "service":
                    summary["services"].add(value)
                elif name == "cve" or "vuln" in name:
                    summary["vulnerabilities"].append({
                        "id": value,
                        "noteId": note_id
                    })
                elif name == "domain" or name == "subdomain":
                    summary["subdomains"].add(value)

        # Convert sets to sorted lists for JSON serialization
        summary["discovered_ports"] = sorted(list(summary["discovered_ports"]))
        summary["services"] = sorted(list(summary["services"]))
        summary["subdomains"] = sorted(list(summary["subdomains"]))

        return json.dumps(summary, indent=2)
