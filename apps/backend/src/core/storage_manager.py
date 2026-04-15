from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _resolve_storage_path(storage_path: str | Path | None) -> Path:
    configured = (
        storage_path
        or os.getenv("K1_VECTOR_MEMORY_PATH")
        or "/mnt/nvme/k1_data/vector_memory/"
    )
    primary = Path(str(configured)).expanduser()
    try:
        primary.mkdir(parents=True, exist_ok=True)
        return primary.resolve()
    except OSError as exc:
        fallback = (Path.cwd() / "runtime" / "k1-vector-memory").resolve()
        fallback.mkdir(parents=True, exist_ok=True)
        logger.warning(
            "StorageManager path '%s' unavailable (%s); using fallback '%s'",
            primary,
            exc,
            fallback,
        )
        return fallback


class StorageManager:
    """
    Persistent Layer for Experience Memory using ChromaDB.
    Located on the NVMe (/mnt/nvme/k1_data/vector_memory/).
    """

    def __init__(self, storage_path: str | Path | None = None):
        self.storage_path = _resolve_storage_path(storage_path)
        self._client = None
        self._collection = None
        self._initialize_chroma()

    def _initialize_chroma(self):
        try:
            import chromadb
            from chromadb.config import Settings
            
            self._client = chromadb.PersistentClient(path=str(self.storage_path))
            # Schema: HNWS cosine space for tactical similarity
            self._collection = self._client.get_or_create_collection(
                name="k1_tactical_experience",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"ChromaDB initialized at {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")

    def persist_experience(self, experience_id: str, document: str, metadata: Dict[str, Any]):
        if self._collection:
            try:
                self._collection.add(
                    ids=[experience_id],
                    documents=[document],
                    metadatas=[metadata]
                )
            except Exception as e:
                logger.error(f"ChromaDB persistence failed: {e}")

    def query_similar_experiences(self, query_text: str, n_results: int = 10) -> List[Dict[str, Any]]:
        if not self._collection:
            return []
        try:
            results = self._collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            
            formatted = []
            ids = results.get("ids", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            
            for i in range(len(ids)):
                formatted.append({
                    "id": ids[i],
                    "metadata": metadatas[i],
                    "score": 1.0 - distances[i] # Similarity score
                })
            return formatted
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            return []
