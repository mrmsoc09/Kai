from __future__ import annotations

import logging
import json
from typing import Dict, Any, Optional
from .trilium.client import TriliumClient

logger = logging.getLogger(__name__)

class PersistenceManager:
    """
    K1 Persistence Manager (Stage 25).
    Saves and restores mission states to ensure '3+3' test continuity.
    """

    def __init__(self, trilium_client: TriliumClient):
        self.trilium = trilium_client
        self.checkpoint_root_id = "checkpoints"

    async def save_state(self, mission_id: str, state: Dict[str, Any]):
        """Persists the current state of a mission."""
        title = f"Checkpoint:{mission_id}"
        content = f"<pre><code>{json.dumps(state, indent=2)}</code></pre>"
        
        # Search for existing
        query = f"note.title='{title}'"
        results = await self.trilium.search_notes(query)
        
        if results:
            await self.trilium.update_note(results[0]["noteId"], content)
            logger.info(f"Persistence: Updated checkpoint for {mission_id}")
        else:
            note = await self.trilium.create_note(self.checkpoint_root_id, title, content)
            note_id = note["note"]["noteId"]
            await self.trilium.create_attribute(note_id, "label", "mission_id", mission_id)
            await self.trilium.create_attribute(note_id, "label", "type", "checkpoint")
            logger.info(f"Persistence: Created new checkpoint for {mission_id}")

    async def load_state(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """Restores the state of a mission."""
        query = f"note.labels.mission_id='{mission_id}' AND note.labels.type='checkpoint'"
        results = await self.trilium.search_notes(query)
        
        if not results:
            logger.warning(f"Persistence: No checkpoint found for {mission_id}")
            return None
            
        note_id = results[0]["noteId"]
        note = await self.trilium.get_note(note_id)
        
        try:
            raw_content = note.get("content", "{}")
            # Basic HTML strip
            json_str = raw_content.replace("<pre><code>", "").replace("</code></pre>", "").strip()
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Persistence: Failed to parse state for {mission_id}: {e}")
            return None
