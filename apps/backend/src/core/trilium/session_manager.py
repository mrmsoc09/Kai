from __future__ import annotations

import asyncio
import random
import logging
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, Optional
from pathlib import Path 
import uuid 

import httpx
from .client import TriliumClient


logger = logging.getLogger(__name__)

@dataclass
class TargetSession:
    target_id: str
    base_url: str
    cookies: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    last_checked: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True
    auth_config: Dict[str, Any] = field(default_factory=dict)

class SessionManager:
    """
    K1 Authentication & Session Resilience Module.
    Manages concurrent authenticated sessions with autonomous re-auth.
    """

    def __init__(self, trilium_client: TriliumClient, protected_root_id: str):
        self.trilium = trilium_client
        self.protected_root_id = protected_root_id
        self.sessions: Dict[str, TargetSession] = {}
        self._lock = asyncio.Lock()
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def start(self):
        """Starts the session heartbeat monitor."""
        if not self._running:
            self._running = True
            self._heartbeat_task = asyncio.create_task(self._run_heartbeat())
            logger.info("SessionManager heartbeat monitor started.")

    async def stop(self):
        """Stops the session heartbeat monitor."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            logger.info("SessionManager heartbeat monitor stopped.")

    async def get_session(self, target_id: str) -> Optional[TargetSession]:
        """Retrieves a valid session for a target, potentially pulling from Trilium."""
        async with self._lock:
            if target_id in self.sessions and self.sessions[target_id].is_active:
                return self.sessions[target_id]
            
            # Try to restore from Trilium Protected Vault
            session = await self._restore_session_from_vault(target_id)
            if session:
                self.sessions[target_id] = session
                return session
            
            return None

    async def _restore_session_from_vault(self, target_id: str) -> Optional[TargetSession]:
        """Pulls credentials and cookies from the Trilium Protected Vault using attributes."""
        try:
            # Search by attribute for precision
            query = f"note.labels.session_target='{target_id}'"
            results = await self.trilium.search_notes(query)
            
            if not results:
                logger.debug(f"No protected session attribute found for {target_id}. Checking by title...")
                query_alt = f"note.title='Session:{target_id}'"
                results = await self.trilium.search_notes(query_alt)
            
            if not results:
                return None
            
            note_id = results[0]["noteId"]
            note = await self.trilium.get_note(note_id)
            
            # Clean and parse JSON content
            content = note.get("content", "{}")
            # Remove HTML tags if present (LLM-friendly cleaning)
            clean_json = re.sub(r"<.*?>", "", content).strip()
            data = json.loads(clean_json)
            
            return TargetSession(
                target_id=target_id,
                base_url=data.get("base_url"),
                cookies=data.get("cookies", {}),
                headers=data.get("headers", {}),
                auth_config=data.get("auth_config", {})
            )
        except Exception as e:
            logger.error(f"Vault restoration failed for {target_id}: {str(e)}")
            return None

    async def _save_session_to_vault(self, session: TargetSession):
        """Persists session state with a search-optimized label."""
        try:
            data = {
                "base_url": session.base_url,
                "cookies": session.cookies,
                "headers": session.headers,
                "auth_config": session.auth_config,
                "updated_at": datetime.now(UTC).isoformat()
            }
            content = f"<pre><code>{json.dumps(data, indent=2)}</code></pre>"
            title = f"Session:{session.target_id}"
            
            # Check for existing note by attribute
            query = f"note.labels.session_target='{session.target_id}'"
            results = await self.trilium.search_notes(query)
            
            if results:
                note_id = results[0]["noteId"]
                await self.trilium.update_note(note_id, content)
            else:
                # Create new note and tag it
                new_note = await self.trilium.create_note(
                    parent_id=self.protected_root_id,
                    title=title,
                    content=content
                )
                note_id = new_note["note"]["noteId"]
                await self.trilium.create_attribute(note_id, "label", "session_target", session.target_id)
                
            logger.info(f"Session {session.target_id} persisted to vault.")
        except Exception as e:
            logger.error(f"Vault persistence failed for {session.target_id}: {str(e)}")

    async def _run_heartbeat(self):
        """Periodically checks all active sessions."""
        while self._running:
            targets = list(self.sessions.keys())
            for target_id in targets:
                session = self.sessions[target_id]
                if not await self._check_session_alive(session):
                    logger.warning(f"Session for {target_id} expired. Attempting auto-reauth.")
                    await self._reauthenticate(session)
            
            await asyncio.sleep(60) # Check every minute

    async def _check_session_alive(self, session: TargetSession) -> bool:
        """Attempts to access a heartbeat endpoint to verify session validity."""
        heartbeat_url = session.auth_config.get("heartbeat_endpoint")
        if not heartbeat_url:
            return True # Assume alive if no check configured
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    heartbeat_url, 
                    cookies=session.cookies, 
                    headers=session.headers,
                    timeout=10.0
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def _reauthenticate(self, session: TargetSession):
        """Autonomous re-authentication flow."""
        login_url = session.auth_config.get("login_url")
        creds = session.auth_config.get("credentials")
        
        if not login_url or not creds:
            logger.error(f"Cannot re-auth {session.target_id}: Missing config.")
            session.is_active = False
            return

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(login_url, json=creds, timeout=20.0)
                if resp.status_code == 200:
                    session.cookies = dict(resp.cookies)
                    # Merge or replace headers if needed
                    session.is_active = True
                    session.last_checked = datetime.now(UTC)
                    await self._save_session_to_vault(session)
                    logger.info(f"Successfully re-authenticated for {session.target_id}")
                else:
                    logger.error(f"Re-auth failed for {session.target_id}: {resp.status_code}")
                    session.is_active = False
        except Exception as e:
            logger.error(f"Error during re-auth for {session.target_id}: {str(e)}")
            session.is_active = False

    def get_auth_headers(self, target_id: str) -> Dict[str, str]:
        """Provides valid headers/cookies for agents to use."""
        session = self.sessions.get(target_id)
        if not session or not session.is_active:
            return {}
        
        # Combine cookies into Cookie header or return as dict
        headers = session.headers.copy()
        if session.cookies:
            cookie_str = "; ".join([f"{k}={v}" for k, v in session.cookies.items()])
            headers["Cookie"] = cookie_str
        
        return headers
