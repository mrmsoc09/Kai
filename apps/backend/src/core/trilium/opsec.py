from __future__ import annotations

import logging
import os
import re
from typing import Any

from .client import TriliumClient

logger = logging.getLogger(__name__)


class OpsecFilter:
    """
    Scans content for sensitive information and redacts it.
    Matches API keys, Bearer tokens, Private Keys, and common exploit patterns.
    """

    # Common sensitive patterns
    PATTERNS = {
        "API_KEY": r"(?i)(?:api_key|apikey|secret|token|password)[\s:=]+['\"]?([a-zA-Z0-9]{16,})['\"]?",
        "BEARER_TOKEN": r"(?i)Bearer\s+([a-zA-Z0-9\-\._~+/]+=*)",
        "PRIVATE_KEY": r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+ PRIVATE KEY-----",
        "GENERIC_SECRET": r"(?i)(?:id|key|secret|pass|token)[\s:=]+[^\s]{12,}",
        "JWT_TOKEN": r"ey[a-zA-Z0-9\-_]+\.ey[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+",
    }

    REDACTION_MESSAGE = "SENSITIVE DATA REDACTED - MOVED TO PROTECTED VAULT"

    def __init__(self):
        self._regex_map = {name: re.compile(pat) for name, pat in self.PATTERNS.items()}

    def scan(self, content: str) -> tuple[str, bool]:
        """
        Scans content for matches.
        Returns (processed_content, found_sensitive)
        """
        sensitive_found = False
        processed = content

        for name, regex in self._regex_map.items():
            if regex.search(processed):
                logger.warning(f"OPSEC: Detected {name} in payload.")
                processed = regex.sub(self.REDACTION_MESSAGE, processed)
                sensitive_found = True

        return processed, sensitive_found


class TriliumOpsecClient:
    """
    Middleware wrapper for TriliumClient that enforces OPSEC filtering.
    """

    def __init__(self, client: TriliumClient, protected_root_id: str | None = None):
        self.client = client
        self.protected_root_id = protected_root_id or os.environ.get("PROTECTED_ROOT_ID", "protected")
        self.filter = OpsecFilter()

    async def create_note(
        self,
        parent_id: str,
        title: str,
        content: str,
        note_type: str = "text",
        is_expanded: bool = False,
    ) -> dict[str, Any]:
        """Intercepts note creation, filters content, and routes sensitive data if needed."""
        clean_content, sensitive_found = self.filter.scan(content)
        
        # If sensitive data was found, we store the ORIGINAL content in the protected subtree
        # and the CLEANED content in the original location.
        if sensitive_found:
            logger.info(f"OPSEC: Routing sensitive discovery to protected root {self.protected_root_id}")
            # Create the protected note first
            protected_title = f"[PROTECTED] {title}"
            await self.client.create_note(
                parent_id=self.protected_root_id,
                title=protected_title,
                content=content,
                note_type=note_type
            )
            
        # Continue with creation of the (cleaned) public note
        return await self.client.create_note(
            parent_id=parent_id,
            title=title,
            content=clean_content,
            note_type=note_type,
            is_expanded=is_expanded
        )

    async def update_note(self, note_id: str, content: str) -> dict[str, Any]:
        """Intercepts note updates and redacts sensitive information."""
        clean_content, _ = self.filter.scan(content)
        return await self.client.update_note(note_id, clean_content)

    # Delegate other calls to the base client
    def __getattr__(self, name):
        return getattr(self.client, name)
