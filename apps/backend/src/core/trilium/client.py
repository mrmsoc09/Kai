from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


from urllib.parse import urlparse

class TriliumClient:
    """
    Asynchronous transport layer for Trilium Notes ETAPI.
    Implements exponential backoff and core note management.
    """

    def __init__(self, url: str | None = None, token: str | None = None):
        raw_url = (url or os.environ.get("TRILIUM_URL", "")).rstrip("/")
        if not raw_url:
            logger.warning("TRILIUM_URL not provided.")
        
        # Security: Basic SSRF protection by validating URL format
        parsed = urlparse(raw_url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Invalid Trilium URL scheme: {parsed.scheme}")
        if not parsed.netloc:
            raise ValueError("Invalid Trilium URL: missing network location")

        self.url = raw_url
        # Token must be injected by caller (from Vault/secret_manager) — never read from env here
        if token is None:
            raise ValueError("TriliumClient requires token to be passed explicitly; use secret_manager")
        self.token = token
        
        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(base_url=self.url, headers=self.headers, timeout=30.0)

    async def request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        max_retries: int = 5,
    ) -> httpx.Response:
        """
        Executes an async HTTP request with exponential backoff for 429 and 5xx errors.
        """
        attempt = 0
        while attempt < max_retries:
            try:
                response = await self.client.request(method, path, json=data, params=params)
                
                # Check for retryable errors
                if response.status_code == 429 or 500 <= response.status_code < 600:
                    attempt += 1
                    wait_time = (2 ** attempt) + (0.1 * attempt) # Exponential backoff
                    logger.warning(
                        f"Trilium API returned {response.status_code} for {method} {path}. "
                        f"Retrying in {wait_time:.2f}s (Attempt {attempt}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as e:
                logger.error(f"Trilium API error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Trilium connection error: {str(e)}")
                if attempt < max_retries - 1:
                    attempt += 1
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    continue
                raise

        raise Exception(f"Trilium request failed after {max_retries} attempts.")

    async def get_note(self, note_id: str) -> dict[str, Any]:
        """Retrieves a specific note by its ID."""
        response = await self.request("GET", f"/etapi/notes/{note_id}")
        return response.json()

    async def create_note(
        self,
        parent_id: str,
        title: str,
        content: str,
        note_type: str = "text",
        is_expanded: bool = False,
    ) -> dict[str, Any]:
        """Creates a new note under a specific parent."""
        data = {
            "parentNoteId": parent_id,
            "title": title,
            "content": content,
            "type": note_type,
            "isExpanded": is_expanded,
        }
        response = await self.request("POST", "/etapi/notes", data=data)
        return response.json()

    async def create_attribute(
        self,
        note_id: str,
        type: str,
        name: str,
        value: str | None = None,
        is_inheritable: bool = False,
    ) -> dict[str, Any]:
        """Creates an attribute (label or relation) for a specific note."""
        data = {
            "noteId": note_id,
            "type": type,
            "name": name,
            "value": value,
            "isInheritable": is_inheritable,
        }
        response = await self.request("POST", "/etapi/attributes", data=data)
        return response.json()

    async def get_attributes(self, note_id: str) -> list[dict[str, Any]]:
        """Retrieves all attributes for a specific note."""
        response = await self.request("GET", f"/etapi/notes/{note_id}/attributes")
        return response.json()

    async def search_notes(self, query: str) -> list[dict[str, Any]]:
        """Searches for notes using Trilium's search syntax."""
        params = {"search": query}
        response = await self.request("GET", "/etapi/notes", params=params)
        return response.json()["results"]

    async def update_note(self, note_id: str, content: str) -> dict[str, Any]:
        """Updates the content of an existing note."""
        data = {"content": content}
        response = await self.request("PATCH", f"/etapi/notes/{note_id}/content", data=data)
        return {"status": "updated", "noteId": note_id}

    async def move_note(self, note_id: str, new_parent_id: str) -> dict[str, Any]:
        """Moves a note to a new parent by updating its branch."""
        # ETAPI moves are done by patching the branch.
        # This assumes the note only has one branch.
        params = {"noteId": note_id}
        branches = (await self.request("GET", "/etapi/branches", params=params)).json()
        if not branches:
            raise Exception(f"No branches found for note {note_id}")
        
        branch_id = branches[0]["branchId"]
        data = {"parentNoteId": new_parent_id}
        await self.request("PATCH", f"/etapi/branches/{branch_id}", data=data)
        return {"status": "moved", "noteId": note_id, "newParent": new_parent_id}

    async def close(self):
        """Closes the underlying httpx client."""
        await self.client.aclose()
